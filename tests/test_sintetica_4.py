"""Tests de publicaciones sintéticas para ocasiones a 4 bandas (cadena parcial
de 3 bandas reales A→B→C con un hueco C→D→A, cerrado por una sintética "D")."""
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
    buscar_cadenas_parciales_4_para,
    crear_aviso_oportunidad_4,
    crear_cadena_4_desde_sintetica,
    crear_pub_sintetica,
)
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


def _setup_cadena_parcial(db):
    """
    Ana→Pedro→María cierran 2 eslabones (A→B, B→C) pero María no cede nada
    que Ana acepte: el ciclo de 3 no se cierra, hace falta un cuarto (Luis).
      - Ana cede mañana_1  (Pedro acepta)
      - Pedro cede tarde_2 (María acepta)
      - María cede noche_3, pero Ana no lo acepta (Ana acepta noche_4, que nadie cede aún)
    """
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    maria = _usuario("María", "maria@test.es")

    gid = ana.unidad.grupo_intercambio_id
    fr_m = _franja(gid, "Mañana")
    fr_t = _franja(gid, "Tarde")
    fr_n = _franja(gid, "Noche")

    pub_ana = _pub_cambio(ana, [(date(2026, 7, 1), fr_m)], [(date(2026, 7, 4), fr_n)])
    pub_pedro = _pub_cambio(pedro, [(date(2026, 7, 2), fr_t)], [(date(2026, 7, 1), fr_m)])
    pub_maria = _pub_cambio(maria, [(date(2026, 7, 3), fr_n)], [(date(2026, 7, 2), fr_t)])

    return pub_ana, pub_pedro, pub_maria, ana, pedro, maria


# ---------------------------------------------------------------------------
# buscar_cadenas_parciales_4_para
# ---------------------------------------------------------------------------

def test_detecta_cadena_parcial_de_4(db):
    """El servicio detecta el trío Ana→Pedro→María como base de una cadena a 4."""
    pub_ana, pub_pedro, pub_maria, *_ = _setup_cadena_parcial(db)

    parciales = buscar_cadenas_parciales_4_para(pub_ana)

    assert len(parciales) == 1
    a, b, c = parciales[0]
    assert (a.id, b.id, c.id) == (pub_ana.id, pub_pedro.id, pub_maria.id)


def test_detecta_cadena_parcial_de_4_consultando_desde_el_intermedio(db):
    """
    Un camino abierto A→B→C no tiene simetría rotacional (a diferencia de un
    ciclo cerrado): hay que encontrar el trío igual si quien publica/edita el
    último es la banda intermedia (Pedro), no solo la primera (Ana).
    """
    pub_ana, pub_pedro, pub_maria, *_ = _setup_cadena_parcial(db)

    parciales = buscar_cadenas_parciales_4_para(pub_pedro)

    assert len(parciales) == 1
    a, b, c = parciales[0]
    assert (a.id, b.id, c.id) == (pub_ana.id, pub_pedro.id, pub_maria.id)


def test_detecta_cadena_parcial_de_4_consultando_desde_el_final(db):
    """Igual que arriba, pero consultando desde la última banda del camino (María)."""
    pub_ana, pub_pedro, pub_maria, *_ = _setup_cadena_parcial(db)

    parciales = buscar_cadenas_parciales_4_para(pub_maria)

    assert len(parciales) == 1
    a, b, c = parciales[0]
    assert (a.id, b.id, c.id) == (pub_ana.id, pub_pedro.id, pub_maria.id)


def test_no_detecta_parcial_si_el_ciclo_de_3_ya_cierra(db):
    """Si María→Ana ya cierra el ciclo (cadena_3 completa), no es una parcial de 4."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    maria = _usuario("María", "maria@test.es")

    gid = ana.unidad.grupo_intercambio_id
    fr_m = _franja(gid, "Mañana")
    fr_t = _franja(gid, "Tarde")
    fr_n = _franja(gid, "Noche")

    pub_ana = _pub_cambio(ana, [(date(2026, 7, 1), fr_m)], [(date(2026, 7, 3), fr_n)])
    _pub_cambio(pedro, [(date(2026, 7, 2), fr_t)], [(date(2026, 7, 1), fr_m)])
    _pub_cambio(maria, [(date(2026, 7, 3), fr_n)], [(date(2026, 7, 2), fr_t)])

    assert buscar_cadenas_parciales_4_para(pub_ana) == []


def test_parcial_4_respeta_filtro_de_categoria(db):
    insertar_categorias_semilla()
    cat_enf = Categoria.query.filter_by(nombre="Enfermería").first()
    cat_aux = Categoria.query.filter_by(nombre="Auxiliar de enfermería (TCAE)").first()

    ana = registrar_usuario("Ana", "ana@test.es", "password123", "H1", "Urgencias", cat_enf.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "H1", "Urgencias", cat_enf.id)
    maria = registrar_usuario("María", "maria@test.es", "password123", "H1", "Urgencias", cat_aux.id)

    gid = ana.unidad.grupo_intercambio_id
    fr_m = _franja(gid, "Mañana")
    fr_t = _franja(gid, "Tarde")
    fr_n = _franja(gid, "Noche")

    pub_ana = _pub_cambio(ana, [(date(2026, 7, 1), fr_m)], [(date(2026, 7, 4), fr_n)])
    _pub_cambio(pedro, [(date(2026, 7, 2), fr_t)], [(date(2026, 7, 1), fr_m)])
    _pub_cambio(maria, [(date(2026, 7, 3), fr_n)], [(date(2026, 7, 2), fr_t)])

    assert buscar_cadenas_parciales_4_para(pub_ana) == []


def test_parcial_4_solo_tipo_cambio(db):
    ana = _usuario("Ana", "ana@test.es")
    gid = ana.unidad.grupo_intercambio_id
    fr_m = _franja(gid, "Mañana")
    fr_t = _franja(gid, "Tarde")

    pub_junte = PublicacionCambio(usuario_id=ana.id, tipo="junte")
    db.session.add(pub_junte)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub_junte.id, fecha=date(2026, 7, 1), franja_horaria_id=fr_m.id))
    db.session.add(TurnoAceptado(publicacion_id=pub_junte.id, fecha=date(2026, 7, 2), franja_horaria_id=fr_t.id))
    db.session.commit()

    assert buscar_cadenas_parciales_4_para(pub_junte) == []


# ---------------------------------------------------------------------------
# crear_pub_sintetica con pub_intermedio (bridge de cadena_4)
# ---------------------------------------------------------------------------

def test_crea_pub_sintetica_con_intermedio(db):
    """
    La sintética de cadena_4 bridgea el último real (María=C) con el primero
    (Ana=A), recordando al intermedio (Pedro=B) para reconstruir el ciclo.
    """
    pub_ana, pub_pedro, pub_maria, *_ = _setup_cadena_parcial(db)

    sint = crear_pub_sintetica(pub_ana, pub_maria, pub_intermedio=pub_pedro)

    assert sint is not None
    assert sint.es_sintetica is True
    assert sint.sintetica_pub_a_id == pub_ana.id
    assert sint.sintetica_pub_b_id == pub_maria.id
    assert sint.sintetica_pub_intermedio_id == pub_pedro.id


def test_sintetica_cadena_3_no_tiene_intermedio(db):
    """Las sintéticas normales (cadena_3, sin pub_intermedio) quedan con el campo NULL."""
    pub_ana, pub_pedro, pub_maria, *_ = _setup_cadena_parcial(db)

    sint = crear_pub_sintetica(pub_ana, pub_pedro)

    assert sint.sintetica_pub_intermedio_id is None


def test_idempotente_con_intermedio(db):
    """Llamar dos veces con el mismo trío (A, C, intermedio=B) no duplica."""
    pub_ana, pub_pedro, pub_maria, *_ = _setup_cadena_parcial(db)

    s1 = crear_pub_sintetica(pub_ana, pub_maria, pub_intermedio=pub_pedro)
    s2 = crear_pub_sintetica(pub_ana, pub_maria, pub_intermedio=pub_pedro)

    assert s1.id == s2.id


def test_sintetica_cadena_3_y_cadena_4_no_se_confunden_para_el_mismo_par(db):
    """
    Una sintética cadena_3 (A,C sin intermedio) y una cadena_4 (A,C con
    intermedio=B) para el mismo par A,C son filas distintas.
    """
    pub_ana, pub_pedro, pub_maria, *_ = _setup_cadena_parcial(db)

    sint_3 = crear_pub_sintetica(pub_ana, pub_maria)
    sint_4 = crear_pub_sintetica(pub_ana, pub_maria, pub_intermedio=pub_pedro)

    assert sint_3.id != sint_4.id


# ---------------------------------------------------------------------------
# crear_aviso_oportunidad_4
# ---------------------------------------------------------------------------

def test_crea_aviso_oportunidad_4_para_los_tres(db):
    pub_ana, pub_pedro, pub_maria, ana, pedro, maria = _setup_cadena_parcial(db)

    crear_aviso_oportunidad_4(pub_ana, pub_pedro, pub_maria)

    notifs = Notificacion.query.filter_by(tipo="aviso_oportunidad_4").all()
    usuarios = {n.usuario_id for n in notifs}
    assert usuarios == {ana.id, pedro.id, maria.id}


def test_aviso_oportunidad_4_es_idempotente(db):
    pub_ana, pub_pedro, pub_maria, ana, pedro, maria = _setup_cadena_parcial(db)

    crear_aviso_oportunidad_4(pub_ana, pub_pedro, pub_maria)
    crear_aviso_oportunidad_4(pub_ana, pub_pedro, pub_maria)

    assert Notificacion.query.filter_by(
        tipo="aviso_oportunidad_4", usuario_id=ana.id
    ).count() == 1


# ---------------------------------------------------------------------------
# crear_cadena_4_desde_sintetica
# ---------------------------------------------------------------------------

def test_crea_match_cadena_4_entre_a_b_c_d(db):
    pub_ana, pub_pedro, pub_maria, ana, pedro, maria = _setup_cadena_parcial(db)
    sint = crear_pub_sintetica(pub_ana, pub_maria, pub_intermedio=pub_pedro)

    luis = _usuario("Luis", "luis@test.es")
    # La sintética ya tiene los turnos en el sentido correcto para el cuarto
    # usuario (D): los copia directamente, sin invertir (igual que hace
    # me_interesa con pub_a.es_sintetica para cadena_3).
    pub_luis = _pub_cambio(
        luis,
        [(t.fecha, t.franja_horaria) for t in sint.turnos_cedidos],
        [(t.fecha, t.franja_horaria) for t in sint.turnos_aceptados],
    )

    match = crear_cadena_4_desde_sintetica(pub_luis, sint)

    assert match is not None
    assert match.tipo == "cadena_4"
    pub_ids = {p.publicacion_id for p in match.participaciones}
    assert pub_ids == {pub_ana.id, pub_pedro.id, pub_maria.id, pub_luis.id}


def test_sintetica_se_cancela_tras_cadena_4(db):
    pub_ana, pub_pedro, pub_maria, ana, pedro, maria = _setup_cadena_parcial(db)
    sint = crear_pub_sintetica(pub_ana, pub_maria, pub_intermedio=pub_pedro)

    luis = _usuario("Luis", "luis@test.es")
    pub_luis = _pub_cambio(
        luis,
        [(t.fecha, t.franja_horaria) for t in sint.turnos_cedidos],
        [(t.fecha, t.franja_horaria) for t in sint.turnos_aceptados],
    )

    crear_cadena_4_desde_sintetica(pub_luis, sint)

    db.session.refresh(sint)
    assert sint.estado == "cancelada"
