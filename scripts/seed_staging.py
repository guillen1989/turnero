#!/usr/bin/env python
"""
Seed de datos para staging.

Uso:
    railway run python scripts/seed_staging.py
    railway run python scripts/seed_staging.py --reset

Crea 10 usuarios y 5 publicaciones de cada tipo (cambio, regalo, petición,
junte, cambio_dia), con matches en distintos estados. Todas las fechas de
turno son posteriores al 1 de septiembre de 2026.

Contraseña de todos: Staging2026!
"""
import os
import sys
from datetime import date, datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from sqlalchemy import text
from app.models import (
    insertar_categorias_semilla,
    Categoria, Usuario,
    PublicacionCambio, TurnoCedido, TurnoAceptado,
    MatchCambio, MatchParticipacion,
    FranjaHoraria, Notificacion,
)
from app.services.registro import (
    encontrar_o_crear_pais,
    encontrar_o_crear_provincia,
    encontrar_o_crear_ciudad,
    encontrar_o_crear_hospital,
    encontrar_o_crear_unidad,
)

_SEED_MARKER = "staging.admin@cambiaturnos.test"
_PASSWORD    = "Staging2026!"

_TODAS_LAS_TABLAS = (
    "event, busqueda_guardada, suscripcion_publicaciones, feedback, "
    "notificacion, match_participacion, match_cambio, "
    "turno_cedido, turno_aceptado, publicacion_cambio, "
    "usuario, franja_horaria, unidad, grupo_intercambio, "
    "hospital, categoria, ciudad, provincia, pais"
)


# ─── helpers ────────────────────────────────────────────────────────────────

def _ya_sembrado():
    return bool(Usuario.query.filter_by(email=_SEED_MARKER).first())


def _truncar():
    db.session.execute(text(f"TRUNCATE {_TODAS_LAS_TABLAS} RESTART IDENTITY CASCADE"))
    db.session.commit()
    print("Tablas vaciadas.")


def _usuario(nombre, email, unidad, categoria, es_admin=False):
    u = Usuario(
        nombre=nombre, email=email,
        unidad=unidad, categoria=categoria,
        es_admin=es_admin, onboarding_visto=True,
    )
    u.set_password(_PASSWORD)
    db.session.add(u)
    return u


def _pub(usuario, tipo, estado="abierta", mensaje=None, created_at=None):
    p = PublicacionCambio(
        usuario=usuario, tipo=tipo, estado=estado, mensaje=mensaje,
        fecha_creacion=created_at or datetime.now(timezone.utc),
    )
    db.session.add(p)
    return p


def _tc(pub, fecha, franja, estado="abierto"):
    t = TurnoCedido(publicacion=pub, fecha=fecha, franja_horaria=franja, estado=estado)
    db.session.add(t)
    return t


def _ta(pub, fecha, franja=None, cualquier_franja=False, estado="abierto"):
    t = TurnoAceptado(
        publicacion=pub, fecha=fecha,
        franja_horaria=franja, cualquier_franja=cualquier_franja,
        estado=estado,
    )
    db.session.add(t)
    return t


def _match(tipo="directo_2", estado="propuesto", created_at=None):
    m = MatchCambio(
        tipo=tipo, estado=estado,
        fecha_creacion=created_at or datetime.now(timezone.utc),
    )
    db.session.add(m)
    return m


def _part(match, pub, tc=None, ta=None, confirmado=False, confirmed_at=None):
    p = MatchParticipacion(
        match=match, publicacion=pub,
        turno_cedido=tc, turno_aceptado=ta,
        confirmado=confirmado,
        fecha_confirmacion=confirmed_at if confirmado else None,
    )
    db.session.add(p)
    return p


def _franja(grupo, nombre):
    return FranjaHoraria.query.filter_by(
        grupo_intercambio_id=grupo.id, nombre=nombre
    ).first()


def _dt(day_offset=0):
    """Datetime de creación escalonado a partir del 1-sep-2026."""
    base = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)
    return base + timedelta(days=day_offset, hours=day_offset % 8)


# ─── seed principal ──────────────────────────────────────────────────────────

def sembrar():
    # 1. Categorías
    insertar_categorias_semilla()
    db.session.flush()
    cat_enf  = Categoria.query.filter_by(nombre="Enfermería").first()
    cat_tcae = Categoria.query.filter_by(nombre="Auxiliar de enfermería (TCAE)").first()
    cat_med  = Categoria.query.filter_by(nombre="Medicina").first()
    if not cat_med:
        cat_med = Categoria(nombre="Medicina")
        db.session.add(cat_med)
    cat_admin_cat = Categoria.query.filter_by(nombre="Administrador").first()
    if not cat_admin_cat:
        cat_admin_cat = Categoria(nombre="Administrador")
        db.session.add(cat_admin_cat)
    db.session.flush()

    # 2. Geografía
    pais      = encontrar_o_crear_pais("España")
    provincia = encontrar_o_crear_provincia("Madrid", pais)
    ciudad    = encontrar_o_crear_ciudad("Madrid", provincia)

    # 3. Hospitales
    lapaz  = encontrar_o_crear_hospital("Hospital Universitario La Paz", ciudad)
    doce   = encontrar_o_crear_hospital("Hospital 12 de Octubre", ciudad)
    grego  = encontrar_o_crear_hospital("Hospital Universitario Gregorio Marañón", ciudad)
    hosp_sys = encontrar_o_crear_hospital("Sistema")

    # 4. Unidades (cada una genera su propio GrupoIntercambio)
    uco_enf,     _ = encontrar_o_crear_unidad("UCO",         lapaz,  cat_enf)
    urg_enf,     _ = encontrar_o_crear_unidad("Urgencias",   lapaz,  cat_enf)
    cardio_enf,  _ = encontrar_o_crear_unidad("Cardiología", doce,   cat_enf)
    uco_tcae,    _ = encontrar_o_crear_unidad("UCO",         lapaz,  cat_tcae)
    ped_enf,     _ = encontrar_o_crear_unidad("Pediatría",   grego,  cat_enf)
    unid_admin,  _ = encontrar_o_crear_unidad("Administración", hosp_sys)
    db.session.flush()

    # Franjas del grupo principal (UCO · Enfermería · La Paz)
    g_uco = uco_enf.grupo_intercambio
    man   = _franja(g_uco, "Mañana")
    tar   = _franja(g_uco, "Tarde")
    noch  = _franja(g_uco, "Noche")
    d12   = _franja(g_uco, "Diurno 12h")
    n12   = _franja(g_uco, "Nocturno 12h")

    g_urg    = urg_enf.grupo_intercambio
    g_cardio = cardio_enf.grupo_intercambio

    # ── Franjas de urgencias y cardiología ──────────────────────────────
    u_man  = _franja(g_urg,    "Mañana")
    u_tar  = _franja(g_urg,    "Tarde")
    c_man  = _franja(g_cardio, "Mañana")
    c_tar  = _franja(g_cardio, "Tarde")

    # 5. Usuarios (10 + 1 admin)
    admin   = _usuario("Admin Staging",  _SEED_MARKER,          unid_admin,  cat_admin_cat, es_admin=True)
    ana     = _usuario("Ana García",     "ana.garcia@test.es",   uco_enf,     cat_enf)
    bruno   = _usuario("Bruno López",    "bruno.lopez@test.es",  uco_enf,     cat_enf)
    carlos  = _usuario("Carlos Ruiz",    "carlos.ruiz@test.es",  uco_enf,     cat_enf)
    diana   = _usuario("Diana Martín",   "diana.martin@test.es", uco_enf,     cat_enf)
    elena   = _usuario("Elena Sanz",     "elena.sanz@test.es",   uco_enf,     cat_enf)
    fran    = _usuario("Fran Molina",    "fran.molina@test.es",  urg_enf,     cat_enf)
    gloria  = _usuario("Gloria Pardo",   "gloria.pardo@test.es", urg_enf,     cat_enf)
    hector  = _usuario("Héctor Vega",    "hector.vega@test.es",  cardio_enf,  cat_enf)
    irene   = _usuario("Irene Blanco",   "irene.blanco@test.es", uco_enf,     cat_enf)
    javier  = _usuario("Javier Mora",    "javier.mora@test.es",  uco_tcae,    cat_tcae)
    db.session.flush()

    # ════════════════════════════════════════════════════════════════════
    # 6. PUBLICACIONES ABIERTAS — 5 por tipo
    # ════════════════════════════════════════════════════════════════════

    # ── CAMBIO (5) ──────────────────────────────────────────────────────
    pub_c1 = _pub(ana,    "cambio", mensaje="Necesito la tarde del 12-sep",    created_at=_dt(0))
    _tc(pub_c1, date(2026, 9,  5), man)
    _ta(pub_c1, date(2026, 9, 12), tar)

    pub_c2 = _pub(bruno,  "cambio", mensaje="Cambio mi noche del 18 por tarde", created_at=_dt(1))
    _tc(pub_c2, date(2026, 9, 18), noch)
    _ta(pub_c2, date(2026, 9, 22), tar)

    pub_c3 = _pub(carlos, "cambio", created_at=_dt(2))
    _tc(pub_c3, date(2026, 9, 25), tar)
    _ta(pub_c3, date(2026, 9, 28), man)

    pub_c4 = _pub(diana,  "cambio", mensaje="Prefiero mañanas esa semana", created_at=_dt(3))
    _tc(pub_c4, date(2026, 10,  2), tard := tar)
    _ta(pub_c4, date(2026, 10,  5), man)

    pub_c5 = _pub(elena,  "cambio", created_at=_dt(4))
    _tc(pub_c5, date(2026, 10, 10), man)
    _ta(pub_c5, date(2026, 10, 15), d12)

    # ── REGALO (5) ──────────────────────────────────────────────────────
    pub_r1 = _pub(ana,    "regalo", mensaje="Regalo tarde, me cubre una compañera", created_at=_dt(5))
    _tc(pub_r1, date(2026, 9,  8), tar)

    pub_r2 = _pub(bruno,  "regalo", created_at=_dt(6))
    _tc(pub_r2, date(2026, 9, 15), man)

    pub_r3 = _pub(carlos, "regalo", mensaje="Regalo nocturno del 20", created_at=_dt(7))
    _tc(pub_r3, date(2026, 9, 20), n12)

    pub_r4 = _pub(diana,  "regalo", created_at=_dt(8))
    _tc(pub_r4, date(2026, 10,  1), d12)

    pub_r5 = _pub(elena,  "regalo", mensaje="Solo necesito librar ese día", created_at=_dt(9))
    _tc(pub_r5, date(2026, 10, 12), noch)

    # ── PETICIÓN (5) ────────────────────────────────────────────────────
    pub_p1 = _pub(ana,    "peticion", mensaje="Necesito librar esa mañana", created_at=_dt(10))
    _ta(pub_p1, date(2026, 9,  6), man)

    pub_p2 = _pub(bruno,  "peticion", created_at=_dt(11))
    _ta(pub_p2, date(2026, 9, 14), tar)

    pub_p3 = _pub(carlos, "peticion", created_at=_dt(12))
    _ta(pub_p3, date(2026, 9, 23), noch)

    pub_p4 = _pub(diana,  "peticion", mensaje="Cita médica esa mañana", created_at=_dt(13))
    _ta(pub_p4, date(2026, 10,  7), man)

    pub_p5 = _pub(elena,  "peticion", created_at=_dt(14))
    _ta(pub_p5, date(2026, 10, 18), d12)

    # ── JUNTE (5) ───────────────────────────────────────────────────────
    pub_j1 = _pub(ana,    "junte", mensaje="Juntes de la semana del 8-sep", created_at=_dt(15))
    _tc(pub_j1, date(2026, 9,  8), noch)
    _ta(pub_j1, date(2026, 9, 15), noch)

    pub_j2 = _pub(bruno,  "junte", created_at=_dt(16))
    _tc(pub_j2, date(2026, 9, 22), noch)
    _ta(pub_j2, date(2026, 9, 29), noch)

    pub_j3 = _pub(carlos, "junte", created_at=_dt(17))
    _tc(pub_j3, date(2026, 10,  5), noch)
    _ta(pub_j3, date(2026, 10, 12), noch)

    pub_j4 = _pub(diana,  "junte", mensaje="Semana de guardia del puente", created_at=_dt(18))
    _tc(pub_j4, date(2026, 10, 12), noch)
    _ta(pub_j4, date(2026, 10, 19), noch)

    pub_j5 = _pub(elena,  "junte", created_at=_dt(19))
    _tc(pub_j5, date(2026, 10, 26), noch)
    _ta(pub_j5, date(2026, 11,  2), noch)

    # ── CAMBIO_DIA (5) ──────────────────────────────────────────────────
    pub_cd1 = _pub(ana,    "cambio_dia", created_at=_dt(20))
    _tc(pub_cd1, date(2026, 9,  4), d12)
    _ta(pub_cd1, date(2026, 9, 11), cualquier_franja=True)

    pub_cd2 = _pub(bruno,  "cambio_dia", mensaje="Cualquier turno me vale", created_at=_dt(21))
    _tc(pub_cd2, date(2026, 9, 17), n12)
    _ta(pub_cd2, date(2026, 9, 24), cualquier_franja=True)

    pub_cd3 = _pub(carlos, "cambio_dia", created_at=_dt(22))
    _tc(pub_cd3, date(2026, 10,  1), man)
    _ta(pub_cd3, date(2026, 10,  8), cualquier_franja=True)

    pub_cd4 = _pub(diana,  "cambio_dia", created_at=_dt(23))
    _tc(pub_cd4, date(2026, 10, 14), tar)
    _ta(pub_cd4, date(2026, 10, 21), cualquier_franja=True)

    pub_cd5 = _pub(elena,  "cambio_dia", created_at=_dt(24))
    _tc(pub_cd5, date(2026, 11,  3), d12)
    _ta(pub_cd5, date(2026, 11, 10), cualquier_franja=True)

    db.session.flush()

    # ════════════════════════════════════════════════════════════════════
    # 7. MATCHES EN DISTINTOS ESTADOS (turnos del grupo UCO · ENF · La Paz)
    # ════════════════════════════════════════════════════════════════════

    match_base = _dt(5)   # fechas de publicaciones asociadas a matches

    # ── Match propuesto: Ana ↔ Bruno ────────────────────────────────────
    m1_pub_a = _pub(ana,   "cambio", created_at=match_base)
    m1_tc_a  = _tc(m1_pub_a, date(2026, 9, 10), man)
    m1_ta_a  = _ta(m1_pub_a, date(2026, 9, 11), tar)
    m1_pub_b = _pub(bruno, "cambio", created_at=match_base)
    m1_tc_b  = _tc(m1_pub_b, date(2026, 9, 11), tar)
    m1_ta_b  = _ta(m1_pub_b, date(2026, 9, 10), man)
    db.session.flush()
    m1 = _match(estado="propuesto", created_at=_dt(6))
    db.session.flush()
    _part(m1, m1_pub_a, tc=m1_tc_a, ta=m1_ta_a)
    _part(m1, m1_pub_b, tc=m1_tc_b, ta=m1_ta_b)

    # ── Match propuesto: Carlos ↔ Diana ─────────────────────────────────
    m2_pub_a = _pub(carlos, "cambio", created_at=_dt(7))
    m2_tc_a  = _tc(m2_pub_a, date(2026, 9, 16), noch)
    m2_ta_a  = _ta(m2_pub_a, date(2026, 9, 17), man)
    m2_pub_b = _pub(diana,  "cambio", created_at=_dt(7))
    m2_tc_b  = _tc(m2_pub_b, date(2026, 9, 17), man)
    m2_ta_b  = _ta(m2_pub_b, date(2026, 9, 16), noch)
    db.session.flush()
    m2 = _match(estado="propuesto", created_at=_dt(8))
    db.session.flush()
    _part(m2, m2_pub_a, tc=m2_tc_a, ta=m2_ta_a)
    _part(m2, m2_pub_b, tc=m2_tc_b, ta=m2_ta_b)

    # ── Match confirmado_parcial: Elena confirmó, Irene pendiente ───────
    confirmed_p = datetime(2026, 9, 20, 10, 30, tzinfo=timezone.utc)
    m3_pub_a = _pub(elena, "cambio", created_at=_dt(10))
    m3_tc_a  = _tc(m3_pub_a, date(2026, 9, 24), man)
    m3_ta_a  = _ta(m3_pub_a, date(2026, 9, 25), tar)
    m3_pub_b = _pub(irene, "cambio", created_at=_dt(10))
    m3_tc_b  = _tc(m3_pub_b, date(2026, 9, 25), tar)
    m3_ta_b  = _ta(m3_pub_b, date(2026, 9, 24), man)
    db.session.flush()
    m3 = _match(estado="confirmado_parcial", created_at=_dt(11))
    db.session.flush()
    _part(m3, m3_pub_a, tc=m3_tc_a, ta=m3_ta_a, confirmado=True,  confirmed_at=confirmed_p)
    _part(m3, m3_pub_b, tc=m3_tc_b, ta=m3_ta_b, confirmado=False)

    # ── Match confirmado_parcial: Bruno confirmó, Carlos pendiente ───────
    m4_pub_a = _pub(bruno,  "cambio", created_at=_dt(12))
    m4_tc_a  = _tc(m4_pub_a, date(2026, 10,  2), tar)
    m4_ta_a  = _ta(m4_pub_a, date(2026, 10,  3), man)
    m4_pub_b = _pub(carlos, "cambio", created_at=_dt(12))
    m4_tc_b  = _tc(m4_pub_b, date(2026, 10,  3), man)
    m4_ta_b  = _ta(m4_pub_b, date(2026, 10,  2), tar)
    db.session.flush()
    m4 = _match(estado="confirmado_parcial", created_at=_dt(13))
    db.session.flush()
    _part(m4, m4_pub_a, tc=m4_tc_a, ta=m4_ta_a, confirmado=True,
          confirmed_at=datetime(2026, 10, 1, 15, 0, tzinfo=timezone.utc))
    _part(m4, m4_pub_b, tc=m4_tc_b, ta=m4_ta_b, confirmado=False)

    # ── Match confirmado_total: Ana ↔ Bruno ──────────────────────────────
    conf_total_dt = datetime(2026, 9, 15, 11, 0, tzinfo=timezone.utc)
    m5_pub_a = _pub(ana,   "cambio", estado="confirmada", created_at=_dt(8))
    m5_tc_a  = _tc(m5_pub_a, date(2026, 9, 18), man, estado="resuelto")
    m5_ta_a  = _ta(m5_pub_a, date(2026, 9, 19), tar, estado="resuelto")
    m5_pub_b = _pub(bruno, "cambio", estado="confirmada", created_at=_dt(8))
    m5_tc_b  = _tc(m5_pub_b, date(2026, 9, 19), tar, estado="resuelto")
    m5_ta_b  = _ta(m5_pub_b, date(2026, 9, 18), man, estado="resuelto")
    db.session.flush()
    m5 = _match(estado="confirmado_total", created_at=_dt(9))
    m5.fecha_confirmacion_total = conf_total_dt
    db.session.flush()
    _part(m5, m5_pub_a, tc=m5_tc_a, ta=m5_ta_a, confirmado=True, confirmed_at=conf_total_dt - timedelta(hours=2))
    _part(m5, m5_pub_b, tc=m5_tc_b, ta=m5_ta_b, confirmado=True, confirmed_at=conf_total_dt)

    # ── Match confirmado_total: Carlos ↔ Diana ───────────────────────────
    conf_total_dt2 = datetime(2026, 9, 28, 9, 45, tzinfo=timezone.utc)
    m6_pub_a = _pub(carlos, "cambio", estado="confirmada", created_at=_dt(14))
    m6_tc_a  = _tc(m6_pub_a, date(2026, 10, 5), noch, estado="resuelto")
    m6_ta_a  = _ta(m6_pub_a, date(2026, 10, 6), man,  estado="resuelto")
    m6_pub_b = _pub(diana,  "cambio", estado="confirmada", created_at=_dt(14))
    m6_tc_b  = _tc(m6_pub_b, date(2026, 10, 6), man,  estado="resuelto")
    m6_ta_b  = _ta(m6_pub_b, date(2026, 10, 5), noch, estado="resuelto")
    db.session.flush()
    m6 = _match(estado="confirmado_total", created_at=_dt(15))
    m6.fecha_confirmacion_total = conf_total_dt2
    db.session.flush()
    _part(m6, m6_pub_a, tc=m6_tc_a, ta=m6_ta_a, confirmado=True, confirmed_at=conf_total_dt2 - timedelta(hours=3))
    _part(m6, m6_pub_b, tc=m6_tc_b, ta=m6_ta_b, confirmado=True, confirmed_at=conf_total_dt2)

    # ── Match confirmado_total: Elena ↔ Irene ────────────────────────────
    conf_total_dt3 = datetime(2026, 10, 10, 14, 20, tzinfo=timezone.utc)
    m7_pub_a = _pub(elena, "cambio", estado="confirmada", created_at=_dt(16))
    m7_tc_a  = _tc(m7_pub_a, date(2026, 10, 14), d12, estado="resuelto")
    m7_ta_a  = _ta(m7_pub_a, date(2026, 10, 15), tar, estado="resuelto")
    m7_pub_b = _pub(irene, "cambio", estado="confirmada", created_at=_dt(16))
    m7_tc_b  = _tc(m7_pub_b, date(2026, 10, 15), tar, estado="resuelto")
    m7_ta_b  = _ta(m7_pub_b, date(2026, 10, 14), d12, estado="resuelto")
    db.session.flush()
    m7 = _match(estado="confirmado_total", created_at=_dt(17))
    m7.fecha_confirmacion_total = conf_total_dt3
    db.session.flush()
    _part(m7, m7_pub_a, tc=m7_tc_a, ta=m7_ta_a, confirmado=True, confirmed_at=conf_total_dt3 - timedelta(hours=1))
    _part(m7, m7_pub_b, tc=m7_tc_b, ta=m7_ta_b, confirmado=True, confirmed_at=conf_total_dt3)

    # ── Parcialmente resuelta: Ana tiene 2 turnos cedidos, 1 resuelto ───
    m8_pub_a = _pub(ana,   "cambio", estado="parcialmente_resuelta", created_at=_dt(18))
    m8_tc_a1 = _tc(m8_pub_a, date(2026, 10, 20), man, estado="resuelto")
    m8_tc_a2 = _tc(m8_pub_a, date(2026, 10, 27), man)   # sigue abierto
    m8_ta_a  = _ta(m8_pub_a, date(2026, 10, 21), tar, estado="resuelto")
    m8_pub_b = _pub(diana, "cambio", estado="confirmada", created_at=_dt(18))
    m8_tc_b  = _tc(m8_pub_b, date(2026, 10, 21), tar, estado="resuelto")
    m8_ta_b  = _ta(m8_pub_b, date(2026, 10, 20), man, estado="resuelto")
    db.session.flush()
    conf_par = datetime(2026, 10, 18, 16, 0, tzinfo=timezone.utc)
    m8 = _match(estado="confirmado_total", created_at=_dt(19))
    m8.fecha_confirmacion_total = conf_par
    db.session.flush()
    _part(m8, m8_pub_a, tc=m8_tc_a1, ta=m8_ta_a, confirmado=True, confirmed_at=conf_par - timedelta(hours=2))
    _part(m8, m8_pub_b, tc=m8_tc_b,  ta=m8_ta_b, confirmado=True, confirmed_at=conf_par)

    # ── Cadena_3 completa propuesta: Ana → Carlos → Bruno → Ana ─────────
    # Ana cede mañana 25-oct, quiere tarde 15-nov
    # Carlos cede mañana 20-sep, quiere mañana 25-oct  (lo que ofrece Ana)
    # Bruno cede tarde 15-nov,  quiere mañana 20-sep   (lo que ofrece Carlos)
    pub_3b_ana   = _pub(ana,   "cambio", created_at=_dt(25))
    tc_3b_ana    = _tc(pub_3b_ana,   date(2026, 10, 25), man)
    _ta(pub_3b_ana,   date(2026, 11, 15), tar)

    pub_3b_carlos = _pub(carlos, "cambio", created_at=_dt(25))
    tc_3b_carlos  = _tc(pub_3b_carlos, date(2026, 9,  20), man)
    _ta(pub_3b_carlos, date(2026, 10, 25), man)

    pub_3b_bruno = _pub(bruno, "cambio", created_at=_dt(25))
    tc_3b_bruno  = _tc(pub_3b_bruno, date(2026, 11, 15), tar)
    _ta(pub_3b_bruno, date(2026, 9,  20), man)

    db.session.flush()

    m_3b = _match(tipo="cadena_3", estado="propuesto", created_at=_dt(26))
    db.session.flush()
    _part(m_3b, pub_3b_ana,    tc=tc_3b_ana)
    _part(m_3b, pub_3b_carlos, tc=tc_3b_carlos)
    _part(m_3b, pub_3b_bruno,  tc=tc_3b_bruno)

    # ── Medio match + pub sintética: Ana(27-oct) ↔ Carlos, esperando C ──
    # Ana cede mañana 27-oct, quiere tarde 20-nov (abierto)
    # Carlos quiere mañana 27-oct, cede mañana 27-sep
    # Sintética (de Ana): CEDE tarde 20-nov, ACEPTA mañana 27-sep
    pub_mm_ana   = _pub(ana,   "cambio", created_at=_dt(27))
    _tc(pub_mm_ana,   date(2026, 10, 27), man)
    ta_mm_ana    = _ta(pub_mm_ana,   date(2026, 11, 20), tar)

    pub_mm_carlos = _pub(carlos, "cambio", created_at=_dt(27))
    tc_mm_carlos  = _tc(pub_mm_carlos, date(2026, 9,  27), man)
    _ta(pub_mm_carlos, date(2026, 10, 27), man)

    db.session.flush()

    pub_sint = PublicacionCambio(
        usuario=ana, tipo="cambio", es_sintetica=True,
        sintetica_pub_a_id=pub_mm_ana.id,
        sintetica_pub_b_id=pub_mm_carlos.id,
    )
    db.session.add(pub_sint)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion=pub_sint, fecha=ta_mm_ana.fecha, franja_horaria=tar))
    db.session.add(TurnoAceptado(publicacion=pub_sint, fecha=tc_mm_carlos.fecha, franja_horaria=man, cualquier_franja=False))
    db.session.add(Notificacion(usuario_id=ana.id,    publicacion_id=pub_mm_carlos.id, tipo="aviso_interes"))
    db.session.add(Notificacion(usuario_id=carlos.id, publicacion_id=pub_mm_ana.id,   tipo="aviso_interes"))

    # ── Canceladas (3) ───────────────────────────────────────────────────
    pub_can1 = _pub(fran,   "cambio",    estado="cancelada", created_at=_dt(20))
    _tc(pub_can1, date(2026, 9, 12), _franja(g_urg, "Mañana"))
    _ta(pub_can1, date(2026, 9, 13), _franja(g_urg, "Tarde"))

    pub_can2 = _pub(gloria, "regalo",    estado="cancelada", created_at=_dt(21))
    _tc(pub_can2, date(2026, 9, 20), _franja(g_urg, "Tarde"))

    pub_can3 = _pub(hector, "peticion",  estado="cancelada", created_at=_dt(22))
    _ta(pub_can3, date(2026, 9, 25), _franja(g_cardio, "Mañana"))

    # ── Caducadas (3) ────────────────────────────────────────────────────
    # fechas de turno pasadas para simular caducidad
    pub_cad1 = _pub(ana,    "cambio",   estado="caducada", created_at=_dt(1))
    _tc(pub_cad1, date(2026, 9,  2), man)
    _ta(pub_cad1, date(2026, 9,  3), tar)

    pub_cad2 = _pub(bruno,  "regalo",   estado="caducada", created_at=_dt(2))
    _tc(pub_cad2, date(2026, 9,  3), tar)

    pub_cad3 = _pub(carlos, "peticion", estado="caducada", created_at=_dt(3))
    _ta(pub_cad3, date(2026, 9,  4), man)

    db.session.commit()
    _imprimir_resumen()


def _imprimir_resumen():
    sep = "═" * 64
    print(f"\n{sep}")
    print("  SEED STAGING COMPLETADO")
    print(sep)
    print(f"\n  Contraseña de todos los usuarios: {_PASSWORD}\n")
    print("  USUARIOS (grupo principal: UCO · Enfermería · La Paz)")
    for email, nombre, desc in [
        (_SEED_MARKER,              "Admin Staging", "es_admin=True"),
        ("ana.garcia@test.es",      "Ana García",    "UCO · ENF · La Paz"),
        ("bruno.lopez@test.es",     "Bruno López",   "UCO · ENF · La Paz"),
        ("carlos.ruiz@test.es",     "Carlos Ruiz",   "UCO · ENF · La Paz"),
        ("diana.martin@test.es",    "Diana Martín",  "UCO · ENF · La Paz"),
        ("elena.sanz@test.es",      "Elena Sanz",    "UCO · ENF · La Paz"),
        ("irene.blanco@test.es",    "Irene Blanco",  "UCO · ENF · La Paz"),
        ("fran.molina@test.es",     "Fran Molina",   "Urgencias · ENF · La Paz"),
        ("gloria.pardo@test.es",    "Gloria Pardo",  "Urgencias · ENF · La Paz"),
        ("hector.vega@test.es",     "Héctor Vega",   "Cardiología · ENF · 12 Oct"),
        ("javier.mora@test.es",     "Javier Mora",   "UCO · TCAE · La Paz"),
    ]:
        print(f"    {email:<36} {nombre:<16} {desc}")
    print()
    print("  PUBLICACIONES ABIERTAS: 5 × cambio, 5 × regalo, 5 × petición, 5 × junte, 5 × cambio_dia")
    print()
    print("  MATCHES:")
    print("    2 propuestos      (Ana↔Bruno, Carlos↔Diana)")
    print("    2 confirmado_parcial  (Elena↔Irene, Bruno↔Carlos)")
    print("    3 confirmado_total    (Ana↔Bruno, Carlos↔Diana, Elena↔Irene)")
    print("    1 parcialmente_resuelta (Ana: turno-1 resuelto, turno-2 abierto)")
    print("    1 cadena_3 propuesta  Ana→Carlos→Bruno→Ana (oct-nov 2026)")
    print("    1 medio match + sintética  Ana(27-oct)↔Carlos, esperando C (nov 2026)")
    print("    3 canceladas      (Fran, Gloria, Héctor)")
    print("    3 caducadas       (Ana, Bruno, Carlos — fechas sep-2 a sep-4)")
    print(f"\n{sep}\n")


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    os.environ.pop("SENTRY_DSN", None)  # evita importar sentry_sdk si no está instalado localmente
    env   = os.environ.get("FLASK_ENV", "production")
    app   = create_app(env)
    with app.app_context():
        if not reset and _ya_sembrado():
            print(
                f"El seed ya está aplicado (marker: {_SEED_MARKER}).\n"
                "Usa --reset para truncar todo y recrear desde cero."
            )
            sys.exit(0)
        if reset:
            _truncar()
        sembrar()
