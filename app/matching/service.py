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
from app.matching.engine import detectar_match_directo, detectar_match_regalo
from app.push.sender import enviar_push
from app.services.email import enviar_aviso_match


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
    """Consulta base de candidatas activas del mismo grupo y categoría."""
    return (
        PublicacionCambio.query
        .join(Usuario, PublicacionCambio.usuario_id == Usuario.id)
        .join(Unidad, Usuario.unidad_id == Unidad.id)
        .filter(
            PublicacionCambio.id != publicacion.id,
            PublicacionCambio.estado.in_(("abierta", "parcialmente_resuelta")),
            Usuario.categoria_id == propietario.categoria_id,
            Unidad.grupo_intercambio_id == grupo_id,
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


def crear_match_directo(pub_a, pub_b):
    """
    Crea un MatchCambio directo (2 bandas) entre pub_a y pub_b.

    Soporta los tres tipos de publicación:
    - cambio ↔ cambio: intercambio clásico, ambos ceden turno.
    - regalo ↔ peticion: regalo da (turno_aceptado), peticion recibe (turno_cedido).
    """
    match = MatchCambio(tipo="directo_2", estado="propuesto")
    db.session.add(match)
    db.session.flush()

    tipo_a = pub_a.tipo
    tipo_b = pub_b.tipo

    if tipo_a in ("cambio", "junte") and tipo_a == tipo_b:
        aceptados_a = _aceptados(pub_a)
        aceptados_b = _aceptados(pub_b)
        turno_a = _primer_cedido_que_acepta(pub_a, aceptados_b)
        turno_b = _primer_cedido_que_acepta(pub_b, aceptados_a)
        if not turno_a or not turno_b:
            db.session.rollback()
            return None
        db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_a.id, turno_cedido_id=turno_a.id))
        db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_b.id, turno_cedido_id=turno_b.id))

    elif tipo_a == "regalo" and tipo_b == "peticion":
        ta = _primer_aceptado_que_cubre(pub_a, _cedidos_abiertos(pub_b))
        tc = _primer_cedido_que_acepta(pub_b, _aceptados(pub_a))
        if not ta or not tc:
            db.session.rollback()
            return None
        db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_a.id, turno_aceptado_id=ta.id))
        db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_b.id, turno_cedido_id=tc.id))

    elif tipo_a == "peticion" and tipo_b == "regalo":
        tc = _primer_cedido_que_acepta(pub_a, _aceptados(pub_b))
        ta = _primer_aceptado_que_cubre(pub_b, _cedidos_abiertos(pub_a))
        if not tc or not ta:
            db.session.rollback()
            return None
        db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_a.id, turno_cedido_id=tc.id))
        db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_b.id, turno_aceptado_id=ta.id))

    # Matches parciales cambio ↔ regalo/peticion
    elif tipo_a == "cambio" and tipo_b == "regalo":
        tc = _primer_cedido_que_acepta(pub_a, _aceptados(pub_b))
        ta = _primer_aceptado_que_cubre(pub_b, _cedidos_abiertos(pub_a))
        if not tc or not ta:
            db.session.rollback()
            return None
        db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_a.id, turno_cedido_id=tc.id))
        db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_b.id, turno_aceptado_id=ta.id))

    elif tipo_a == "regalo" and tipo_b == "cambio":
        ta = _primer_aceptado_que_cubre(pub_a, _cedidos_abiertos(pub_b))
        tc = _primer_cedido_que_acepta(pub_b, _aceptados(pub_a))
        if not ta or not tc:
            db.session.rollback()
            return None
        db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_a.id, turno_aceptado_id=ta.id))
        db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_b.id, turno_cedido_id=tc.id))

    elif tipo_a == "cambio" and tipo_b == "peticion":
        ta = _primer_aceptado_que_cubre(pub_a, _cedidos_abiertos(pub_b))
        tc = _primer_cedido_que_acepta(pub_b, _aceptados(pub_a))
        if not ta or not tc:
            db.session.rollback()
            return None
        db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_a.id, turno_aceptado_id=ta.id))
        db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_b.id, turno_cedido_id=tc.id))

    elif tipo_a == "peticion" and tipo_b == "cambio":
        tc = _primer_cedido_que_acepta(pub_a, _aceptados(pub_b))
        ta = _primer_aceptado_que_cubre(pub_b, _cedidos_abiertos(pub_a))
        if not tc or not ta:
            db.session.rollback()
            return None
        db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_a.id, turno_cedido_id=tc.id))
        db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_b.id, turno_aceptado_id=ta.id))

    db.session.add(Notificacion(usuario_id=pub_a.usuario_id, match_id=match.id, tipo="nuevo_match"))
    db.session.add(Notificacion(usuario_id=pub_b.usuario_id, match_id=match.id, tipo="nuevo_match"))
    db.session.commit()

    enviar_push(pub_a.usuario, "Nuevo cambio disponible", "Tienes un posible cambio de turno.")
    enviar_push(pub_b.usuario, "Nuevo cambio disponible", "Tienes un posible cambio de turno.")

    enviar_aviso_match(pub_a.usuario, pub_a)
    enviar_aviso_match(pub_b.usuario, pub_b)

    return match
