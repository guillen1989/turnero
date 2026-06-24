"""
Capa de búsqueda y creación de matches: conecta el motor puro con la base de datos.

Responsabilidades:
  - Filtrar candidatas por categoría, grupo de intercambio y estado activo.
  - Extraer los conjuntos de turnos de cada publicación ORM.
  - Delegar la lógica de coincidencia al motor puro (engine.py).
  - Crear registros MatchCambio, MatchParticipacion y Notificacion.
"""
from app.extensions import db
from app.models import (
    FranjaHoraria,
    MatchCambio,
    MatchParticipacion,
    Notificacion,
    PublicacionCambio,
    Unidad,
    Usuario,
)
from app.matching.engine import detectar_cadena_3, detectar_match_directo, detectar_match_regalo
from app.push.sender import enviar_push_condicional
from app.services.eventos import registrar_evento
from sqlalchemy.orm import selectinload


def _cedidos_abiertos(pub):
    return frozenset(
        (t.fecha, t.franja_horaria_id)
        for t in pub.turnos_cedidos
        if t.estado == "abierto"
    )


def _franjas_del_grupo(pub):
    """Devuelve los IDs de todas las franjas disponibles en el grupo del usuario."""
    grupo_id = db.session.get(Usuario, pub.usuario_id).unidad.grupo_intercambio_id
    return [f.id for f in FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id).all()]


def _aceptados(pub):
    """Frozenset de (fecha, franja_id) de los turnos aceptados.

    Si un turno tiene cualquier_franja=True, se expande a todas las franjas
    del grupo para que haga match con cualquier turno cedido de esa fecha.
    """
    result = set()
    franjas_cache = None
    for t in pub.turnos_aceptados:
        if t.cualquier_franja:
            if franjas_cache is None:
                franjas_cache = _franjas_del_grupo(pub)
            for fid in franjas_cache:
                result.add((t.fecha, fid))
        else:
            result.add((t.fecha, t.franja_horaria_id))
    return frozenset(result)


def _primer_cedido_que_acepta(pub, aceptados_contraparte):
    """Primer TurnoCedido abierto de pub cuya clave (fecha, franja_id) está en aceptados_contraparte."""
    for t in pub.turnos_cedidos:
        if t.estado == "abierto" and (t.fecha, t.franja_horaria_id) in aceptados_contraparte:
            return t
    return None


def _candidatas_base(publicacion, propietario, grupo_id):
    """Consulta base de candidatas activas del mismo grupo y categoría.

    Carga turnos_cedidos y turnos_aceptados en la misma consulta (2 SELECT IN
    adicionales) para evitar el N+1 que se produciría al acceder a ellos
    durante el matching.
    """
    return (
        PublicacionCambio.query
        .join(Usuario, PublicacionCambio.usuario_id == Usuario.id)
        .join(Unidad, Usuario.unidad_id == Unidad.id)
        .filter(
            PublicacionCambio.id != publicacion.id,
            PublicacionCambio.usuario_id != propietario.id,
            PublicacionCambio.estado.in_(("abierta", "parcialmente_resuelta")),
            Usuario.categoria_id == propietario.categoria_id,
            Unidad.grupo_intercambio_id == grupo_id,
        )
        .options(
            selectinload(PublicacionCambio.turnos_cedidos),
            selectinload(PublicacionCambio.turnos_aceptados),
        )
        .all()
    )


def buscar_matches_para(publicacion):
    """
    Devuelve las publicaciones activas que hacen match con `publicacion`.

    Matches completos (bidireccionales):
      - cambio ↔ cambio, junte ↔ junte

    Matches asimétricos completos:
      - regalo ↔ peticion

    Matches parciales (un lado satisfecho):
      - cambio ↔ regalo: el regalo cubre uno de los cedidos del cambio
      - cambio ↔ peticion: la peticion cubre uno de los aceptados del cambio
    """
    propietario = db.session.get(Usuario, publicacion.usuario_id)
    grupo_id = propietario.unidad.grupo_intercambio_id
    candidatas = _candidatas_base(publicacion, propietario, grupo_id)

    tipo = publicacion.tipo

    if tipo == "junte":
        cedidos_pub = _cedidos_abiertos(publicacion)
        aceptados_pub = _aceptados(publicacion)
        return [
            c for c in candidatas
            if c.tipo == "junte" and detectar_match_directo(
                cedidos_pub, aceptados_pub,
                _cedidos_abiertos(c), _aceptados(c),
            )
        ]

    if tipo == "cambio":
        cedidos_pub = _cedidos_abiertos(publicacion)
        aceptados_pub = _aceptados(publicacion)
        resultado = []
        for c in candidatas:
            if c.tipo == "cambio" and detectar_match_directo(
                cedidos_pub, aceptados_pub, _cedidos_abiertos(c), _aceptados(c)
            ):
                resultado.append(c)
            elif c.tipo == "regalo" and bool(cedidos_pub & _aceptados(c)):
                resultado.append(c)
            elif c.tipo == "peticion" and bool(aceptados_pub & _cedidos_abiertos(c)):
                resultado.append(c)
        return resultado

    if tipo == "regalo":
        aceptados_pub = _aceptados(publicacion)
        return [
            c for c in candidatas
            if (c.tipo == "peticion" and detectar_match_regalo(aceptados_pub, _cedidos_abiertos(c)))
            or (c.tipo == "cambio"   and bool(aceptados_pub & _cedidos_abiertos(c)))
        ]

    if tipo == "peticion":
        cedidos_pub = _cedidos_abiertos(publicacion)
        return [
            c for c in candidatas
            if (c.tipo == "regalo" and detectar_match_regalo(_aceptados(c), cedidos_pub))
            or (c.tipo == "cambio"  and bool(cedidos_pub & _aceptados(c)))
        ]

    if tipo == "cambio_dia":
        cedidos_pub = _cedidos_abiertos(publicacion)
        aceptados_pub = _aceptados(publicacion)
        return [
            c for c in candidatas
            if c.tipo == "cambio_dia" and detectar_match_directo(
                cedidos_pub, aceptados_pub,
                _cedidos_abiertos(c), _aceptados(c),
            )
        ]

    return []


def _primer_aceptado_que_cubre(pub, cedidos_contraparte):
    """Primer TurnoAceptado de pub cuya clave (fecha, franja_id) está en cedidos_contraparte.

    Si el turno tiene cualquier_franja=True basta con que la fecha coincida con
    algún cedido de la contraparte, igual que hace _aceptados() al expandir.
    """
    fechas_contraparte = frozenset(fecha for fecha, _ in cedidos_contraparte)
    for t in pub.turnos_aceptados:
        if t.cualquier_franja:
            if t.fecha in fechas_contraparte:
                return t
        elif (t.fecha, t.franja_horaria_id) in cedidos_contraparte:
            return t
    return None


def _roles_cambio_simétrico(pub_a, pub_b):
    """cambio↔cambio o junte↔junte: ambos ceden un turno al otro."""
    tc_a = _primer_cedido_que_acepta(pub_a, _aceptados(pub_b))
    tc_b = _primer_cedido_que_acepta(pub_b, _aceptados(pub_a))
    return tc_a, None, tc_b, None


def _roles_regalo_peticion(pub_a, pub_b):
    ta_a = _primer_aceptado_que_cubre(pub_a, _cedidos_abiertos(pub_b))
    tc_b = _primer_cedido_que_acepta(pub_b, _aceptados(pub_a))
    return None, ta_a, tc_b, None


def _roles_peticion_regalo(pub_a, pub_b):
    tc_a = _primer_cedido_que_acepta(pub_a, _aceptados(pub_b))
    ta_b = _primer_aceptado_que_cubre(pub_b, _cedidos_abiertos(pub_a))
    return tc_a, None, None, ta_b


def _roles_cambio_regalo(pub_a, pub_b):
    tc_a = _primer_cedido_que_acepta(pub_a, _aceptados(pub_b))
    ta_b = _primer_aceptado_que_cubre(pub_b, _cedidos_abiertos(pub_a))
    return tc_a, None, None, ta_b


def _roles_regalo_cambio(pub_a, pub_b):
    ta_a = _primer_aceptado_que_cubre(pub_a, _cedidos_abiertos(pub_b))
    tc_b = _primer_cedido_que_acepta(pub_b, _aceptados(pub_a))
    return None, ta_a, tc_b, None


def _roles_cambio_peticion(pub_a, pub_b):
    ta_a = _primer_aceptado_que_cubre(pub_a, _cedidos_abiertos(pub_b))
    tc_b = _primer_cedido_que_acepta(pub_b, _aceptados(pub_a))
    return None, ta_a, tc_b, None


def _roles_peticion_cambio(pub_a, pub_b):
    tc_a = _primer_cedido_que_acepta(pub_a, _aceptados(pub_b))
    ta_b = _primer_aceptado_que_cubre(pub_b, _cedidos_abiertos(pub_a))
    return tc_a, None, None, ta_b


_PARES_PARCIALES = frozenset({
    ("cambio", "regalo"), ("regalo", "cambio"),
    ("cambio", "peticion"), ("peticion", "cambio"),
})

# (tipo_a, tipo_b) → handler(pub_a, pub_b) → (tc_a, ta_a, tc_b, ta_b)
# Cada handler devuelve el turno cedido y aceptado que aporta cada publicación.
# None significa que esa publicación no aporta ese tipo de turno.
_ROLES_HANDLER = {
    ("cambio",     "cambio"):     _roles_cambio_simétrico,
    ("junte",      "junte"):      _roles_cambio_simétrico,
    ("cambio_dia", "cambio_dia"): _roles_cambio_simétrico,
    ("regalo",  "peticion"): _roles_regalo_peticion,
    ("peticion","regalo"):   _roles_peticion_regalo,
    ("cambio",  "regalo"):   _roles_cambio_regalo,
    ("regalo",  "cambio"):   _roles_regalo_cambio,
    ("cambio",  "peticion"): _roles_cambio_peticion,
    ("peticion","cambio"):   _roles_peticion_cambio,
}


def crear_match_directo(pub_a, pub_b):
    """Crea un MatchCambio directo (2 bandas) entre pub_a y pub_b."""
    handler = _ROLES_HANDLER.get((pub_a.tipo, pub_b.tipo))
    if handler is None:
        return None

    match = MatchCambio(tipo="directo_2", estado="propuesto")
    db.session.add(match)
    db.session.flush()

    tc_a, ta_a, tc_b, ta_b = handler(pub_a, pub_b)

    if (tc_a is None and ta_a is None) or (tc_b is None and ta_b is None):
        db.session.rollback()
        return None

    kwargs_a = {"turno_cedido_id": tc_a.id} if tc_a else {"turno_aceptado_id": ta_a.id}
    kwargs_b = {"turno_cedido_id": tc_b.id} if tc_b else {"turno_aceptado_id": ta_b.id}

    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_a.id, **kwargs_a))
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_b.id, **kwargs_b))

    db.session.add(Notificacion(usuario_id=pub_a.usuario_id, match_id=match.id, tipo="nuevo_match"))
    db.session.add(Notificacion(usuario_id=pub_b.usuario_id, match_id=match.id, tipo="nuevo_match"))
    db.session.commit()

    tipos_par = (pub_a.tipo, pub_b.tipo)
    if tipos_par in _PARES_PARCIALES:
        usuario_cambio = pub_a.usuario if pub_a.tipo == "cambio" else pub_b.usuario
        usuario_otro = pub_b.usuario if pub_a.tipo == "cambio" else pub_a.usuario
        enviar_push_condicional(usuario_cambio, "match_parcial")
        enviar_push_condicional(usuario_otro, "match")
    else:
        enviar_push_condicional(pub_b.usuario, "match")

    for pub in (pub_a, pub_b):
        registrar_evento(pub.usuario_id, "match_found", match.id)
    db.session.commit()

    return match


def _cadenas_3_existentes(pub_id):
    """Frozensets de pub_ids para cadena_3 matches activos que incluyen pub_id."""
    from sqlalchemy import select as sa_select

    match_ids = db.session.execute(
        sa_select(MatchParticipacion.match_id)
        .join(MatchCambio, MatchParticipacion.match_id == MatchCambio.id)
        .where(
            MatchParticipacion.publicacion_id == pub_id,
            MatchCambio.tipo == "cadena_3",
            MatchCambio.estado.in_(["propuesto", "confirmado_parcial"]),
        )
    ).scalars().all()

    if not match_ids:
        return set()

    rows = db.session.execute(
        sa_select(MatchParticipacion.match_id, MatchParticipacion.publicacion_id)
        .where(MatchParticipacion.match_id.in_(match_ids))
    ).all()

    agrupado = {}
    for mid, pid in rows:
        agrupado.setdefault(mid, set()).add(pid)

    return {frozenset(pubs) for pubs in agrupado.values()}


def buscar_cadenas_3_para(publicacion):
    """
    Devuelve lista de pares (pub_b, pub_c) donde publicacion→pub_b→pub_c→publicacion
    forma un ciclo de intercambio válido a 3 bandas.

    Solo opera sobre publicaciones de tipo 'cambio'.
    """
    if publicacion.tipo != "cambio":
        return []

    propietario = db.session.get(Usuario, publicacion.usuario_id)
    grupo_id = propietario.unidad.grupo_intercambio_id
    candidatas = _candidatas_base(publicacion, propietario, grupo_id)
    candidatas_cambio = [c for c in candidatas if c.tipo == "cambio"]

    cedidos_a = _cedidos_abiertos(publicacion)
    aceptados_a = _aceptados(publicacion)

    cedidos_por_pub = {c.id: _cedidos_abiertos(c) for c in candidatas_cambio}
    aceptados_por_pub = {c.id: _aceptados(c) for c in candidatas_cambio}

    existing = _cadenas_3_existentes(publicacion.id)
    resultado = []

    for pub_b in candidatas_cambio:
        cedidos_b = cedidos_por_pub[pub_b.id]
        aceptados_b = aceptados_por_pub[pub_b.id]

        if not (cedidos_a & aceptados_b):
            continue

        for pub_c in candidatas_cambio:
            if pub_c.id == pub_b.id:
                continue
            if pub_c.usuario_id == pub_b.usuario_id:
                continue

            cedidos_c = cedidos_por_pub[pub_c.id]
            aceptados_c = aceptados_por_pub[pub_c.id]

            if detectar_cadena_3(
                cedidos_a, aceptados_a,
                cedidos_b, aceptados_b,
                cedidos_c, aceptados_c,
            ):
                key = frozenset({publicacion.id, pub_b.id, pub_c.id})
                if key not in existing:
                    resultado.append((pub_b, pub_c))
                    existing.add(key)

    return resultado


def crear_match_cadena_3(pub_a, pub_b, pub_c):
    """
    Crea un MatchCambio a 3 bandas para el ciclo pub_a→pub_b→pub_c→pub_a.

    Cada participación registra el turno que ese usuario cede al siguiente
    en el ciclo.
    """
    aceptados_a = _aceptados(pub_a)
    aceptados_b = _aceptados(pub_b)
    aceptados_c = _aceptados(pub_c)

    turno_a = _primer_cedido_que_acepta(pub_a, aceptados_b)  # A cede a B
    turno_b = _primer_cedido_que_acepta(pub_b, aceptados_c)  # B cede a C
    turno_c = _primer_cedido_que_acepta(pub_c, aceptados_a)  # C cede a A

    if not turno_a or not turno_b or not turno_c:
        db.session.rollback()
        return None

    match = MatchCambio(tipo="cadena_3", estado="propuesto")
    db.session.add(match)
    db.session.flush()

    db.session.add(MatchParticipacion(
        match_id=match.id, publicacion_id=pub_a.id, turno_cedido_id=turno_a.id
    ))
    db.session.add(MatchParticipacion(
        match_id=match.id, publicacion_id=pub_b.id, turno_cedido_id=turno_b.id
    ))
    db.session.add(MatchParticipacion(
        match_id=match.id, publicacion_id=pub_c.id, turno_cedido_id=turno_c.id
    ))

    for pub in (pub_a, pub_b, pub_c):
        db.session.add(Notificacion(
            usuario_id=pub.usuario_id, match_id=match.id, tipo="nuevo_match"
        ))

    db.session.commit()

    enviar_push_condicional(pub_b.usuario, "match")
    enviar_push_condicional(pub_c.usuario, "match")

    for pub in (pub_a, pub_b, pub_c):
        registrar_evento(pub.usuario_id, "match_found", match.id)
    db.session.commit()

    return match
