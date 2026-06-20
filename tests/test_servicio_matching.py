"""Tests de integración del servicio de búsqueda de matches (Fase 4, paso 2).

Verifica los filtros de visibilidad (misma categoría + mismo grupo de intercambio)
y que el servicio combina correctamente el motor puro con la capa de datos.
"""
from datetime import date, time

from app.extensions import db
from app.models import (
    Categoria,
    FranjaHoraria,
    PublicacionCambio,
    TurnoCedido,
    TurnoAceptado,
    insertar_categorias_semilla,
)
from app.services.registro import registrar_usuario
from app.matching.service import buscar_matches_para


# --- Helpers ---

def _categoria(nombre="Enfermería"):
    insertar_categorias_semilla()
    return Categoria.query.filter_by(nombre=nombre).first()


def _usuario(nombre, email, hospital="H1", unidad="Urgencias", categoria=None):
    if categoria is None:
        categoria = _categoria()
    return registrar_usuario(nombre, email, "password123", hospital, unidad, categoria.id)


def _franja(grupo_id, nombre="Mañana"):
    return FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id, nombre=nombre).first()


def _publicacion(usuario, fecha_cede, franja_cede, fecha_acepta, franja_acepta):
    pub = PublicacionCambio(usuario_id=usuario.id)
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=fecha_cede, franja_horaria_id=franja_cede.id))
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=fecha_acepta, franja_horaria_id=franja_acepta.id))
    db.session.commit()
    return pub


# --- UAT-3.1: detecta match directo ---

def test_detecta_match_directo(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_ana = _publicacion(
        ana,
        fecha_cede=date(2026, 6, 25), franja_cede=franja,
        fecha_acepta=date(2026, 6, 26), franja_acepta=franja,
    )
    _publicacion(
        pedro,
        fecha_cede=date(2026, 6, 26), franja_cede=franja,
        fecha_acepta=date(2026, 6, 25), franja_acepta=franja,
    )

    matches = buscar_matches_para(pub_ana)
    assert len(matches) == 1
    assert matches[0].usuario_id == pedro.id


# --- UAT-3.2: sin match si no hay coincidencia en ambos sentidos ---

def test_no_detecta_match_si_un_sentido_no_coincide(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)
    franja2 = _franja(ana.unidad.grupo_intercambio_id, nombre="Tarde")

    pub_ana = _publicacion(
        ana,
        fecha_cede=date(2026, 6, 25), franja_cede=franja,
        fecha_acepta=date(2026, 6, 26), franja_acepta=franja,
    )
    _publicacion(
        pedro,
        fecha_cede=date(2026, 6, 27), franja_cede=franja2,
        fecha_acepta=date(2026, 6, 25), franja_acepta=franja,
    )

    assert buscar_matches_para(pub_ana) == []


# --- Filtros de visibilidad ---

def test_no_incluye_publicacion_propia(db):
    """Una publicación no puede hacer match consigo misma."""
    ana = _usuario("Ana", "ana@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub = _publicacion(
        ana,
        fecha_cede=date(2026, 6, 25), franja_cede=franja,
        fecha_acepta=date(2026, 6, 26), franja_acepta=franja,
    )

    assert buscar_matches_para(pub) == []


def test_no_incluye_diferente_categoria(db):
    """Enfermería no puede hacer match con Auxiliar."""
    insertar_categorias_semilla()
    cat_enf = Categoria.query.filter_by(nombre="Enfermería").first()
    cat_aux = Categoria.query.filter_by(nombre="Auxiliar de enfermería (TCAE)").first()

    ana = registrar_usuario("Ana", "ana@test.es", "password123", "H1", "Urgencias", cat_enf.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "H1", "Urgencias", cat_aux.id)
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_ana = _publicacion(
        ana,
        fecha_cede=date(2026, 6, 25), franja_cede=franja,
        fecha_acepta=date(2026, 6, 26), franja_acepta=franja,
    )
    _publicacion(
        pedro,
        fecha_cede=date(2026, 6, 26), franja_cede=franja,
        fecha_acepta=date(2026, 6, 25), franja_acepta=franja,
    )

    assert buscar_matches_para(pub_ana) == []


def test_no_incluye_diferente_grupo_intercambio(db):
    """Usuarios de grupos de intercambio distintos no se ven entre sí."""
    ana = registrar_usuario("Ana", "ana@test.es", "password123", "H1", "Urgencias", _categoria().id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "H2", "Cardiología", _categoria().id)

    franja_ana = _franja(ana.unidad.grupo_intercambio_id)
    franja_pedro = _franja(pedro.unidad.grupo_intercambio_id)

    pub_ana = _publicacion(
        ana,
        fecha_cede=date(2026, 6, 25), franja_cede=franja_ana,
        fecha_acepta=date(2026, 6, 26), franja_acepta=franja_ana,
    )
    _publicacion(
        pedro,
        fecha_cede=date(2026, 6, 26), franja_cede=franja_pedro,
        fecha_acepta=date(2026, 6, 25), franja_acepta=franja_pedro,
    )

    assert buscar_matches_para(pub_ana) == []


def test_no_incluye_publicaciones_inactivas(db):
    """Publicaciones canceladas o caducadas no aparecen como candidatas."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_ana = _publicacion(
        ana,
        fecha_cede=date(2026, 6, 25), franja_cede=franja,
        fecha_acepta=date(2026, 6, 26), franja_acepta=franja,
    )
    pub_pedro = _publicacion(
        pedro,
        fecha_cede=date(2026, 6, 26), franja_cede=franja,
        fecha_acepta=date(2026, 6, 25), franja_acepta=franja,
    )
    pub_pedro.estado = "cancelada"
    db.session.commit()

    assert buscar_matches_para(pub_ana) == []
