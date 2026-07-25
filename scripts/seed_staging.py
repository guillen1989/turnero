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

Además, siempre (independientemente de si el seed base ya estaba aplicado)
amplía la unidad real UCO·Hospital Universitario La Paz·Enfermería: añade
23 cuentas sintéticas (contraseña: la de app.services.demo.DEMO_PASSWORD),
una supervisora (supervisora.uco@demo.turnero.com / supervisora), la rota
de julio-agosto-septiembre 2026 para todos sus usuarios (cobertura diaria
de las 5 franjas, descanso obligatorio tras Noche/Nocturno 12h, 2 días
libres/semana) y hojas de cambio (agosto-septiembre 2026) en sus 4 estados
posibles. Es aditivo e idempotente: nunca borra ni toca usuarios ya
existentes de esa unidad.
"""
import os
import sys
from datetime import date, datetime, timezone, timedelta

from flask import current_app

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from sqlalchemy import text
from app.models import (
    insertar_categorias_semilla,
    Categoria, Unidad, Usuario,
    PublicacionCambio, TurnoCedido, TurnoAceptado,
    MatchCambio, MatchParticipacion,
    FranjaHoraria, Notificacion,
    EstadoDiaPlanilla, PlanillaMes, SalienteDia, TurnoPlanilla,
    DocumentoCambio,
)
from app.services.registro import (
    encontrar_o_crear_pais,
    encontrar_o_crear_provincia,
    encontrar_o_crear_ciudad,
    encontrar_o_crear_hospital,
    encontrar_o_crear_unidad,
)
from app.services.demo import BOT_ACCOUNTS, DEMO_ACCOUNTS, sembrar_contenido_bot
from app.services.documento_cambio import (
    crear_documento_cambio, firmar_documento, autorizar_documento, denegar_documento,
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


# ─── generador de rota (planillas jul-sep) ──────────────────────────────────
#
# Cada trabajador recibe una plantilla semanal fija, indexada por (fase,
# variante_noche): `fase` (0=lunes..6=domingo) marca en qué día de la semana
# cae su turno nocturno, y `variante_noche` si ese turno es "Noche" o
# "Nocturno 12h". La plantilla, relativa a `fase`, es siempre:
#
#   fase+0: turno nocturno (variante_noche)
#   fase+1: libre (descanso obligatorio tras la noche)
#   fase+2: Mañana
#   fase+3: Tarde
#   fase+4: Diurno 12h
#   fase+5: libre (segundo libre de la semana)
#   fase+6: Tarde
#
# Con las 14 combinaciones (7 fases × 2 variantes) repartidas en round-robin,
# cada día de la semana recibe, de al menos una plantilla distinta, cada una
# de las 5 franjas -- ver tests/test_seed_staging_rota.py para la prueba de
# las tres invariantes (cobertura diaria, descanso tras noche, 2 libres/semana).
_PLANTILLA_ROTA = {0: "NOCHE", 1: "L", 2: "M", 3: "T", 4: "D", 5: "L", 6: "T"}
_COMBOS_ROTA = [(fase, variante) for fase in range(7) for variante in ("N", "C")]


def generar_rota(usuarios, franjas, fecha_inicio, fecha_fin):
    """Genera (sin session.add ni commit) los TurnoPlanilla/EstadoDiaPlanilla/
    SalienteDia de cada usuario entre fecha_inicio y fecha_fin (inclusive),
    repartiendo a los usuarios en round-robin sobre las 14 plantillas de
    `_COMBOS_ROTA`. Devuelve (turnos, estados, salientes)."""
    codigo_a_franja = {
        "M": franjas["man"], "T": franjas["tar"], "N": franjas["noch"],
        "D": franjas["d12"], "C": franjas["n12"],
    }
    turnos, estados, salientes = [], [], []

    for idx, usuario in enumerate(usuarios):
        fase, variante = _COMBOS_ROTA[idx % len(_COMBOS_ROTA)]
        dia = fecha_inicio
        while dia <= fecha_fin:
            r = (dia.weekday() - fase) % 7
            codigo = _PLANTILLA_ROTA[r]
            if codigo == "NOCHE":
                codigo = variante
            if codigo == "L":
                estados.append(EstadoDiaPlanilla(usuario=usuario, fecha=dia, tipo="libre"))
                if r == 1:
                    salientes.append(SalienteDia(usuario=usuario, fecha=dia))
            else:
                turnos.append(TurnoPlanilla(usuario=usuario, fecha=dia, franja_horaria=codigo_a_franja[codigo]))
            dia += timedelta(days=1)

    return turnos, estados, salientes


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


# ═════════════════════════════════════════════════════════════════════════
# AMPLIACIÓN: UCO · Hospital Universitario La Paz · Enfermería
# ═════════════════════════════════════════════════════════════════════════
#
# A diferencia de `sembrar()` (que crea sus propios usuarios de cero y se
# salta por completo si ya se aplicó), esta ampliación es aditiva: se suma
# a la unidad real UCO·La Paz·Enfermería de staging, que ya tiene sus
# propios usuarios (creados a mano por quien prueba la app). Nunca borra ni
# modifica usuarios existentes -- solo añade cuentas sintéticas, planillas
# jul-sep-2026 y hojas de cambio. Tiene su propia comprobación de
# idempotencia (independiente de `_ya_sembrado()`), así que se ejecuta
# siempre, tanto si `sembrar()` se aplicó de cero como si ya estaba hecha.

UCO_HOSPITAL   = "Hospital Universitario La Paz"
UCO_UNIDAD     = "UCO"
UCO_CATEGORIA  = "Enfermería"
UCO_SUPERVISORA_EMAIL    = "supervisora.uco@demo.turnero.com"
UCO_SUPERVISORA_PASSWORD = "supervisora"
UCO_ROTA_INICIO = date(2026, 7, 1)
UCO_ROTA_FIN    = date(2026, 9, 30)
UCO_HOJAS_INICIO = date(2026, 8, 1)
UCO_HOJAS_FIN    = date(2026, 9, 30)


def _cuentas_uco(cuentas):
    """Mismo nombre, email distinto: evita chocar con la unidad de
    demostración aislada de producción (`flask seed-demo`, activa también
    en staging vía DEMO_ENABLED), que usa los mismos nombres/emails base de
    DEMO_ACCOUNTS/BOT_ACCOUNTS -- el email es único a nivel de toda la base
    de datos, así que reutilizarlos tal cual revienta con un
    IntegrityError en cuanto ambas unidades conviven en la misma BD."""
    return [
        (nombre, f"uco.{email.split('@')[0]}@demo.turnero.com")
        for nombre, email in cuentas
    ]


UCO_DEMO_ACCOUNTS = _cuentas_uco(DEMO_ACCOUNTS)
UCO_BOT_ACCOUNTS  = _cuentas_uco(BOT_ACCOUNTS)


def _ya_ampliada_uco(unidad):
    return Usuario.query.filter_by(
        unidad_id=unidad.id, email=UCO_BOT_ACCOUNTS[0][1]
    ).first() is not None


def _upsert_supervisora_uco(unidad):
    """Devuelve la cuenta supervisora de esa unidad, sustituyendo cualquier
    otra existente en el mismo grupo de intercambio -- salvo que ya tenga
    hojas de cambio decididas (violaría la FK al borrarla), en cuyo caso se
    deja intacta y se avisa."""
    existente = Usuario.query.filter_by(email=UCO_SUPERVISORA_EMAIL).first()
    if existente:
        return existente

    grupo_id = unidad.grupo_intercambio_id
    otras = (
        Usuario.query.join(Unidad, Usuario.unidad_id == Unidad.id)
        .filter(Unidad.grupo_intercambio_id == grupo_id, Usuario.es_supervisora.is_(True))
        .all()
    )
    for sup in otras:
        tiene_decisiones = DocumentoCambio.query.filter_by(supervisora_id=sup.id).first() is not None
        if tiene_decisiones:
            print(f"  Aviso: no se borra a la supervisora existente ({sup.email}); "
                  "tiene hojas de cambio ya decididas. Se deja intacta.")
            continue
        db.session.delete(sup)
    db.session.flush()

    supervisora = Usuario(
        nombre="Supervisora UCO", email=UCO_SUPERVISORA_EMAIL,
        unidad=unidad, categoria=unidad.categoria,
        es_supervisora=True, onboarding_visto=True,
    )
    supervisora.set_password(UCO_SUPERVISORA_PASSWORD)
    db.session.add(supervisora)
    db.session.flush()
    return supervisora


def _limpiar_rota_previa(usuarios, fecha_inicio, fecha_fin):
    """Borra turnos/estados/salientes ya existentes de esos usuarios en ese
    rango, para poder regenerar la rota sin chocar con datos previos
    (manuales o de una ejecución anterior del script)."""
    ids = [u.id for u in usuarios]
    if not ids:
        return
    for modelo in (TurnoPlanilla, EstadoDiaPlanilla, SalienteDia):
        modelo.query.filter(
            modelo.usuario_id.in_(ids),
            modelo.fecha >= fecha_inicio, modelo.fecha <= fecha_fin,
        ).delete(synchronize_session=False)
    db.session.commit()


def _mapas_turnos_no_nocturnos(usuarios, turnos):
    """{usuario: {fecha: franja_horaria}}, solo con turnos de franjas no
    nocturnas (para elegir cambios sin tocar el descanso obligatorio tras
    una Noche/Nocturno 12h) y fechas dentro de agosto-septiembre 2026."""
    turnos_por_usuario = {u: {} for u in usuarios}
    for t in turnos:
        if t.franja_horaria.nombre in ("Noche", "Nocturno 12h"):
            continue
        if not (UCO_HOJAS_INICIO <= t.fecha <= UCO_HOJAS_FIN):
            continue
        turnos_por_usuario[t.usuario][t.fecha] = t.franja_horaria
    return turnos_por_usuario


def _libres_por_usuario(usuarios, estados):
    libres = {u: set() for u in usuarios}
    for e in estados:
        libres[e.usuario].add(e.fecha)
    return libres


def _buscar_intercambio(u_trabaja, u_libra, turnos_por_usuario, libres_por_usuario, ya_usadas):
    """Fecha (dentro de UCO_HOJAS_INICIO/FIN) en la que `u_trabaja` tiene un
    turno no nocturno y `u_libra` está libre ese mismo día, sin repetir
    fechas ya usadas. Devuelve (fecha, franja) o None."""
    for fecha, franja in sorted(turnos_por_usuario[u_trabaja].items()):
        if fecha in ya_usadas:
            continue
        if fecha in libres_por_usuario[u_libra]:
            return fecha, franja
    return None


def sembrar_hojas_cambio_uco(usuarios, supervisora, turnos, estados):
    """Crea al menos 2 hojas de cambio por usuario (agosto-septiembre 2026),
    repartidas entre sus 4 estados posibles: pendiente de firma, completa
    pendiente de decisión de la supervisora, autorizada y denegada. Usa los
    servicios reales (firma cruzada, autorización) para que numeración,
    notificaciones y volcado a planilla queden igual que en producción."""
    turnos_por_usuario  = _mapas_turnos_no_nocturnos(usuarios, turnos)
    libres_por_usuario  = _libres_por_usuario(usuarios, estados)

    ciclo_estados = ["pendiente_firmas", "completo_pendiente", "autorizado", "denegado"]
    n_creadas = 0

    # Se empareja cada usuario con el que está a "media vuelta" de distancia
    # en la lista (no con el contiguo): dos usuarios consecutivos comparten
    # la misma fase de rota (_COMBOS_ROTA los agrupa de dos en dos, mismo
    # `fase`, distinta `variante` de noche), así que tendrían el mismo
    # patrón de días libres/trabajados y nunca habría hueco para un cambio.
    mitad = len(usuarios) // 2
    parejas = [(usuarios[i], usuarios[i + mitad]) for i in range(mitad)]
    if len(usuarios) % 2:
        # usuario impar suelto: se empareja también con el primero de la lista
        parejas.append((usuarios[-1], usuarios[0]))

    for idx, (u_a, u_b) in enumerate(parejas):
        estados_pareja = [ciclo_estados[(2 * idx) % 4], ciclo_estados[(2 * idx + 1) % 4]]
        ya_usadas = set()
        for estado_deseado in estados_pareja:
            cede = _buscar_intercambio(u_a, u_b, turnos_por_usuario, libres_por_usuario, ya_usadas)
            if cede is None:
                continue
            fecha_cede, franja_cede = cede
            ya_usadas.add(fecha_cede)
            recibe = _buscar_intercambio(u_b, u_a, turnos_por_usuario, libres_por_usuario, ya_usadas)
            if recibe is None:
                continue
            fecha_recibe, franja_recibe = recibe
            ya_usadas.add(fecha_recibe)

            doc = crear_documento_cambio(
                u_a, u_b, fecha_cede, franja_cede.id, fecha_recibe, franja_recibe.id,
            )
            n_creadas += 1
            if estado_deseado == "pendiente_firmas":
                firmar_documento(doc, u_a, "data:image/png;base64,seed-firma")
                continue
            firmar_documento(doc, u_a, "data:image/png;base64,seed-firma")
            firmar_documento(doc, u_b, "data:image/png;base64,seed-firma")
            if estado_deseado == "autorizado":
                autorizar_documento(doc, supervisora)
            elif estado_deseado == "denegado":
                denegar_documento(doc, supervisora, "Necesidades del servicio esos días.")
            # "completo_pendiente": se deja completo, sin decisión (por defecto).

    print(f"  {n_creadas} hojas de cambio creadas para {len(usuarios)} usuarios.")


def ampliar_uco_la_paz():
    insertar_categorias_semilla()
    db.session.flush()
    cat_enf = Categoria.query.filter_by(nombre=UCO_CATEGORIA).first()

    pais      = encontrar_o_crear_pais("España")
    provincia = encontrar_o_crear_provincia("Madrid", pais)
    ciudad    = encontrar_o_crear_ciudad("Madrid", provincia)
    hospital  = encontrar_o_crear_hospital(UCO_HOSPITAL, ciudad)
    unidad, _ = encontrar_o_crear_unidad(UCO_UNIDAD, hospital, cat_enf)
    db.session.flush()

    if _ya_ampliada_uco(unidad):
        print(f"{UCO_UNIDAD}·{UCO_HOSPITAL}·{UCO_CATEGORIA} ya está ampliada — nada que hacer.")
        return

    print(f"Ampliando {UCO_UNIDAD}·{UCO_HOSPITAL}·{UCO_CATEGORIA}...")
    sembrar_contenido_bot(
        unidad, cat_enf, incluir_planillas=False,
        cuentas_demo=UCO_DEMO_ACCOUNTS, cuentas_bot=UCO_BOT_ACCOUNTS,
    )
    db.session.flush()

    supervisora = _upsert_supervisora_uco(unidad)

    usuarios = (
        Usuario.query.filter_by(unidad_id=unidad.id)
        .filter(Usuario.id != supervisora.id)
        .order_by(Usuario.id)
        .all()
    )
    g = unidad.grupo_intercambio
    franjas = {
        "man": _franja(g, "Mañana"), "tar": _franja(g, "Tarde"),
        "noch": _franja(g, "Noche"), "d12": _franja(g, "Diurno 12h"),
        "n12": _franja(g, "Nocturno 12h"),
    }

    _limpiar_rota_previa(usuarios, UCO_ROTA_INICIO, UCO_ROTA_FIN)
    turnos, estados, salientes = generar_rota(usuarios, franjas, UCO_ROTA_INICIO, UCO_ROTA_FIN)
    db.session.add_all(turnos)
    db.session.add_all(estados)
    db.session.add_all(salientes)
    for usuario in usuarios:
        for mes in (7, 8, 9):
            planilla = PlanillaMes.query.filter_by(usuario_id=usuario.id, anyo=2026, mes=mes).first()
            if planilla is None:
                planilla = PlanillaMes(usuario=usuario, anyo=2026, mes=mes)
                db.session.add(planilla)
            planilla.publicada = True
    db.session.commit()
    print(f"  Rota jul-sep-2026 generada para {len(usuarios)} usuarios.")

    # Las hojas de cambio notifican (push/email/campana), lo que pasa por
    # Flask-Babel (_()) y url_for -- ambos necesitan una request activa, que
    # no existe al ejecutar este script por CLI (solo hay app_context).
    with current_app.test_request_context():
        sembrar_hojas_cambio_uco(usuarios, supervisora, turnos, estados)

    print(f"{UCO_UNIDAD}·{UCO_HOSPITAL}·{UCO_CATEGORIA} ampliada correctamente.")


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    os.environ.pop("SENTRY_DSN", None)  # evita importar sentry_sdk si no está instalado localmente
    env   = os.environ.get("FLASK_ENV", "production")
    app   = create_app(env)
    with app.app_context():
        if reset:
            _truncar()
            sembrar()
        elif not _ya_sembrado():
            sembrar()
        else:
            print(
                f"El seed base ya está aplicado (marker: {_SEED_MARKER}).\n"
                "Usa --reset para truncar todo y recrear desde cero."
            )
        ampliar_uco_la_paz()
