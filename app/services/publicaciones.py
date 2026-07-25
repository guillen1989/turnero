from app.extensions import db
from app.models import AuditEliminacion, MatchCambio, MatchParticipacion, Notificacion, PublicacionCambio, SuscripcionPublicaciones, TurnoCedido, TurnoAceptado, Usuario
from app.push.sender import enviar_push_condicional
from app.services.eventos import registrar_evento
from app.services.busquedas_guardadas import notificar_busquedas_guardadas

_ESTADOS_MATCH_ACTIVOS = ("propuesto", "confirmado_parcial")



def publicar_cambio(usuario_id, turnos_cedidos, turnos_aceptados, mensaje=None, tipo="cambio"):
    """
    Crea una PublicacionCambio con los turnos indicados.
    turnos_cedidos/aceptados: listas de (fecha: date, franja_horaria_id: int)
    tipo: 'cambio' | 'regalo' | 'peticion'
    """
    pub = PublicacionCambio(usuario_id=usuario_id, mensaje=mensaje or None, tipo=tipo)
    db.session.add(pub)
    db.session.flush()

    for fecha, franja_id in turnos_cedidos:
        db.session.add(TurnoCedido(
            publicacion_id=pub.id,
            fecha=fecha,
            franja_horaria_id=franja_id,
        ))

    for fecha, franja_id in turnos_aceptados:
        cualquier = franja_id is None
        db.session.add(TurnoAceptado(
            publicacion_id=pub.id,
            fecha=fecha,
            franja_horaria_id=None if cualquier else franja_id,
            cualquier_franja=cualquier,
        ))

    db.session.commit()
    registrar_evento(usuario_id, "publication_created", pub.id)
    db.session.commit()

    publicador = db.session.get(Usuario, usuario_id)
    _notificar_suscriptores(publicador, pub)
    notificar_busquedas_guardadas(pub)

    return pub


def _notificar_suscriptores(publicador, pub):
    """Crea notificaciones in-app y envía push a los suscriptores del publicador."""
    suscripciones = SuscripcionPublicaciones.query.filter_by(publicador_id=publicador.id).all()
    if not suscripciones:
        return

    ids = [s.suscriptor_id for s in suscripciones]
    suscriptores = {u.id: u for u in Usuario.query.filter(Usuario.id.in_(ids)).all()}

    for suscripcion in suscripciones:
        suscriptor = suscriptores.get(suscripcion.suscriptor_id)
        if suscriptor:
            db.session.add(Notificacion(
                usuario_id=suscriptor.id,
                publicacion_id=pub.id,
                tipo="nueva_publicacion_seguido",
            ))
            enviar_push_condicional(suscriptor, "publicacion")
    db.session.commit()


def cancelar_publicacion(pub):
    """Marca la publicación como cancelada y propaga la cancelación a las sintéticas
    que la referencian como pub_a o pub_b."""
    _rechazar_matches_activos_de_publicacion(pub)
    pub.estado = "cancelada"
    _cancelar_sinteticas_de(pub.id)
    db.session.commit()
    registrar_evento(pub.usuario_id, "publication_cancelled", pub.id)
    db.session.commit()


def _rechazar_matches_activos_de_publicacion(pub):
    """Rechaza (marca 'rechazado', notifica a la contraparte y registra evento)
    los matches todavía activos (propuesto/confirmado_parcial) de esta publicación.

    Sin esto, cancelar/editar/eliminar una publicación dejaba a la contraparte con
    un match huérfano (al cancelar) o lo borraba de la BD en silencio y sin avisar
    (al editar/eliminar), rompiendo confirmaciones ya hechas por la otra parte.
    """
    from app.services.matches import rechazar_match

    matches_activos = (
        MatchCambio.query
        .join(MatchParticipacion)
        .filter(
            MatchParticipacion.publicacion_id == pub.id,
            MatchCambio.estado.in_(_ESTADOS_MATCH_ACTIVOS),
        )
        .distinct()
        .all()
    )
    for match in matches_activos:
        rechazar_match(match, pub.usuario_id)


def _cancelar_sinteticas_de(pub_id):
    """Cancela todas las pubs sintéticas que dependen de pub_id.

    Incluye sintetica_pub_intermedio_id: en una sintética de cadena_4 esa
    columna guarda la banda real intermedia del trío (B), que también debe
    invalidar la sintética si cancela su publicación.

    UPDATE en bloque (no una fila por sintética en un bucle Python): una
    publicación puede tener cientos de sintéticas dependientes (motor de
    matching sin límite de generación) y un bucle con una consulta o
    actualización por fila multiplicaba los tiempos de respuesta por ese
    número de sintéticas.
    """
    from sqlalchemy import or_
    PublicacionCambio.query.filter(
        PublicacionCambio.es_sintetica.is_(True),
        PublicacionCambio.estado.in_(("abierta", "parcialmente_resuelta")),
        or_(
            PublicacionCambio.sintetica_pub_a_id == pub_id,
            PublicacionCambio.sintetica_pub_b_id == pub_id,
            PublicacionCambio.sintetica_pub_intermedio_id == pub_id,
        ),
    ).update({"estado": "cancelada"}, synchronize_session=False)


def _eliminar_matches_de_publicaciones(pub_ids):
    """Desvincula las publicaciones de `pub_ids` de cualquier match que las
    involucre, para poder borrarlas/reemplazar sus turnos sin violar la FK de
    MatchParticipacion.

    Solo borra el MatchCambio (y sus notificaciones) por completo si se queda
    sin ninguna otra participación; si el match tenía más partes (p. ej. un
    rechazo ya registrado por `_rechazar_matches_activos_de_publicacion` para
    la contraparte), el match y su notificación de rechazo se preservan como
    historial.

    Versión en bloque (acepta una lista de ids): antes se llamaba una vez por
    publicación en un bucle Python al eliminar las sintéticas dependientes de
    una publicación, lo que suponía varias consultas secuenciales por cada
    una (hasta 225 sintéticas vistas en producción, causando un WORKER
    TIMEOUT de gunicorn al eliminar). Con `synchronize_session=False` porque
    los objetos borrados no se vuelven a usar en la sesión tras esta función.
    """
    if not pub_ids:
        return

    match_ids = {
        row.match_id for row in
        MatchParticipacion.query
        .filter(MatchParticipacion.publicacion_id.in_(pub_ids))
        .with_entities(MatchParticipacion.match_id)
        .all()
    }
    MatchParticipacion.query.filter(
        MatchParticipacion.publicacion_id.in_(pub_ids)
    ).delete(synchronize_session=False)
    # Flush antes de continuar: garantiza que MatchParticipacion (que puede referenciar
    # TurnoAceptado via turno_aceptado_id) se elimine antes que TurnoAceptado.
    db.session.flush()

    if match_ids:
        con_participaciones = {
            row.match_id for row in
            MatchParticipacion.query
            .filter(MatchParticipacion.match_id.in_(match_ids))
            .with_entities(MatchParticipacion.match_id)
            .distinct()
            .all()
        }
        huerfanos = match_ids - con_participaciones
        if huerfanos:
            Notificacion.query.filter(
                Notificacion.match_id.in_(huerfanos)
            ).delete(synchronize_session=False)
            MatchCambio.query.filter(
                MatchCambio.id.in_(huerfanos)
            ).delete(synchronize_session=False)
    db.session.flush()


def _eliminar_matches_de_publicacion(pub_id):
    """Ver `_eliminar_matches_de_publicaciones`: versión para una sola publicación."""
    _eliminar_matches_de_publicaciones([pub_id])


def editar_publicacion(pub, turnos_cedidos, turnos_aceptados, mensaje=None, tipo=None):
    """
    Reemplaza los turnos de una publicación activa y recalcula matches.
    turnos_cedidos/aceptados: listas de (fecha: date, franja_horaria_id: int)
    """
    _cancelar_sinteticas_de(pub.id)
    _rechazar_matches_activos_de_publicacion(pub)
    _eliminar_matches_de_publicacion(pub.id)

    for tc in list(pub.turnos_cedidos):
        db.session.delete(tc)
    for ta in list(pub.turnos_aceptados):
        db.session.delete(ta)
    db.session.flush()

    pub.mensaje = mensaje or None
    if tipo is not None:
        pub.tipo = tipo
    for fecha, franja_id in turnos_cedidos:
        db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=fecha, franja_horaria_id=franja_id))
    for fecha, franja_id in turnos_aceptados:
        cualquier = franja_id is None
        db.session.add(TurnoAceptado(
            publicacion_id=pub.id, fecha=fecha,
            franja_horaria_id=None if cualquier else franja_id,
            cualquier_franja=cualquier,
        ))

    pub.estado = "abierta"
    db.session.commit()
    return pub


def _eliminar_sinteticas_de(pub_id):
    """Elimina físicamente todas las sintéticas que referencian pub_id (cualquier estado).

    _cancelar_sinteticas_de solo marca estado='cancelada' pero las filas siguen
    en DB referenciando la pub padre via FK, lo que bloquea el DELETE posterior.

    En bloque (no una sintética a la vez en un bucle Python): una publicación
    puede tener cientos de sintéticas dependientes, y hacer una tanda de
    consultas/deletes por cada una provocaba un WORKER TIMEOUT de gunicorn al
    eliminar. TurnoCedido/TurnoAceptado se borran explícitamente porque su FK
    a publicacion_cambio no tiene ondelete=CASCADE a nivel de BD (el
    cascade="all, delete-orphan" del modelo es solo de ORM y no actúa en
    deletes en bloque).
    """
    from sqlalchemy import or_
    sint_ids = [
        row.id for row in
        PublicacionCambio.query.filter(
            PublicacionCambio.es_sintetica.is_(True),
            or_(
                PublicacionCambio.sintetica_pub_a_id == pub_id,
                PublicacionCambio.sintetica_pub_b_id == pub_id,
                PublicacionCambio.sintetica_pub_intermedio_id == pub_id,
            ),
        )
        .with_entities(PublicacionCambio.id)
        .all()
    ]
    if not sint_ids:
        return

    _eliminar_matches_de_publicaciones(sint_ids)
    Notificacion.query.filter(
        Notificacion.publicacion_id.in_(sint_ids)
    ).delete(synchronize_session=False)
    TurnoCedido.query.filter(
        TurnoCedido.publicacion_id.in_(sint_ids)
    ).delete(synchronize_session=False)
    TurnoAceptado.query.filter(
        TurnoAceptado.publicacion_id.in_(sint_ids)
    ).delete(synchronize_session=False)
    PublicacionCambio.query.filter(
        PublicacionCambio.id.in_(sint_ids)
    ).delete(synchronize_session=False)
    db.session.flush()


def eliminar_publicacion(pub):
    """Borra completamente una publicación y todos sus datos asociados."""
    unidad_id = pub.usuario.unidad_id if pub.usuario else None
    _eliminar_sinteticas_de(pub.id)
    _rechazar_matches_activos_de_publicacion(pub)
    _eliminar_matches_de_publicacion(pub.id)
    Notificacion.query.filter_by(publicacion_id=pub.id).delete()
    db.session.delete(pub)
    db.session.add(AuditEliminacion(unidad_id=unidad_id))
    db.session.commit()
