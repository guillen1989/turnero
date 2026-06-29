"""Tests del aviso de interés: cambio ↔ cambio con solapamiento unilateral."""
from datetime import date

from app.extensions import db
from app.models import (
    Categoria,
    FranjaHoraria,
    Notificacion,
    PublicacionCambio,
    TurnoCedido,
    TurnoAceptado,
    insertar_categorias_semilla,
)
from app.matching.service import buscar_avisos_interes_para, crear_aviso_oportunidad_3
from app.services.registro import registrar_usuario


def _usuario(nombre, email, password="password123"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario(nombre, email, password, "Hospital T", "Urgencias", cat.id)


def _franja(grupo_id, nombre="Mañana"):
    return FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id, nombre=nombre).first()


def _pub_cambio(usuario, franja, fecha_cede, fecha_acepta):
    pub = PublicacionCambio(usuario_id=usuario.id, tipo="cambio")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=fecha_cede, franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=fecha_acepta, franja_horaria_id=franja.id))
    db.session.commit()
    return pub


# --- buscar_avisos_interes_para ---

def test_sin_candidatas_devuelve_vacio(db):
    ana = _usuario("Ana", "ana@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)
    pub = _pub_cambio(ana, franja, date(2026, 7, 10), date(2026, 8, 3))
    assert buscar_avisos_interes_para(pub) == []


def test_tipo_no_cambio_devuelve_vacio(db):
    ana = _usuario("Ana", "ana@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)
    pub = PublicacionCambio(usuario_id=ana.id, tipo="regalo")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=date(2026, 7, 10), franja_horaria_id=franja.id))
    db.session.commit()
    assert buscar_avisos_interes_para(pub) == []


def test_match_directo_completo_no_genera_aviso(db):
    """Ambas direcciones cuadran → no es aviso de interés."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)
    pub_ana = _pub_cambio(ana, franja, date(2026, 7, 10), date(2026, 7, 21))
    # Pedro cede lo que Ana acepta y viceversa → match directo completo
    _pub_cambio(pedro, franja, date(2026, 7, 21), date(2026, 7, 10))
    assert buscar_avisos_interes_para(pub_ana) == []


def test_ninguna_direccion_no_genera_aviso(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)
    pub_ana = _pub_cambio(ana, franja, date(2026, 7, 10), date(2026, 8, 3))
    _pub_cambio(pedro, franja, date(2026, 9, 1), date(2026, 9, 5))
    assert buscar_avisos_interes_para(pub_ana) == []


def test_cedido_a_en_aceptados_b_devuelve_candidata(db):
    """A cede lo que B acepta, pero B cede algo que A no acepta → aviso."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)
    pub_ana = _pub_cambio(ana, franja, date(2026, 7, 10), date(2026, 8, 3))
    pub_pedro = _pub_cambio(pedro, franja, date(2026, 7, 21), date(2026, 7, 10))
    result = buscar_avisos_interes_para(pub_ana)
    assert pub_pedro in result


def test_cedido_b_en_aceptados_a_devuelve_candidata(db):
    """B cede lo que A acepta, pero A cede algo que B no acepta → aviso."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)
    pub_ana = _pub_cambio(ana, franja, date(2026, 7, 10), date(2026, 7, 21))
    pub_pedro = _pub_cambio(pedro, franja, date(2026, 7, 21), date(2026, 8, 9))
    result = buscar_avisos_interes_para(pub_ana)
    assert pub_pedro in result


# --- crear_aviso_oportunidad_3 ---

def test_crea_notificaciones_para_ambos_usuarios(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)
    pub_ana = _pub_cambio(ana, franja, date(2026, 7, 10), date(2026, 8, 3))
    pub_pedro = _pub_cambio(pedro, franja, date(2026, 7, 21), date(2026, 7, 10))

    crear_aviso_oportunidad_3(pub_ana, pub_pedro)

    assert Notificacion.query.filter_by(
        usuario_id=ana.id, publicacion_id=pub_pedro.id, tipo="aviso_oportunidad_3"
    ).count() == 1
    assert Notificacion.query.filter_by(
        usuario_id=pedro.id, publicacion_id=pub_ana.id, tipo="aviso_oportunidad_3"
    ).count() == 1


def test_no_duplica_notificaciones(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)
    pub_ana = _pub_cambio(ana, franja, date(2026, 7, 10), date(2026, 8, 3))
    pub_pedro = _pub_cambio(pedro, franja, date(2026, 7, 21), date(2026, 7, 10))

    crear_aviso_oportunidad_3(pub_ana, pub_pedro)
    crear_aviso_oportunidad_3(pub_ana, pub_pedro)

    assert Notificacion.query.filter_by(
        usuario_id=ana.id, publicacion_id=pub_pedro.id, tipo="aviso_oportunidad_3"
    ).count() == 1


# --- Integración: aviso generado al publicar ---

def test_aviso_generado_al_publicar(client, db):
    """Al publicar un cambio con solapamiento unilateral, ambos reciben aviso."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)
    # Ana cede 21/07, acepta 10/07
    _pub_cambio(ana, franja, date(2026, 7, 21), date(2026, 7, 10))

    # Pedro publica: cede 10/07, acepta 03/08 → Ana acepta 10/07 → solapamiento
    client.post("/auth/login", data={"email": "pedro@test.es", "password": "password123"})
    client.post("/publicar", data={
        "tipo": "cambio",
        "fecha_cedida_0": "2026-07-10",
        "franja_cedida_0": str(franja.id),
        "fecha_aceptada_0": "2026-08-03",
        "franja_aceptada_0": str(franja.id),
    })

    pub_pedro = PublicacionCambio.query.filter_by(usuario_id=pedro.id).first()
    assert pub_pedro is not None
    assert Notificacion.query.filter_by(usuario_id=pedro.id, tipo="aviso_oportunidad_3").count() >= 1
    assert Notificacion.query.filter_by(usuario_id=ana.id, tipo="aviso_oportunidad_3").count() >= 1
