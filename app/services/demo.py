"""Seed y reset de la unidad de demostración.

Crea un entorno ficticio con usuarios, publicaciones y matches en distintos
estados para que cualquier persona pueda explorar la app sin datos reales.
Las fechas de turno son siempre relativas a hoy, por lo que el contenido
es válido indefinidamente mientras se resetee periódicamente.
"""
import calendar
import os
from datetime import date, datetime, timezone, timedelta

from app.extensions import db
from app.models import (
    AuditEliminacion,
    BusquedaGuardada,
    Categoria,
    Ciudad,
    CompatibilidadPlanilla,
    EstadoDiaPlanilla,
    FranjaHoraria,
    GrupoIntercambio,
    Hospital,
    MatchCambio,
    MatchParticipacion,
    NotaDia,
    Notificacion,
    Pais,
    PlanillaMes,
    Provincia,
    PublicacionCambio,
    SalienteDia,
    SuscripcionPublicaciones,
    TurnoCedido,
    TurnoAceptado,
    TurnoPlanilla,
    Unidad,
    Usuario,
    insertar_categorias_semilla,
)
from app.services.registro import (
    encontrar_o_crear_ciudad,
    encontrar_o_crear_hospital,
    encontrar_o_crear_pais,
    encontrar_o_crear_provincia,
    encontrar_o_crear_unidad,
)

DEMO_PAIS      = "País de Demostración"
DEMO_PROVINCIA = "Provincia de Demostración"
DEMO_CIUDAD    = "Ciudad de Demostración"
DEMO_HOSPITAL  = "Hospital de Demostración"
DEMO_UNIDAD    = "Urgencias de Demostración"
DEMO_PASSWORD  = "demo1234"

DEMO_ACCOUNTS = [
    ("Ana Demo",     "demo1@turnero.com"),
    ("Carlos Demo",  "demo2@turnero.com"),
    ("Elena Demo",   "demo3@turnero.com"),
]
_BOT_ACCOUNTS = [
    ("María García",    "bot.maria@demo.turnero.com"),
    ("Javier López",    "bot.javier@demo.turnero.com"),
    ("Sofía Ruiz",      "bot.sofia@demo.turnero.com"),
    ("Pedro Martín",    "bot.pedro@demo.turnero.com"),
    ("Laura Fernández", "bot.laura@demo.turnero.com"),
]

_DEMO_EMAILS = {email for _, email in DEMO_ACCOUNTS + _BOT_ACCOUNTS}


def _hoy(offset=0):
    return date.today() + timedelta(days=offset)


def _ahora(offset_days=0):
    return datetime.now(timezone.utc) - timedelta(days=offset_days)


def _usuario(nombre, email, unidad, categoria):
    u = Usuario(nombre=nombre, email=email, unidad=unidad,
                categoria=categoria, onboarding_visto=False)
    u.set_password(DEMO_PASSWORD)
    db.session.add(u)
    return u


def _pub(usuario, tipo, estado="abierta", mensaje=None, created_at=None):
    p = PublicacionCambio(
        usuario=usuario, tipo=tipo, estado=estado, mensaje=mensaje,
        fecha_creacion=created_at or _ahora(),
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
    m = MatchCambio(tipo=tipo, estado=estado,
                    fecha_creacion=created_at or _ahora())
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


# ─── reset ───────────────────────────────────────────────────────────────────

def _borrar_demo():
    """Elimina toda la estructura de demo sin tocar datos reales.

    Usa exclusivamente text() para evitar conflictos entre bulk-delete y el
    mapa de identidad del ORM (synchronize_session=False deja objetos obsoletos
    en sesión, lo que puede romper el commit si luego se mezclan ORM deletes).
    """
    from sqlalchemy import text

    pais = Pais.query.filter_by(nombre=DEMO_PAIS).first()
    if not pais:
        return

    provincia = Provincia.query.filter_by(nombre=DEMO_PROVINCIA, pais_id=pais.id).first()
    ciudad    = Ciudad.query.filter_by(nombre=DEMO_CIUDAD, provincia_id=provincia.id).first() if provincia else None
    hospital  = Hospital.query.filter_by(nombre=DEMO_HOSPITAL, ciudad_id=ciudad.id).first() if ciudad else None

    hosp_id = hospital.id if hospital else None
    ciu_id  = ciudad.id   if ciudad   else None
    prov_id = provincia.id if provincia else None
    pais_id = pais.id

    # Colectar IDs antes de borrar nada
    unidad_ids = [u.id for u in Unidad.query.filter_by(hospital_id=hosp_id).all()] if hosp_id else []
    gi_ids     = [u.grupo_intercambio_id for u in Unidad.query.filter(Unidad.id.in_(unidad_ids)).all()] if unidad_ids else []
    user_ids   = [u.id for u in Usuario.query.filter(Usuario.unidad_id.in_(unidad_ids)).all()] if unidad_ids else []
    pub_ids    = [p.id for p in PublicacionCambio.query.filter(PublicacionCambio.usuario_id.in_(user_ids)).all()] if user_ids else []
    match_ids  = list({mp.match_id for mp in MatchParticipacion.query.filter(MatchParticipacion.publicacion_id.in_(pub_ids)).all()}) if pub_ids else []

    def _del(tabla, condicion, params):
        db.session.execute(text(f"DELETE FROM {tabla} WHERE {condicion}"), params)

    def _del_in(tabla, columna, ids):
        if ids:
            db.session.execute(text(f"DELETE FROM {tabla} WHERE {columna} = ANY(:ids)"), {"ids": ids})

    # Borrar en orden respetando FK (hijos antes que padres)
    _del_in("match_participacion", "match_id",       match_ids)
    _del_in("match_cambio",        "id",              match_ids)
    _del_in("turno_cedido",        "publicacion_id",  pub_ids)
    _del_in("turno_aceptado",      "publicacion_id",  pub_ids)
    _del_in("publicacion_cambio",  "id",              pub_ids)
    _del_in("notificacion",        "usuario_id",      user_ids)
    _del_in("busqueda_guardada",   "usuario_id",      user_ids)
    if user_ids:
        db.session.execute(text(
            "DELETE FROM suscripcion_publicaciones "
            "WHERE suscriptor_id = ANY(:ids) OR publicador_id = ANY(:ids)"
        ), {"ids": user_ids})
    _del_in("estado_dia_planilla", "usuario_id",  user_ids)
    _del_in("turno_planilla",      "usuario_id",  user_ids)
    _del_in("nota_dia",            "usuario_id",  user_ids)
    _del_in("saliente_dia",        "usuario_id",  user_ids)
    _del_in("planilla_mes",        "usuario_id",  user_ids)
    _del_in("usuario",             "id",          user_ids)
    _del_in("audit_eliminacion",   "unidad_id",   unidad_ids)
    _del_in("unidad",              "id",          unidad_ids)
    _del_in("franja_horaria",      "grupo_intercambio_id", gi_ids)
    _del_in("grupo_intercambio",   "id",          gi_ids)
    if hosp_id:
        _del("hospital",  "id = :id", {"id": hosp_id})
    if ciu_id:
        _del("ciudad",    "id = :id", {"id": ciu_id})
    if prov_id:
        _del("provincia", "id = :id", {"id": prov_id})
    _del("pais", "id = :id", {"id": pais_id})

    db.session.commit()


# ─── seed ────────────────────────────────────────────────────────────────────

def _sembrar_demo():
    insertar_categorias_semilla()
    db.session.flush()
    cat_enf = Categoria.query.filter_by(nombre="Enfermería").first()

    pais      = encontrar_o_crear_pais(DEMO_PAIS)
    provincia = encontrar_o_crear_provincia(DEMO_PROVINCIA, pais)
    ciudad    = encontrar_o_crear_ciudad(DEMO_CIUDAD, provincia)
    hospital  = encontrar_o_crear_hospital(DEMO_HOSPITAL, ciudad)
    unidad, _ = encontrar_o_crear_unidad(DEMO_UNIDAD, hospital, cat_enf)
    db.session.flush()

    g = unidad.grupo_intercambio
    man  = _franja(g, "Mañana")
    tar  = _franja(g, "Tarde")
    noch = _franja(g, "Noche")
    d12  = _franja(g, "Diurno 12h")
    n12  = _franja(g, "Nocturno 12h")

    # Cuentas demo
    ana, carlos, elena = [
        _usuario(nombre, email, unidad, cat_enf)
        for nombre, email in DEMO_ACCOUNTS
    ]
    # Bots
    maria, javier, sofia, pedro, laura = [
        _usuario(nombre, email, unidad, cat_enf)
        for nombre, email in _BOT_ACCOUNTS
    ]
    db.session.flush()

    # ── Publicaciones abiertas de los bots (dan vida a la unidad) ──────────
    pub_b1 = _pub(maria,  "cambio",    mensaje="Cambio mi mañana por una tarde, necesito llevar al médico a mi madre", created_at=_ahora(5))
    _tc(pub_b1, _hoy(18), man);  _ta(pub_b1, _hoy(22), tar)

    pub_b2 = _pub(javier, "regalo",    mensaje="Regalo mi nocturno, me surge un viaje", created_at=_ahora(3))
    _tc(pub_b2, _hoy(14), n12)

    pub_b3 = _pub(sofia,  "peticion",  mensaje="Busco alguien que me cubra la mañana del día 25", created_at=_ahora(2))
    _ta(pub_b3, _hoy(25), man)

    pub_b4 = _pub(pedro,  "junte",     created_at=_ahora(4))
    _tc(pub_b4, _hoy(30), noch);  _ta(pub_b4, _hoy(37), noch)

    pub_b5 = _pub(laura,  "cambio_dia", mensaje="Cualquier turno me vale ese día", created_at=_ahora(1))
    _tc(pub_b5, _hoy(20), d12);  _ta(pub_b5, _hoy(27), cualquier_franja=True)

    pub_b6 = _pub(maria,  "cambio",    created_at=_ahora(7))
    _tc(pub_b6, _hoy(35), tar);  _ta(pub_b6, _hoy(40), man)

    pub_b7 = _pub(pedro,  "regalo",    created_at=_ahora(6))
    _tc(pub_b7, _hoy(45), man)

    # ── demo1 (Ana): match propuesto con bot Javier — puede confirmar ──────
    pub_ana_m = _pub(ana, "cambio", mensaje="Cambio tarde del 12 por mañana, tengo cita", created_at=_ahora(8))
    tc_ana    = _tc(pub_ana_m, _hoy(12), tar)
    ta_ana    = _ta(pub_ana_m, _hoy(15), man)

    pub_jav_m = _pub(javier, "cambio", created_at=_ahora(8))
    tc_jav    = _tc(pub_jav_m, _hoy(15), man)
    ta_jav    = _ta(pub_jav_m, _hoy(12), tar)
    db.session.flush()

    m1 = _match(estado="propuesto", created_at=_ahora(1))
    db.session.flush()
    _part(m1, pub_ana_m, tc=tc_ana, ta=ta_ana)
    _part(m1, pub_jav_m, tc=tc_jav, ta=ta_jav)

    # Ana también tiene una publicación abierta sin match
    pub_ana_open = _pub(ana, "regalo", mensaje="Regalo mi noche del día 50, me voy fuera", created_at=_ahora(2))
    _tc(pub_ana_open, _hoy(50), noch)

    # ── demo2 (Carlos): confirmado_parcial — él confirmó, bot pendiente ────
    pub_car_m = _pub(carlos, "cambio", mensaje="Necesito librar esa tarde", created_at=_ahora(10))
    tc_car    = _tc(pub_car_m, _hoy(28), noch)
    ta_car    = _ta(pub_car_m, _hoy(21), tar)

    pub_sof_m = _pub(sofia, "cambio", created_at=_ahora(10))
    tc_sof    = _tc(pub_sof_m, _hoy(21), tar)
    ta_sof    = _ta(pub_sof_m, _hoy(28), noch)
    db.session.flush()

    m2 = _match(estado="confirmado_parcial", created_at=_ahora(3))
    db.session.flush()
    _part(m2, pub_car_m, tc=tc_car, ta=ta_car,
          confirmado=True, confirmed_at=_ahora(2))
    _part(m2, pub_sof_m, tc=tc_sof, ta=ta_sof, confirmado=False)

    # Carlos también tiene una publicación abierta
    pub_car_open = _pub(carlos, "peticion", mensaje="Busco mañana libre esa semana", created_at=_ahora(1))
    _ta(pub_car_open, _hoy(33), man)

    # ── demo3 (Elena): dos publicaciones abiertas, sin match aún ──────────
    pub_ele1 = _pub(elena, "cambio", mensaje="Cambio mi diurno del 38 por una tarde", created_at=_ahora(3))
    _tc(pub_ele1, _hoy(38), d12);  _ta(pub_ele1, _hoy(42), tar)

    pub_ele2 = _pub(elena, "cambio", created_at=_ahora(1))
    _tc(pub_ele2, _hoy(55), man);  _ta(pub_ele2, _hoy(60), tar)

    # ── Match confirmado_total entre bots (muestra el flujo completado) ────
    conf_dt = _ahora(5)
    pub_lau_c = _pub(laura, "cambio", estado="confirmada", created_at=_ahora(12))
    tc_lau    = _tc(pub_lau_c, _hoy(7),  man, estado="resuelto")
    ta_lau    = _ta(pub_lau_c, _hoy(10), tar, estado="resuelto")

    pub_ped_c = _pub(pedro, "cambio", estado="confirmada", created_at=_ahora(12))
    tc_ped    = _tc(pub_ped_c, _hoy(10), tar, estado="resuelto")
    ta_ped    = _ta(pub_ped_c, _hoy(7),  man, estado="resuelto")
    db.session.flush()

    m3 = _match(estado="confirmado_total", created_at=_ahora(6))
    m3.fecha_confirmacion_total = conf_dt
    db.session.flush()
    _part(m3, pub_lau_c, tc=tc_lau, ta=ta_lau,
          confirmado=True, confirmed_at=_ahora(6))
    _part(m3, pub_ped_c, tc=tc_ped, ta=ta_ped,
          confirmado=True, confirmed_at=conf_dt)

    _sembrar_planillas(
        usuarios=[ana, carlos, elena, maria, javier, sofia, pedro, laura],
        franjas={"man": man, "tar": tar, "noch": noch, "d12": d12, "n12": n12},
        grupo=g,
    )

    db.session.commit()


def _sembrar_planillas(usuarios, franjas, grupo):
    """Crea planillas publicadas para el mes actual y el siguiente."""
    man, tar, noch, d12, n12 = (
        franjas["man"], franjas["tar"], franjas["noch"], franjas["d12"], franjas["n12"],
    )
    hoy = date.today()

    # Patrones de turno por usuario (franja, días-de-semana con turno en ese mes)
    # weekday(): 0=lun, 1=mar, 2=mie, 3=jue, 4=vie, 5=sab, 6=dom
    patrones = [
        # (usuario, franja_principal, franja_alternativa, días de semana con turno)
        (usuarios[0], man,  None, {0, 2, 4}),        # Ana:    lun/mie/vie → mañana
        (usuarios[1], tar,  None, {1, 3, 5}),        # Carlos: mar/jue/sab → tarde
        (usuarios[2], d12,  n12,  {0, 4}),           # Elena:  lun→diurno 12h, vie→nocturno 12h
        (usuarios[3], man,  tar,  {0, 1, 2}),        # María:  lun/mar→mañana, mie→tarde
        (usuarios[4], tar,  noch, {2, 3, 4}),        # Javier: mie/jue→tarde, vie→noche
        (usuarios[5], man,  None, {1, 3}),           # Sofía:  mar/jue → mañana
        (usuarios[6], noch, n12,  {5, 6}),           # Pedro:  sab→noche, dom→nocturno 12h
        (usuarios[7], tar,  man,  {0, 2, 5}),        # Laura:  lun/mie→tarde, sab→mañana
    ]

    for delta_mes in (0, 1):
        anyo = hoy.year + (hoy.month + delta_mes - 1) // 12
        mes  = (hoy.month + delta_mes - 1) % 12 + 1
        _, n_dias = calendar.monthrange(anyo, mes)

        for usuario, franja_a, franja_b, dias_semana in patrones:
            db.session.add(PlanillaMes(
                usuario=usuario, anyo=anyo, mes=mes, publicada=True,
            ))
            for dia in range(1, n_dias + 1):
                fecha = date(anyo, mes, dia)
                wd = fecha.weekday()
                if wd not in dias_semana:
                    continue
                franja = franja_b if (franja_b and wd == max(dias_semana)) else franja_a
                db.session.add(TurnoPlanilla(
                    usuario=usuario, fecha=fecha, franja_horaria=franja,
                ))


# ─── punto de entrada público ─────────────────────────────────────────────────

def reset_demo():
    """Borra la unidad demo y la recrea con datos frescos."""
    _borrar_demo()
    _sembrar_demo()


def ya_sembrado():
    return bool(Usuario.query.filter_by(email=DEMO_ACCOUNTS[0][1]).first())
