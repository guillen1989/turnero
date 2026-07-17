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
BOT_ACCOUNTS = [
    ("María García",     "bot.maria@demo.turnero.com"),
    ("Javier López",     "bot.javier@demo.turnero.com"),
    ("Sofía Ruiz",       "bot.sofia@demo.turnero.com"),
    ("Pedro Martín",     "bot.pedro@demo.turnero.com"),
    ("Laura Fernández",  "bot.laura@demo.turnero.com"),
    ("Marta Sánchez",    "bot.marta@demo.turnero.com"),
    ("Diego Torres",     "bot.diego@demo.turnero.com"),
    ("Lucía Romero",     "bot.lucia@demo.turnero.com"),
    ("Alejandro Díaz",   "bot.alejandro@demo.turnero.com"),
    ("Carmen Molina",    "bot.carmen@demo.turnero.com"),
    ("Raúl Ortega",      "bot.raul@demo.turnero.com"),
    ("Isabel Navarro",   "bot.isabel@demo.turnero.com"),
    ("Daniel Castro",    "bot.daniel@demo.turnero.com"),
    ("Paula Iglesias",   "bot.paula@demo.turnero.com"),
    ("Sergio Vega",      "bot.sergio@demo.turnero.com"),
    ("Cristina Herrera", "bot.cristina@demo.turnero.com"),
    ("Miguel Ramos",     "bot.miguel@demo.turnero.com"),
    ("Beatriz Gil",      "bot.beatriz@demo.turnero.com"),
    ("Alberto Serrano",  "bot.alberto@demo.turnero.com"),
    ("Nuria Campos",     "bot.nuria@demo.turnero.com"),
]

# Plantillas de publicación abierta que dan vida a la unidad. Se repiten
# ciclando sobre todos los bots para generar varias rondas de contenido.
_BOT_PUB_TEMPLATES = [
    dict(tipo="cambio", mensaje="Cambio mi mañana por una tarde, necesito llevar al médico a mi madre",
         cedido=("man", 18), aceptado=("tar", 22), created_offset=5),
    dict(tipo="regalo", mensaje="Regalo mi nocturno, me surge un viaje",
         cedido=("n12", 14), created_offset=3),
    dict(tipo="peticion", mensaje="Busco alguien que me cubra la mañana del día 25",
         aceptado=("man", 25), created_offset=2),
    dict(tipo="junte", mensaje=None,
         cedido=("noch", 30), aceptado=("noch", 37), created_offset=4),
    dict(tipo="cambio_dia", mensaje="Cualquier turno me vale ese día",
         cedido=("d12", 20), aceptado=(None, 27), created_offset=1),
    dict(tipo="cambio", mensaje=None,
         cedido=("tar", 35), aceptado=("man", 40), created_offset=7),
    dict(tipo="regalo", mensaje=None,
         cedido=("man", 45), created_offset=6),
]
_RONDAS_PUBLICACIONES_BOT = 4

_DEMO_EMAILS = {email for _, email in DEMO_ACCOUNTS + BOT_ACCOUNTS}


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


def _desplazar(par_franja_dia, dias):
    """Suma `dias` al offset de un par (franja_key, dia) de una plantilla.

    `franja_key` puede ser None (turno aceptado en cualquier franja); se
    conserva tal cual para no alterar ese significado.
    """
    if par_franja_dia is None:
        return None
    franja_key, dia = par_franja_dia
    return (franja_key, dia + dias)


def _pub_bot_generica(bot, tipo, mensaje, franjas, cedido=None, aceptado=None, created_offset=0):
    """Crea una publicación de bot a partir de una plantilla de `_BOT_PUB_TEMPLATES`."""
    p = _pub(bot, tipo, mensaje=mensaje, created_at=_ahora(created_offset))
    if cedido:
        franja_key, dia = cedido
        _tc(p, _hoy(dia), franjas[franja_key])
    if aceptado:
        franja_key, dia = aceptado
        if franja_key is None:
            _ta(p, _hoy(dia), cualquier_franja=True)
        else:
            _ta(p, _hoy(dia), franjas[franja_key])
    return p


def _sembrar_publicaciones_bot(bots, franjas):
    """Genera varias rondas de publicaciones abiertas repartidas entre los bots."""
    n_plantillas = len(_BOT_PUB_TEMPLATES)
    for ronda in range(_RONDAS_PUBLICACIONES_BOT):
        for i, tmpl in enumerate(_BOT_PUB_TEMPLATES):
            bot = bots[(ronda * n_plantillas + i) % len(bots)]
            _pub_bot_generica(
                bot, tmpl["tipo"], tmpl["mensaje"], franjas,
                cedido=_desplazar(tmpl.get("cedido"), ronda * 8),
                aceptado=_desplazar(tmpl.get("aceptado"), ronda * 8),
                created_offset=tmpl["created_offset"] + ronda,
            )


def _match_confirmado_total(bot_a, bot_b, dia_a, dia_b, franja_a, franja_b, base_offset):
    """Crea un match ya resuelto entre dos bots (cierra el ciclo cedido/aceptado)."""
    pub_created  = _ahora(base_offset + 6)
    match_created = _ahora(base_offset)
    conf_dt      = _ahora(base_offset - 1)

    pub_a = _pub(bot_a, "cambio", estado="confirmada", created_at=pub_created)
    tc_a  = _tc(pub_a, _hoy(dia_a), franja_a, estado="resuelto")
    ta_a  = _ta(pub_a, _hoy(dia_b), franja_b, estado="resuelto")

    pub_b = _pub(bot_b, "cambio", estado="confirmada", created_at=pub_created)
    tc_b  = _tc(pub_b, _hoy(dia_b), franja_b, estado="resuelto")
    ta_b  = _ta(pub_b, _hoy(dia_a), franja_a, estado="resuelto")
    db.session.flush()

    m = _match(estado="confirmado_total", created_at=match_created)
    m.fecha_confirmacion_total = conf_dt
    db.session.flush()
    _part(m, pub_a, tc=tc_a, ta=ta_a, confirmado=True, confirmed_at=match_created)
    _part(m, pub_b, tc=tc_b, ta=ta_b, confirmado=True, confirmed_at=conf_dt)
    return m


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

    # Borrar en orden respetando FK (hijos antes que padres).
    # notificacion.match_id referencia match_cambio.id: debe borrarse antes.
    _del_in("notificacion",        "usuario_id",      user_ids)
    _del_in("match_participacion", "match_id",       match_ids)
    _del_in("match_cambio",        "id",              match_ids)
    _del_in("turno_cedido",        "publicacion_id",  pub_ids)
    _del_in("turno_aceptado",      "publicacion_id",  pub_ids)
    _del_in("publicacion_cambio",  "id",              pub_ids)
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

def sembrar_contenido_bot(unidad, categoria, incluir_planillas=True):
    """Crea las 23 cuentas sintéticas (3 demo navegables + 20 bots) dentro de
    `unidad`, con publicaciones abiertas y matches en varios estados. No hace
    commit ni toca a los usuarios ya existentes de `unidad` -- responsabilidad
    del llamador. Reutilizable tanto por la unidad de demostración aislada
    (`_sembrar_demo`) como por una unidad real a la que se le quiera añadir
    contenido de ejemplo sin tocar sus usuarios existentes (ver
    scripts/seed_staging.py).

    `incluir_planillas=False` omite las planillas del mes actual/siguiente
    (pensadas para la demo aislada, siempre "hoy"); úsalo cuando el llamador
    vaya a generar sus propias planillas con fechas fijas para todo el
    grupo, evitando turnos duplicados el mismo día.
    """
    g = unidad.grupo_intercambio
    man  = _franja(g, "Mañana")
    tar  = _franja(g, "Tarde")
    noch = _franja(g, "Noche")
    d12  = _franja(g, "Diurno 12h")
    n12  = _franja(g, "Nocturno 12h")

    # Cuentas demo
    ana, carlos, elena = [
        _usuario(nombre, email, unidad, categoria)
        for nombre, email in DEMO_ACCOUNTS
    ]
    # Bots
    bots = [
        _usuario(nombre, email, unidad, categoria)
        for nombre, email in BOT_ACCOUNTS
    ]
    maria, javier, sofia, pedro, laura = bots[:5]
    marta, diego, lucia, alejandro, carmen, raul = bots[5:11]
    db.session.flush()

    franjas = {"man": man, "tar": tar, "noch": noch, "d12": d12, "n12": n12}

    # ── Publicaciones abiertas de los bots (dan vida a la unidad) ──────────
    _sembrar_publicaciones_bot(bots, franjas)

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

    # ── Matches confirmado_total entre bots (muestran el flujo completado) ──
    _match_confirmado_total(laura, pedro,     7,  10, man, tar,  base_offset=6)
    _match_confirmado_total(marta, diego,     8,  11, tar, noch, base_offset=7)
    _match_confirmado_total(lucia, alejandro, 9,  12, noch, man, base_offset=8)
    _match_confirmado_total(carmen, raul,     13, 16, d12, n12,  base_offset=9)

    if incluir_planillas:
        _sembrar_planillas(
            usuarios=[ana, carlos, elena] + bots,
            franjas=franjas,
            grupo=g,
        )

    return {"cuentas_demo": (ana, carlos, elena), "bots": bots, "franjas": franjas}


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

    sembrar_contenido_bot(unidad, cat_enf)

    db.session.commit()


def _sembrar_planillas(usuarios, franjas, grupo):
    """Crea planillas publicadas para el mes actual y el siguiente."""
    man, tar, noch, d12, n12 = (
        franjas["man"], franjas["tar"], franjas["noch"], franjas["d12"], franjas["n12"],
    )
    hoy = date.today()

    # Patrones de turno por usuario (franja, días-de-semana con turno en ese mes)
    # weekday(): 0=lun, 1=mar, 2=mie, 3=jue, 4=vie, 5=sab, 6=dom
    # Ciclo de patrones (franja_principal, franja_alternativa, días de semana
    # con turno) que se reparte entre todos los usuarios, en orden, repitiendo
    # si hay más usuarios que patrones. weekday(): 0=lun ... 6=dom.
    ciclo_patrones = [
        (man,  None, {0, 2, 4}),   # lun/mie/vie → mañana
        (tar,  None, {1, 3, 5}),   # mar/jue/sab → tarde
        (d12,  n12,  {0, 4}),      # lun→diurno 12h, vie→nocturno 12h
        (man,  tar,  {0, 1, 2}),   # lun/mar→mañana, mie→tarde
        (tar,  noch, {2, 3, 4}),   # mie/jue→tarde, vie→noche
        (man,  None, {1, 3}),      # mar/jue → mañana
        (noch, n12,  {5, 6}),      # sab→noche, dom→nocturno 12h
        (tar,  man,  {0, 2, 5}),   # lun/mie→tarde, sab→mañana
    ]

    for delta_mes in (0, 1):
        anyo = hoy.year + (hoy.month + delta_mes - 1) // 12
        mes  = (hoy.month + delta_mes - 1) % 12 + 1
        _, n_dias = calendar.monthrange(anyo, mes)

        for idx, usuario in enumerate(usuarios):
            franja_a, franja_b, dias_semana = ciclo_patrones[idx % len(ciclo_patrones)]
            db.session.add(PlanillaMes(
                usuario=usuario, anyo=anyo, mes=mes, publicada=True,
            ))
            for dia in range(1, n_dias + 1):
                fecha = date(anyo, mes, dia)
                wd = fecha.weekday()
                if wd not in dias_semana:
                    db.session.add(EstadoDiaPlanilla(
                        usuario=usuario, fecha=fecha, tipo="libre",
                    ))
                else:
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
