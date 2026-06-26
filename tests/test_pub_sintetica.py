"""Tests de publicaciones sintéticas (generador de cambios a 3 bandas)."""
from datetime import date

import pytest

from app.extensions import db
from app.models import (
    Categoria,
    FranjaHoraria,
    MatchCambio,
    Notificacion,
    PublicacionCambio,
    TurnoCedido,
    TurnoAceptado,
    insertar_categorias_semilla,
)
from app.matching.service import (
    buscar_avisos_interes_para,
    buscar_sinteticas_que_coinciden_con,
    crear_aviso_interes,
    crear_cadena_3_desde_sintetica,
    crear_pub_sintetica,
)
from app.services.publicaciones import cancelar_publicacion
from app.services.registro import registrar_usuario


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _usuario(nombre, email, password="password123"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario(nombre, email, password, "Hospital T", "Urgencias", cat.id)


def _franja(grupo_id, nombre="Mañana"):
    return FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id, nombre=nombre).first()


def _franja_tarde(grupo_id):
    return FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id, nombre="Tarde").first()


def _pub_cambio(usuario, cedidos, aceptados):
    """cedidos / aceptados: lista de (fecha, franja)."""
    pub = PublicacionCambio(usuario_id=usuario.id, tipo="cambio")
    db.session.add(pub)
    db.session.flush()
    for fecha, franja in cedidos:
        db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=fecha, franja_horaria_id=franja.id))
    for fecha, franja in aceptados:
        db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=fecha, franja_horaria_id=franja.id))
    db.session.commit()
    return pub


# ---------------------------------------------------------------------------
# crear_pub_sintetica
# ---------------------------------------------------------------------------

def test_crea_pub_con_cedidos_de_aceptados_a_y_acepta_cedido_b(db):
    """
    Regla: cedido_sintética = aceptados_A, acepta_sintética = cedidos_B.
    """
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    m = _franja(ana.unidad.grupo_intercambio_id, "Mañana")
    t = _franja_tarde(ana.unidad.grupo_intercambio_id)

    # Ana cede 10/07 M, acepta 03/08 T y 09/08 T
    pub_a = _pub_cambio(ana, [(date(2026, 7, 10), m)], [(date(2026, 8, 3), t), (date(2026, 8, 9), t)])
    # Pedro cede 21/07 M, acepta 10/07 M
    pub_b = _pub_cambio(pedro, [(date(2026, 7, 21), m)], [(date(2026, 7, 10), m)])

    sint = crear_pub_sintetica(pub_a, pub_b)

    assert sint is not None
    assert sint.es_sintetica is True
    assert sint.sintetica_pub_a_id == pub_a.id
    assert sint.sintetica_pub_b_id == pub_b.id
    assert sint.usuario_id == pub_a.usuario_id
    assert sint.tipo == "cambio"
    assert sint.estado == "abierta"

    fechas_cedidas = {(t.fecha, t.franja_horaria_id) for t in sint.turnos_cedidos}
    assert (date(2026, 8, 3), t.id) in fechas_cedidas
    assert (date(2026, 8, 9), t.id) in fechas_cedidas

    fechas_aceptadas = {(ta.fecha, ta.franja_horaria_id) for ta in sint.turnos_aceptados}
    assert (date(2026, 7, 21), m.id) in fechas_aceptadas


def test_idempotente_no_duplica(db):
    """Llamar crear_pub_sintetica dos veces para el mismo par no crea dos pubs."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    m = _franja(ana.unidad.grupo_intercambio_id)
    t = _franja_tarde(ana.unidad.grupo_intercambio_id)

    pub_a = _pub_cambio(ana, [(date(2026, 7, 10), m)], [(date(2026, 8, 3), t)])
    pub_b = _pub_cambio(pedro, [(date(2026, 7, 21), m)], [(date(2026, 7, 10), m)])

    s1 = crear_pub_sintetica(pub_a, pub_b)
    s2 = crear_pub_sintetica(pub_a, pub_b)

    assert s1.id == s2.id
    assert PublicacionCambio.query.filter_by(
        sintetica_pub_a_id=pub_a.id, sintetica_pub_b_id=pub_b.id
    ).count() == 1


def test_sintetica_no_aparece_en_candidatas_normales(db):
    """Una pub sintética no debe aparecer como candidata en búsquedas regulares."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    carlos = _usuario("Carlos", "carlos@test.es")
    m = _franja(ana.unidad.grupo_intercambio_id)
    t = _franja_tarde(ana.unidad.grupo_intercambio_id)

    pub_a = _pub_cambio(ana, [(date(2026, 7, 10), m)], [(date(2026, 8, 3), t)])
    pub_b = _pub_cambio(pedro, [(date(2026, 7, 21), m)], [(date(2026, 7, 10), m)])
    sint = crear_pub_sintetica(pub_a, pub_b)

    # Carlos publica algo que coincidiría con la sintética si se buscara
    pub_c = _pub_cambio(carlos, [(date(2026, 8, 3), t)], [(date(2026, 7, 21), m)])

    from app.matching.service import buscar_matches_para
    candidatas = buscar_matches_para(pub_c)
    assert sint not in candidatas


# ---------------------------------------------------------------------------
# buscar_sinteticas_que_coinciden_con
# ---------------------------------------------------------------------------

def test_encuentra_sintetica_cuando_coincide(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    carlos = _usuario("Carlos", "carlos@test.es")
    m = _franja(ana.unidad.grupo_intercambio_id)
    t = _franja_tarde(ana.unidad.grupo_intercambio_id)

    pub_a = _pub_cambio(ana, [(date(2026, 7, 10), m)], [(date(2026, 8, 3), t)])
    pub_b = _pub_cambio(pedro, [(date(2026, 7, 21), m)], [(date(2026, 7, 10), m)])
    sint = crear_pub_sintetica(pub_a, pub_b)

    # Carlos: cede 03/08 T, acepta 21/07 M → cierra el triángulo
    pub_c = _pub_cambio(carlos, [(date(2026, 8, 3), t)], [(date(2026, 7, 21), m)])

    resultado = buscar_sinteticas_que_coinciden_con(pub_c)
    assert sint in resultado


def test_no_encuentra_sintetica_si_no_coincide(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    carlos = _usuario("Carlos", "carlos@test.es")
    m = _franja(ana.unidad.grupo_intercambio_id)
    t = _franja_tarde(ana.unidad.grupo_intercambio_id)

    pub_a = _pub_cambio(ana, [(date(2026, 7, 10), m)], [(date(2026, 8, 3), t)])
    pub_b = _pub_cambio(pedro, [(date(2026, 7, 21), m)], [(date(2026, 7, 10), m)])
    crear_pub_sintetica(pub_a, pub_b)

    # Carlos no cuadra con la sintética
    pub_c = _pub_cambio(carlos, [(date(2026, 9, 1), m)], [(date(2026, 9, 5), t)])

    resultado = buscar_sinteticas_que_coinciden_con(pub_c)
    assert resultado == []


def test_sintetica_cancelada_no_aparece(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    carlos = _usuario("Carlos", "carlos@test.es")
    m = _franja(ana.unidad.grupo_intercambio_id)
    t = _franja_tarde(ana.unidad.grupo_intercambio_id)

    pub_a = _pub_cambio(ana, [(date(2026, 7, 10), m)], [(date(2026, 8, 3), t)])
    pub_b = _pub_cambio(pedro, [(date(2026, 7, 21), m)], [(date(2026, 7, 10), m)])
    sint = crear_pub_sintetica(pub_a, pub_b)
    sint.estado = "cancelada"
    db.session.commit()

    pub_c = _pub_cambio(carlos, [(date(2026, 8, 3), t)], [(date(2026, 7, 21), m)])
    assert buscar_sinteticas_que_coinciden_con(pub_c) == []


# ---------------------------------------------------------------------------
# crear_cadena_3_desde_sintetica
# ---------------------------------------------------------------------------

def test_crea_match_cadena_3_entre_a_b_c(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    carlos = _usuario("Carlos", "carlos@test.es")
    m = _franja(ana.unidad.grupo_intercambio_id)
    t = _franja_tarde(ana.unidad.grupo_intercambio_id)

    pub_a = _pub_cambio(ana, [(date(2026, 7, 10), m)], [(date(2026, 8, 3), t)])
    pub_b = _pub_cambio(pedro, [(date(2026, 7, 21), m)], [(date(2026, 7, 10), m)])
    sint = crear_pub_sintetica(pub_a, pub_b)
    pub_c = _pub_cambio(carlos, [(date(2026, 8, 3), t)], [(date(2026, 7, 21), m)])

    match = crear_cadena_3_desde_sintetica(pub_c, sint)

    assert match is not None
    assert match.tipo == "cadena_3"
    pub_ids = {p.publicacion_id for p in match.participaciones}
    assert pub_a.id in pub_ids
    assert pub_b.id in pub_ids
    assert pub_c.id in pub_ids


def test_sintetica_se_cancela_tras_cadena_3(db):
    """La pub sintética queda cancelada cuando el match a 3 se crea."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    carlos = _usuario("Carlos", "carlos@test.es")
    m = _franja(ana.unidad.grupo_intercambio_id)
    t = _franja_tarde(ana.unidad.grupo_intercambio_id)

    pub_a = _pub_cambio(ana, [(date(2026, 7, 10), m)], [(date(2026, 8, 3), t)])
    pub_b = _pub_cambio(pedro, [(date(2026, 7, 21), m)], [(date(2026, 7, 10), m)])
    sint = crear_pub_sintetica(pub_a, pub_b)
    pub_c = _pub_cambio(carlos, [(date(2026, 8, 3), t)], [(date(2026, 7, 21), m)])

    crear_cadena_3_desde_sintetica(pub_c, sint)

    db.session.refresh(sint)
    assert sint.estado == "cancelada"


# ---------------------------------------------------------------------------
# Ciclo de vida: cancelar pub fuente cancela la sintética
# ---------------------------------------------------------------------------

def test_cancelar_pub_a_cancela_sintetica(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    m = _franja(ana.unidad.grupo_intercambio_id)
    t = _franja_tarde(ana.unidad.grupo_intercambio_id)

    pub_a = _pub_cambio(ana, [(date(2026, 7, 10), m)], [(date(2026, 8, 3), t)])
    pub_b = _pub_cambio(pedro, [(date(2026, 7, 21), m)], [(date(2026, 7, 10), m)])
    sint = crear_pub_sintetica(pub_a, pub_b)

    cancelar_publicacion(pub_a)

    db.session.refresh(sint)
    assert sint.estado == "cancelada"


def test_cancelar_pub_b_cancela_sintetica(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    m = _franja(ana.unidad.grupo_intercambio_id)
    t = _franja_tarde(ana.unidad.grupo_intercambio_id)

    pub_a = _pub_cambio(ana, [(date(2026, 7, 10), m)], [(date(2026, 8, 3), t)])
    pub_b = _pub_cambio(pedro, [(date(2026, 7, 21), m)], [(date(2026, 7, 10), m)])
    sint = crear_pub_sintetica(pub_a, pub_b)

    cancelar_publicacion(pub_b)

    db.session.refresh(sint)
    assert sint.estado == "cancelada"


# ---------------------------------------------------------------------------
# Integración: publicar C dispara cadena_3 via sintética
# ---------------------------------------------------------------------------

def test_publicar_c_genera_cadena_3(client, db):
    """Al publicar C, si hay una sintética que coincide, se crea el match cadena_3."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    carlos = _usuario("Carlos", "carlos@test.es")
    m = _franja(ana.unidad.grupo_intercambio_id)
    t = _franja_tarde(ana.unidad.grupo_intercambio_id)

    pub_a = _pub_cambio(ana, [(date(2026, 7, 10), m)], [(date(2026, 8, 3), t)])
    pub_b = _pub_cambio(pedro, [(date(2026, 7, 21), m)], [(date(2026, 7, 10), m)])
    sint = crear_pub_sintetica(pub_a, pub_b)

    client.post("/auth/login", data={"email": "carlos@test.es", "password": "password123"})
    client.post("/publicar", data={
        "tipo": "cambio",
        "fecha_cedida_0": "2026-08-03",
        "franja_cedida_0": str(t.id),
        "fecha_aceptada_0": "2026-07-21",
        "franja_aceptada_0": str(m.id),
    })

    pub_c = PublicacionCambio.query.filter_by(usuario_id=carlos.id, es_sintetica=False).first()
    assert pub_c is not None

    match = MatchCambio.query.filter_by(tipo="cadena_3").first()
    assert match is not None

    pub_ids = {p.publicacion_id for p in match.participaciones}
    assert pub_a.id in pub_ids
    assert pub_b.id in pub_ids
    assert pub_c.id in pub_ids


# ---------------------------------------------------------------------------
# Notificaciones aviso_sintetica
# ---------------------------------------------------------------------------

def test_crear_sintetica_notifica_a_ambos_usuarios(db):
    """Al crear una pub sintética, ambos usuarios reciben aviso_sintetica."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    m = _franja(ana.unidad.grupo_intercambio_id)
    t = _franja_tarde(ana.unidad.grupo_intercambio_id)

    pub_a = _pub_cambio(ana, [(date(2026, 7, 10), m)], [(date(2026, 8, 3), t)])
    pub_b = _pub_cambio(pedro, [(date(2026, 7, 21), m)], [(date(2026, 7, 10), m)])

    crear_pub_sintetica(pub_a, pub_b)

    notif_ana = Notificacion.query.filter_by(
        usuario_id=ana.id, tipo="aviso_sintetica"
    ).first()
    notif_pedro = Notificacion.query.filter_by(
        usuario_id=pedro.id, tipo="aviso_sintetica"
    ).first()

    assert notif_ana is not None
    assert notif_pedro is not None
    # Cada notificación apunta a la publicación del otro
    assert notif_ana.publicacion_id == pub_b.id
    assert notif_pedro.publicacion_id == pub_a.id


def test_crear_sintetica_no_duplica_notificacion(db):
    """Llamar crear_pub_sintetica dos veces no duplica los avisos."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    m = _franja(ana.unidad.grupo_intercambio_id)
    t = _franja_tarde(ana.unidad.grupo_intercambio_id)

    pub_a = _pub_cambio(ana, [(date(2026, 7, 10), m)], [(date(2026, 8, 3), t)])
    pub_b = _pub_cambio(pedro, [(date(2026, 7, 21), m)], [(date(2026, 7, 10), m)])

    crear_pub_sintetica(pub_a, pub_b)
    crear_pub_sintetica(pub_a, pub_b)

    count_ana = Notificacion.query.filter_by(
        usuario_id=ana.id, tipo="aviso_sintetica"
    ).count()
    count_pedro = Notificacion.query.filter_by(
        usuario_id=pedro.id, tipo="aviso_sintetica"
    ).count()

    assert count_ana == 1
    assert count_pedro == 1
