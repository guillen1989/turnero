"""
Tests de los tres escenarios de combinación de tipos de publicación.

Escenario 1 — Regalo ↔ Petición:
    user1 ofrece Regalo tarde día 1, user2 solicita Petición tarde día 1.
    Deben encontrarse y crear el match sin crash.

Escenario 2 — Cambio ↔ Regalo:
    user1 cambio (cede día2 tarde + día3 mañana, acepta día4 tarde + día5 tarde).
    user2 regalo (ofrece trabajar día3 mañana).
    No hay intercambio bidireccional posible: NO deben hacer match.

Escenario 3 — Junte ↔ Junte:
    user1 cadencia LMVD quiere noches LMXJ → cede V,D acepta M,J.
    user2 cadencia MJS quiere noches VSD  → cede M,J acepta V,D.
    Los cedidos de cada uno son los aceptados del otro: SÍ deben hacer match.
    Un junte NO hace match con cambio ni regalo.
"""
from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models import (
    Categoria,
    FranjaHoraria,
    PublicacionCambio,
    TurnoAceptado,
    TurnoCedido,
    insertar_categorias_semilla,
)
from app.matching.service import buscar_matches_para, crear_match_directo
from app.services.registro import registrar_usuario


# ── helpers ──────────────────────────────────────────────────────────────────

def _setup_usuarios():
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    u1 = registrar_usuario("User1", "u1@test.es", "pw", "H1", "Urgencias", cat.id)
    u2 = registrar_usuario("User2", "u2@test.es", "pw", "H1", "Urgencias", cat.id)
    return u1, u2


def _franja(grupo_id, nombre):
    return FranjaHoraria.query.filter_by(
        grupo_intercambio_id=grupo_id, nombre=nombre
    ).first()


# ── Escenario 1: Regalo ↔ Petición ───────────────────────────────────────────

def test_escenario1_regalo_peticion_busca_match(db):
    """Regalo tarde día1 debe encontrar Petición tarde día1."""
    u1, u2 = _setup_usuarios()
    tarde = _franja(u1.unidad.grupo_intercambio_id, "Tarde")
    dia1 = date(2026, 8, 1)

    regalo = PublicacionCambio(usuario_id=u1.id, tipo="regalo")
    db.session.add(regalo)
    db.session.flush()
    db.session.add(TurnoAceptado(publicacion_id=regalo.id, fecha=dia1,
                                 franja_horaria_id=tarde.id))

    peticion = PublicacionCambio(usuario_id=u2.id, tipo="peticion")
    db.session.add(peticion)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=peticion.id, fecha=dia1,
                               franja_horaria_id=tarde.id))
    db.session.commit()

    assert buscar_matches_para(regalo) == [peticion]
    assert buscar_matches_para(peticion) == [regalo]


def test_escenario1_crear_match_regalo_peticion_no_crash(db):
    """crear_match_directo regalo↔peticion no debe lanzar excepción ni devolver None."""
    u1, u2 = _setup_usuarios()
    tarde = _franja(u1.unidad.grupo_intercambio_id, "Tarde")
    dia1 = date(2026, 8, 1)

    regalo = PublicacionCambio(usuario_id=u1.id, tipo="regalo")
    db.session.add(regalo)
    db.session.flush()
    db.session.add(TurnoAceptado(publicacion_id=regalo.id, fecha=dia1,
                                 franja_horaria_id=tarde.id))

    peticion = PublicacionCambio(usuario_id=u2.id, tipo="peticion")
    db.session.add(peticion)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=peticion.id, fecha=dia1,
                               franja_horaria_id=tarde.id))
    db.session.commit()

    match = crear_match_directo(regalo, peticion)
    assert match is not None
    assert match.estado == "propuesto"


# ── Escenario 2: Cambio ↔ Regalo — sin match ─────────────────────────────────

def test_escenario2_cambio_no_hace_match_con_regalo(db):
    """
    Un cambio bidireccional NO puede hacer match con un regalo:
    el regalo no tiene turnos cedidos para satisfacer los aceptados del cambio.
    """
    u1, u2 = _setup_usuarios()
    grupo = u1.unidad.grupo_intercambio_id
    manana = _franja(grupo, "Mañana")
    tarde  = _franja(grupo, "Tarde")

    dia2, dia3, dia4, dia5 = (date(2026, 8, d) for d in (2, 3, 4, 5))

    # user1: cambio — cede día2 tarde + día3 mañana, acepta día4 tarde + día5 tarde
    cambio = PublicacionCambio(usuario_id=u1.id, tipo="cambio")
    db.session.add(cambio)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=cambio.id, fecha=dia2, franja_horaria_id=tarde.id))
    db.session.add(TurnoCedido(publicacion_id=cambio.id, fecha=dia3, franja_horaria_id=manana.id))
    db.session.add(TurnoAceptado(publicacion_id=cambio.id, fecha=dia4, franja_horaria_id=tarde.id))
    db.session.add(TurnoAceptado(publicacion_id=cambio.id, fecha=dia5, franja_horaria_id=tarde.id))

    # user2: regalo — ofrece trabajar día3 mañana (solo aceptado, sin cedidos)
    regalo = PublicacionCambio(usuario_id=u2.id, tipo="regalo")
    db.session.add(regalo)
    db.session.flush()
    db.session.add(TurnoAceptado(publicacion_id=regalo.id, fecha=dia3, franja_horaria_id=manana.id))
    db.session.commit()

    assert buscar_matches_para(cambio) == []
    assert buscar_matches_para(regalo) == []


# ── Escenario 3: Junte ↔ Junte ───────────────────────────────────────────────

def _junte(usuario, lunes, cedidos_dias, aceptados_dias, franja_noche):
    """Crea una publicación tipo junte con los días (0=lun…6=dom) indicados."""
    pub = PublicacionCambio(usuario_id=usuario.id, tipo="junte")
    db.session.add(pub)
    db.session.flush()
    for d in cedidos_dias:
        db.session.add(TurnoCedido(
            publicacion_id=pub.id,
            fecha=lunes + timedelta(days=d),
            franja_horaria_id=franja_noche.id,
        ))
    for d in aceptados_dias:
        db.session.add(TurnoAceptado(
            publicacion_id=pub.id,
            fecha=lunes + timedelta(days=d),
            franja_horaria_id=franja_noche.id,
        ))
    db.session.commit()
    return pub


def test_escenario3_junte_hace_match_con_junte_complementario(db):
    """
    user1 cadencia LMVD quiere LMXJ → cede V(4),D(6) acepta M(1),J(3).
    user2 cadencia MJS  quiere VSD  → cede M(1),J(3) acepta V(4),D(6).
    Los cedidos de cada uno son exactamente los aceptados del otro: match.
    """
    u1, u2 = _setup_usuarios()
    noche = _franja(u1.unidad.grupo_intercambio_id, "Noche")
    lunes = date(2026, 8, 3)  # lunes de una semana futura

    # user1: cadencia LMVD={0,2,4,6}, quiere trabajar LMXJ={0,1,2,3}
    # cede: {4,6} (V,D), acepta: {1,3} (M,J)
    j1 = _junte(u1, lunes, cedidos_dias=[4, 6], aceptados_dias=[1, 3], franja_noche=noche)

    # user2: cadencia MJS={1,3,5}, quiere trabajar VSD={4,5,6}
    # cede: {1,3} (M,J), acepta: {4,6} (V,D)
    j2 = _junte(u2, lunes, cedidos_dias=[1, 3], aceptados_dias=[4, 6], franja_noche=noche)

    assert buscar_matches_para(j1) == [j2]
    assert buscar_matches_para(j2) == [j1]


def test_escenario3_crear_match_junte_no_crash(db):
    """crear_match_directo entre dos juntes complementarios debe funcionar."""
    u1, u2 = _setup_usuarios()
    noche = _franja(u1.unidad.grupo_intercambio_id, "Noche")
    lunes = date(2026, 8, 3)

    j1 = _junte(u1, lunes, cedidos_dias=[4, 6], aceptados_dias=[1, 3], franja_noche=noche)
    j2 = _junte(u2, lunes, cedidos_dias=[1, 3], aceptados_dias=[4, 6], franja_noche=noche)

    match = crear_match_directo(j1, j2)
    assert match is not None
    assert match.estado == "propuesto"


def test_escenario3_junte_no_hace_match_con_cambio(db):
    """Un junte no debe hacer match con una publicación tipo cambio."""
    u1, u2 = _setup_usuarios()
    grupo = u1.unidad.grupo_intercambio_id
    noche = _franja(grupo, "Noche")
    tarde = _franja(grupo, "Tarde")
    lunes = date(2026, 8, 3)

    j1 = _junte(u1, lunes, cedidos_dias=[4, 6], aceptados_dias=[1, 3], franja_noche=noche)

    cambio = PublicacionCambio(usuario_id=u2.id, tipo="cambio")
    db.session.add(cambio)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=cambio.id,
                               fecha=lunes + timedelta(days=1), franja_horaria_id=noche.id))
    db.session.add(TurnoAceptado(publicacion_id=cambio.id,
                                 fecha=lunes + timedelta(days=4), franja_horaria_id=noche.id))
    db.session.commit()

    assert buscar_matches_para(j1) == []
    assert buscar_matches_para(cambio) == []


def test_escenario3_junte_sin_complementario_no_hace_match(db):
    """Dos juntes de la misma cadencia no hacen match entre sí."""
    u1, u2 = _setup_usuarios()
    noche = _franja(u1.unidad.grupo_intercambio_id, "Noche")
    lunes = date(2026, 8, 3)

    # Ambos ceden V,D y aceptan M,J — mismo perfil, no complementarios
    j1 = _junte(u1, lunes, cedidos_dias=[4, 6], aceptados_dias=[1, 3], franja_noche=noche)
    j2 = _junte(u2, lunes, cedidos_dias=[4, 6], aceptados_dias=[1, 3], franja_noche=noche)

    assert buscar_matches_para(j1) == []
    assert buscar_matches_para(j2) == []
