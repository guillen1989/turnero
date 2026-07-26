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
from app.matching.engine import (
    detectar_cadena_3,
    detectar_cadena_4,
    detectar_match_directo,
    detectar_match_regalo,
)
from app.push.sender import enviar_push_condicional
from app.services.busquedas_guardadas import notificar_busquedas_guardadas
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
    """Frozenset de (fecha, franja_id) de los turnos aceptados aún abiertos.

    Si un turno tiene cualquier_franja=True, se expande a todas las franjas
    del grupo para que haga match con cualquier turno cedido de esa fecha.
    """
    result = set()
    franjas_cache = None
    for t in pub.turnos_aceptados:
        if t.estado != "abierto":
            continue
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
            PublicacionCambio.es_sintetica.is_(False),
            Usuario.categoria_id == propietario.categoria_id,
            Unidad.grupo_intercambio_id == grupo_id,
        )
        .options(
            selectinload(PublicacionCambio.turnos_cedidos),
            selectinload(PublicacionCambio.turnos_aceptados),
        )
        .all()
    )


def candidatas_activas_para(publicacion):
    """Candidatas activas para `publicacion` (mismo grupo/categoría, mismos
    filtros que usan todas las búsquedas de matching).

    Pensada para calcularse una sola vez por publish/editar y pasarse a las
    distintas búsquedas (buscar_matches_para, buscar_cadenas_3_para, ...) en
    vez de que cada una repita la misma consulta (con sus selectinload).
    """
    propietario = db.session.get(Usuario, publicacion.usuario_id)
    grupo_id = propietario.unidad.grupo_intercambio_id
    return _candidatas_base(publicacion, propietario, grupo_id)


def _resolver_candidatas(publicacion, candidatas):
    """Devuelve `candidatas` tal cual si ya se pasaron calculadas, o las
    calcula si no (para que cada búsqueda siga funcionando de forma
    independiente cuando se llama sin ese argumento, como en los tests)."""
    if candidatas is not None:
        return candidatas
    return candidatas_activas_para(publicacion)


def buscar_matches_para(publicacion, candidatas=None):
    """
    Devuelve las publicaciones activas que hacen match con `publicacion`.

    Matches completos (bidireccionales):
      - cambio ↔ cambio, junte ↔ junte

    Matches asimétricos completos:
      - regalo ↔ peticion

    Matches parciales (un lado satisfecho):
      - cambio ↔ regalo: el regalo cubre uno de los cedidos del cambio
      - cambio ↔ peticion: la peticion cubre uno de los aceptados del cambio

    `candidatas`: opcional, ya calculadas por el llamador (ver `_resolver_candidatas`).
    """
    candidatas = _resolver_candidatas(publicacion, candidatas)

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
    """Primer TurnoAceptado abierto de pub cuya clave (fecha, franja_id) está en cedidos_contraparte.

    Si el turno tiene cualquier_franja=True basta con que la fecha coincida con
    algún cedido de la contraparte, igual que hace _aceptados() al expandir.
    """
    fechas_contraparte = frozenset(fecha for fecha, _ in cedidos_contraparte)
    for t in pub.turnos_aceptados:
        if t.estado != "abierto":
            continue
        if t.cualquier_franja:
            if t.fecha in fechas_contraparte:
                return t
        elif (t.fecha, t.franja_horaria_id) in cedidos_contraparte:
            return t
    return None


def _roles_cambio_simétrico(pub_a, pub_b):
    """cambio↔cambio o junte↔junte: ambos ceden un turno al otro."""
    aceptados_a = _aceptados(pub_a)
    aceptados_b = _aceptados(pub_b)
    tc_a = _primer_cedido_que_acepta(pub_a, aceptados_b)
    tc_b = _primer_cedido_que_acepta(pub_b, aceptados_a)
    ta_a = _primer_aceptado_que_cubre(pub_a, _cedidos_abiertos(pub_b))
    ta_b = _primer_aceptado_que_cubre(pub_b, _cedidos_abiertos(pub_a))
    return tc_a, ta_a, tc_b, ta_b


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

    kwargs_a = {}
    if tc_a:
        kwargs_a["turno_cedido_id"] = tc_a.id
    if ta_a:
        kwargs_a["turno_aceptado_id"] = ta_a.id
    kwargs_b = {}
    if tc_b:
        kwargs_b["turno_cedido_id"] = tc_b.id
    if ta_b:
        kwargs_b["turno_aceptado_id"] = ta_b.id

    if not kwargs_a or not kwargs_b:
        db.session.rollback()
        return None

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


def buscar_cadenas_3_para(publicacion, candidatas=None):
    """
    Devuelve lista de pares (pub_b, pub_c) donde publicacion→pub_b→pub_c→publicacion
    forma un ciclo de intercambio válido a 3 bandas.

    Solo opera sobre publicaciones de tipo 'cambio'.
    `candidatas`: opcional, ya calculadas por el llamador (ver `_resolver_candidatas`).
    """
    if publicacion.tipo != "cambio":
        return []

    candidatas = _resolver_candidatas(publicacion, candidatas)
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
    en el ciclo. Idempotente: si el trío ya tiene un match activo, devuelve None.
    """
    if frozenset({pub_a.id, pub_b.id, pub_c.id}) in _cadenas_3_existentes(pub_a.id):
        return None

    aceptados_a = _aceptados(pub_a)
    aceptados_b = _aceptados(pub_b)
    aceptados_c = _aceptados(pub_c)

    turno_a = _primer_cedido_que_acepta(pub_a, aceptados_b)  # A cede a B
    turno_b = _primer_cedido_que_acepta(pub_b, aceptados_c)  # B cede a C
    turno_c = _primer_cedido_que_acepta(pub_c, aceptados_a)  # C cede a A

    if not turno_a or not turno_b or not turno_c:
        db.session.rollback()
        return None

    # Turno que cada banda recibe de la anterior en el ciclo: hace falta
    # registrarlo para que confirmar_participacion pueda marcarlo resuelto.
    ta_b = _primer_aceptado_que_cubre(pub_b, frozenset({(turno_a.fecha, turno_a.franja_horaria_id)}))
    ta_c = _primer_aceptado_que_cubre(pub_c, frozenset({(turno_b.fecha, turno_b.franja_horaria_id)}))
    ta_a = _primer_aceptado_que_cubre(pub_a, frozenset({(turno_c.fecha, turno_c.franja_horaria_id)}))

    if not ta_a or not ta_b or not ta_c:
        db.session.rollback()
        return None

    match = MatchCambio(tipo="cadena_3", estado="propuesto")
    db.session.add(match)
    db.session.flush()

    db.session.add(MatchParticipacion(
        match_id=match.id, publicacion_id=pub_a.id,
        turno_cedido_id=turno_a.id, turno_aceptado_id=ta_a.id,
    ))
    db.session.add(MatchParticipacion(
        match_id=match.id, publicacion_id=pub_b.id,
        turno_cedido_id=turno_b.id, turno_aceptado_id=ta_b.id,
    ))
    db.session.add(MatchParticipacion(
        match_id=match.id, publicacion_id=pub_c.id,
        turno_cedido_id=turno_c.id, turno_aceptado_id=ta_c.id,
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


def _cadenas_4_existentes(pub_id):
    """Frozensets de pub_ids para cadena_4 matches activos que incluyen pub_id."""
    from sqlalchemy import select as sa_select

    match_ids = db.session.execute(
        sa_select(MatchParticipacion.match_id)
        .join(MatchCambio, MatchParticipacion.match_id == MatchCambio.id)
        .where(
            MatchParticipacion.publicacion_id == pub_id,
            MatchCambio.tipo == "cadena_4",
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


def buscar_cadenas_4_para(publicacion, candidatas=None):
    """
    Devuelve lista de tríos (pub_b, pub_c, pub_d) donde
    publicacion→pub_b→pub_c→pub_d→publicacion forma un ciclo de intercambio
    válido a 4 bandas.

    Solo opera sobre publicaciones de tipo 'cambio'.
    `candidatas`: opcional, ya calculadas por el llamador (ver `_resolver_candidatas`).
    """
    if publicacion.tipo != "cambio":
        return []

    candidatas = _resolver_candidatas(publicacion, candidatas)
    candidatas_cambio = [c for c in candidatas if c.tipo == "cambio"]

    cedidos_a = _cedidos_abiertos(publicacion)
    aceptados_a = _aceptados(publicacion)

    cedidos_por_pub = {c.id: _cedidos_abiertos(c) for c in candidatas_cambio}
    aceptados_por_pub = {c.id: _aceptados(c) for c in candidatas_cambio}

    existing = _cadenas_4_existentes(publicacion.id)
    resultado = []

    for pub_b in candidatas_cambio:
        cedidos_b = cedidos_por_pub[pub_b.id]
        aceptados_b = aceptados_por_pub[pub_b.id]

        if not (cedidos_a & aceptados_b):
            continue

        for pub_c in candidatas_cambio:
            if pub_c.id == pub_b.id or pub_c.usuario_id == pub_b.usuario_id:
                continue

            cedidos_c = cedidos_por_pub[pub_c.id]
            aceptados_c = aceptados_por_pub[pub_c.id]

            if not (cedidos_b & aceptados_c):
                continue

            for pub_d in candidatas_cambio:
                if pub_d.id in (pub_b.id, pub_c.id):
                    continue
                if pub_d.usuario_id in (pub_b.usuario_id, pub_c.usuario_id):
                    continue

                cedidos_d = cedidos_por_pub[pub_d.id]
                aceptados_d = aceptados_por_pub[pub_d.id]

                if detectar_cadena_4(
                    cedidos_a, aceptados_a,
                    cedidos_b, aceptados_b,
                    cedidos_c, aceptados_c,
                    cedidos_d, aceptados_d,
                ):
                    key = frozenset({publicacion.id, pub_b.id, pub_c.id, pub_d.id})
                    if key not in existing:
                        resultado.append((pub_b, pub_c, pub_d))
                        existing.add(key)

    return resultado


def crear_match_cadena_4(pub_a, pub_b, pub_c, pub_d):
    """
    Crea un MatchCambio a 4 bandas para el ciclo pub_a→pub_b→pub_c→pub_d→pub_a.

    Cada participación registra el turno que ese usuario cede al siguiente
    en el ciclo. Idempotente: si el cuarteto ya tiene un match activo, devuelve None.
    """
    if frozenset({pub_a.id, pub_b.id, pub_c.id, pub_d.id}) in _cadenas_4_existentes(pub_a.id):
        return None

    aceptados_a = _aceptados(pub_a)
    aceptados_b = _aceptados(pub_b)
    aceptados_c = _aceptados(pub_c)
    aceptados_d = _aceptados(pub_d)

    turno_a = _primer_cedido_que_acepta(pub_a, aceptados_b)  # A cede a B
    turno_b = _primer_cedido_que_acepta(pub_b, aceptados_c)  # B cede a C
    turno_c = _primer_cedido_que_acepta(pub_c, aceptados_d)  # C cede a D
    turno_d = _primer_cedido_que_acepta(pub_d, aceptados_a)  # D cede a A

    if not turno_a or not turno_b or not turno_c or not turno_d:
        db.session.rollback()
        return None

    # Turno que cada banda recibe de la anterior en el ciclo: hace falta
    # registrarlo para que confirmar_participacion pueda marcarlo resuelto.
    ta_b = _primer_aceptado_que_cubre(pub_b, frozenset({(turno_a.fecha, turno_a.franja_horaria_id)}))
    ta_c = _primer_aceptado_que_cubre(pub_c, frozenset({(turno_b.fecha, turno_b.franja_horaria_id)}))
    ta_d = _primer_aceptado_que_cubre(pub_d, frozenset({(turno_c.fecha, turno_c.franja_horaria_id)}))
    ta_a = _primer_aceptado_que_cubre(pub_a, frozenset({(turno_d.fecha, turno_d.franja_horaria_id)}))

    if not ta_a or not ta_b or not ta_c or not ta_d:
        db.session.rollback()
        return None

    match = MatchCambio(tipo="cadena_4", estado="propuesto")
    db.session.add(match)
    db.session.flush()

    db.session.add(MatchParticipacion(
        match_id=match.id, publicacion_id=pub_a.id,
        turno_cedido_id=turno_a.id, turno_aceptado_id=ta_a.id,
    ))
    db.session.add(MatchParticipacion(
        match_id=match.id, publicacion_id=pub_b.id,
        turno_cedido_id=turno_b.id, turno_aceptado_id=ta_b.id,
    ))
    db.session.add(MatchParticipacion(
        match_id=match.id, publicacion_id=pub_c.id,
        turno_cedido_id=turno_c.id, turno_aceptado_id=ta_c.id,
    ))
    db.session.add(MatchParticipacion(
        match_id=match.id, publicacion_id=pub_d.id,
        turno_cedido_id=turno_d.id, turno_aceptado_id=ta_d.id,
    ))

    for pub in (pub_a, pub_b, pub_c, pub_d):
        db.session.add(Notificacion(
            usuario_id=pub.usuario_id, match_id=match.id, tipo="nuevo_match"
        ))

    db.session.commit()

    enviar_push_condicional(pub_b.usuario, "match")
    enviar_push_condicional(pub_c.usuario, "match")
    enviar_push_condicional(pub_d.usuario, "match")

    for pub in (pub_a, pub_b, pub_c, pub_d):
        registrar_evento(pub.usuario_id, "match_found", match.id)
    db.session.commit()

    return match


def buscar_cadenas_parciales_4_para(publicacion, candidatas=None):
    """
    Devuelve lista de tríos (pub_a, pub_b, pub_c) donde pub_a→pub_b→pub_c
    cierra 2 de los 3 eslabones de un ciclo sin cerrar el tercero (pub_c→pub_a):
    si cerrara sería ya una cadena_3 completa, no un hueco de cadena_4.
    `publicacion` participa en el trío, pero no necesariamente como pub_a:
    a diferencia de un ciclo cerrado (con simetría rotacional), un camino
    abierto A→B→C no es simétrico, así que hay que buscar `publicacion` en
    sus 3 posibles posiciones (primera, intermedia o última) para que el
    hueco se detecte sin importar qué banda del trío publique o edite la
    última.

    Estos tríos son la base para generar una publicación sintética que
    represente al cuarto usuario que falta. Solo opera sobre publicaciones
    de tipo 'cambio'.
    `candidatas`: opcional, ya calculadas por el llamador (ver `_resolver_candidatas`).
    """
    if publicacion.tipo != "cambio":
        return []

    candidatas = _resolver_candidatas(publicacion, candidatas)
    candidatas_cambio = [c for c in candidatas if c.tipo == "cambio"]

    cedidos_pub = _cedidos_abiertos(publicacion)
    aceptados_pub = _aceptados(publicacion)

    cedidos_por_pub = {c.id: _cedidos_abiertos(c) for c in candidatas_cambio}
    aceptados_por_pub = {c.id: _aceptados(c) for c in candidatas_cambio}

    def _distintos(pub_x, pub_y):
        return pub_x.id != pub_y.id and pub_x.usuario_id != pub_y.usuario_id

    resultado = []

    # Rol A: publicacion→x→y, sin que y cierre de vuelta con publicacion.
    for pub_x in candidatas_cambio:
        if not (cedidos_pub & aceptados_por_pub[pub_x.id]):
            continue
        for pub_y in candidatas_cambio:
            if not _distintos(pub_x, pub_y):
                continue
            if not (cedidos_por_pub[pub_x.id] & aceptados_por_pub[pub_y.id]):
                continue
            if cedidos_por_pub[pub_y.id] & aceptados_pub:
                continue
            resultado.append((publicacion, pub_x, pub_y))

    # Rol B (intermedio): x→publicacion→y, sin que y cierre de vuelta con x.
    for pub_x in candidatas_cambio:
        if not (cedidos_por_pub[pub_x.id] & aceptados_pub):
            continue
        for pub_y in candidatas_cambio:
            if not _distintos(pub_x, pub_y):
                continue
            if not (cedidos_pub & aceptados_por_pub[pub_y.id]):
                continue
            if cedidos_por_pub[pub_y.id] & aceptados_por_pub[pub_x.id]:
                continue
            resultado.append((pub_x, publicacion, pub_y))

    # Rol C (última): x→y→publicacion, sin que publicacion cierre de vuelta con x.
    for pub_x in candidatas_cambio:
        for pub_y in candidatas_cambio:
            if not _distintos(pub_x, pub_y):
                continue
            if not (cedidos_por_pub[pub_x.id] & aceptados_por_pub[pub_y.id]):
                continue
            if not (cedidos_por_pub[pub_y.id] & aceptados_pub):
                continue
            if cedidos_pub & aceptados_por_pub[pub_x.id]:
                continue
            resultado.append((pub_x, pub_y, publicacion))

    return resultado


def buscar_avisos_interes_para(publicacion, candidatas=None):
    """
    Devuelve publicaciones cambio con solapamiento unilateral respecto a `publicacion`.

    Una sola dirección cuadra (A puede dar a B lo que B quiere, o viceversa) pero
    no la otra, por lo que no puede formarse un match directo. Se notifica a ambas
    partes para que puedan ampliar sus aceptados o explorar cadenas.
    Solo opera sobre publicaciones de tipo 'cambio'.
    `candidatas`: opcional, ya calculadas por el llamador (ver `_resolver_candidatas`).
    """
    if publicacion.tipo != "cambio":
        return []

    candidatas = _resolver_candidatas(publicacion, candidatas)

    cedidos_pub = _cedidos_abiertos(publicacion)
    aceptados_pub = _aceptados(publicacion)

    resultado = []
    for c in candidatas:
        if c.tipo != "cambio":
            continue
        cedidos_c = _cedidos_abiertos(c)
        aceptados_c = _aceptados(c)
        a_da_a_b = bool(cedidos_pub & aceptados_c)
        b_da_a_a = bool(cedidos_c & aceptados_pub)
        if a_da_a_b ^ b_da_a_a:
            resultado.append(c)
    return resultado



def crear_aviso_oportunidad_4(pub_a, pub_b, pub_c):
    """
    Crea una Notificacion combinada de tipo 'aviso_oportunidad_4' para cada
    uno de los 3 usuarios reales del trío A→B→C (falta un cuarto para
    cerrar el ciclo). Cada destinatario referencia al siguiente en el
    ciclo.
    Idempotente: no duplica si ya existe para el mismo trío.
    """
    for destinatario_id, pub_ref in (
        (pub_a.usuario_id, pub_b),
        (pub_b.usuario_id, pub_c),
        (pub_c.usuario_id, pub_a),
    ):
        existe = Notificacion.query.filter_by(
            usuario_id=destinatario_id,
            publicacion_id=pub_ref.id,
            tipo="aviso_oportunidad_4",
        ).first()
        if not existe:
            db.session.add(Notificacion(
                usuario_id=destinatario_id,
                publicacion_id=pub_ref.id,
                tipo="aviso_oportunidad_4",
            ))
    db.session.commit()

    enviar_push_condicional(pub_a.usuario, "aviso_oportunidad_4")
    enviar_push_condicional(pub_b.usuario, "aviso_oportunidad_4")
    enviar_push_condicional(pub_c.usuario, "aviso_oportunidad_4")


def procesar_cadena_parcial_4(pub_a, pub_b, pub_c):
    """
    Crea la pub sintética (con pub_b como intermedio) y el aviso combinado
    para un trío pub_a→pub_b→pub_c que cierra 2 de los 3 eslabones de un
    hueco de cadena_4. La dirección ya viene resuelta por
    buscar_cadenas_parciales_4_para, a diferencia de procesar_aviso_y_sintetica.
    """
    crear_pub_sintetica(pub_a, pub_c, pub_intermedio=pub_b)
    crear_aviso_oportunidad_4(pub_a, pub_b, pub_c)


def procesar_aviso_y_sintetica(pub, candidata):
    """
    Crea la pub sintética para un par (pub, candidata) con solapamiento
    unilateral. Determina automáticamente la dirección A→B.
    """
    cedidos_pub = _cedidos_abiertos(pub)
    aceptados_candidata = _aceptados(candidata)
    if bool(cedidos_pub & aceptados_candidata):
        # candidata acepta el cedido de pub → pub=A, candidata=B
        crear_pub_sintetica(pub, candidata)
    else:
        # pub acepta el cedido de candidata → candidata=A, pub=B
        crear_pub_sintetica(candidata, pub)


def crear_pub_sintetica(pub_a, pub_b, pub_intermedio=None):
    """
    Crea una PublicacionCambio sintética que cierra el hueco entre pub_a y pub_b.

    Regla de construcción (misma para cadena_3 y cadena_4, solo depende de
    los dos extremos del hueco):
      cedido_sintética  = aceptados abiertos de pub_a  (A cubriría esos turnos para C)
      acepta_sintética  = cedidos  abiertos de pub_b  (C cubriría esos turnos para B)

    pub_intermedio: solo para cadena_4. Es la banda real "B" del trío
    A→B→C ya cerrado; se guarda para poder reconstruir el ciclo completo
    cuando un cuarto usuario cierre la sintética. None (por defecto) para
    sintéticas de cadena_3.

    Propietario = usuario de pub_a.
    Idempotente: si ya existe una sintética activa para este trío (mismos
    pub_a, pub_b y pub_intermedio), la devuelve sin crear otra.
    """
    from app.models import TurnoCedido as TC, TurnoAceptado as TA

    intermedio_id = pub_intermedio.id if pub_intermedio else None
    existente = PublicacionCambio.query.filter(
        PublicacionCambio.sintetica_pub_a_id == pub_a.id,
        PublicacionCambio.sintetica_pub_b_id == pub_b.id,
        PublicacionCambio.sintetica_pub_intermedio_id == intermedio_id,
        PublicacionCambio.estado.in_(("abierta", "parcialmente_resuelta")),
    ).first()
    if existente:
        return existente

    sint = PublicacionCambio(
        usuario_id=pub_a.usuario_id,
        tipo="cambio",
        es_sintetica=True,
        sintetica_pub_a_id=pub_a.id,
        sintetica_pub_b_id=pub_b.id,
        sintetica_pub_intermedio_id=intermedio_id,
    )
    db.session.add(sint)
    db.session.flush()

    for ta in pub_a.turnos_aceptados:
        if ta.estado != "abierto":
            continue
        if ta.cualquier_franja:
            for fid in _franjas_del_grupo(pub_a):
                db.session.add(TC(
                    publicacion_id=sint.id, fecha=ta.fecha, franja_horaria_id=fid
                ))
        else:
            db.session.add(TC(
                publicacion_id=sint.id,
                fecha=ta.fecha,
                franja_horaria_id=ta.franja_horaria_id,
            ))

    for tc in pub_b.turnos_cedidos:
        if tc.estado != "abierto":
            continue
        db.session.add(TA(
            publicacion_id=sint.id,
            fecha=tc.fecha,
            franja_horaria_id=tc.franja_horaria_id,
        ))

    db.session.commit()

    notificar_busquedas_guardadas(sint)

    return sint


def buscar_sinteticas_que_coinciden_con(publicacion):
    """
    Devuelve publicaciones sintéticas activas con las que `publicacion` forma
    un match directo (ambas direcciones cubiertas).

    Cuando una pub sintética coincide con `publicacion`, la cadena a 3 está
    completa y se puede crear el MatchCambio cadena_3.
    """
    if publicacion.tipo != "cambio":
        return []

    propietario = db.session.get(Usuario, publicacion.usuario_id)
    grupo_id = propietario.unidad.grupo_intercambio_id

    sinteticas = (
        PublicacionCambio.query
        .join(Usuario, PublicacionCambio.usuario_id == Usuario.id)
        .join(Unidad, Usuario.unidad_id == Unidad.id)
        .filter(
            PublicacionCambio.es_sintetica.is_(True),
            PublicacionCambio.estado.in_(("abierta", "parcialmente_resuelta")),
            PublicacionCambio.usuario_id != propietario.id,
            Usuario.categoria_id == propietario.categoria_id,
            Unidad.grupo_intercambio_id == grupo_id,
        )
        .options(
            selectinload(PublicacionCambio.turnos_cedidos),
            selectinload(PublicacionCambio.turnos_aceptados),
        )
        .all()
    )

    cedidos_pub = _cedidos_abiertos(publicacion)
    aceptados_pub = _aceptados(publicacion)

    # La sintética tiene:
    #   cedido  = aceptados_A  (días que C libraría, cubiertos por A)
    #   acepta  = cedido_B     (días que C trabajaría para B)
    # C cierra el triángulo si:
    #   • C quiere librar algún día que la sintética también "libra" (cedidos solapan)
    #   • C está dispuesto a trabajar algún día que la sintética "acepta" (aceptados solapan)
    return [
        s for s in sinteticas
        if bool(cedidos_pub & _cedidos_abiertos(s)) and bool(aceptados_pub & _aceptados(s))
    ]


def crear_cadena_3_desde_sintetica(pub_c, pub_sintetica):
    """
    Crea un MatchCambio cadena_3 entre pub_a, pub_b y pub_c usando la
    pub_sintetica como puente para recuperar pub_a y pub_b.
    Cancela la pub_sintetica al finalizar.
    """
    pub_a = db.session.get(PublicacionCambio, pub_sintetica.sintetica_pub_a_id)
    pub_b = db.session.get(PublicacionCambio, pub_sintetica.sintetica_pub_b_id)

    if not pub_a or not pub_b:
        return None
    if not pub_a.esta_activa() or not pub_b.esta_activa():
        return None

    match = crear_match_cadena_3(pub_a, pub_b, pub_c)
    if match:
        pub_sintetica.estado = "cancelada"
        db.session.commit()
    return match


def crear_cadena_4_desde_sintetica(pub_d, pub_sintetica):
    """
    Crea un MatchCambio cadena_4 entre pub_a, pub_b (intermedio), pub_c y
    pub_d usando la pub_sintetica como puente para recuperar el trío real
    A→B→C. Cancela la pub_sintetica al finalizar.
    """
    pub_a = db.session.get(PublicacionCambio, pub_sintetica.sintetica_pub_a_id)
    pub_b = db.session.get(PublicacionCambio, pub_sintetica.sintetica_pub_intermedio_id)
    pub_c = db.session.get(PublicacionCambio, pub_sintetica.sintetica_pub_b_id)

    if not pub_a or not pub_b or not pub_c:
        return None
    if not pub_a.esta_activa() or not pub_b.esta_activa() or not pub_c.esta_activa():
        return None

    match = crear_match_cadena_4(pub_a, pub_b, pub_c, pub_d)
    if match:
        pub_sintetica.estado = "cancelada"
        db.session.commit()
    return match
