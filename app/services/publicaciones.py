from app.extensions import db
from app.models import AuditEliminacion, MatchCambio, MatchParticipacion, Notificacion, PublicacionCambio, SuscripcionPublicaciones, TurnoCedido, TurnoAceptado, Usuario
from app.push.sender import enviar_push_condicional
from app.services.eventos import registrar_evento
from app.services.busquedas_guardadas import notificar_busquedas_guardadas



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
    pub.estado = "cancelada"
    _cancelar_sinteticas_de(pub.id)
    db.session.commit()
    registrar_evento(pub.usuario_id, "publication_cancelled", pub.id)
    db.session.commit()


def _cancelar_sinteticas_de(pub_id):
    """Cancela todas las pubs sintéticas que dependen de pub_id."""
    from sqlalchemy import or_
    dependientes = PublicacionCambio.query.filter(
        PublicacionCambio.es_sintetica.is_(True),
        PublicacionCambio.estado.in_(("abierta", "parcialmente_resuelta")),
        or_(
            PublicacionCambio.sintetica_pub_a_id == pub_id,
            PublicacionCambio.sintetica_pub_b_id == pub_id,
        ),
    ).all()
    for sint in dependientes:
        sint.estado = "cancelada"


def _eliminar_matches_de_publicacion(pub_id):
    """Borra los matches (y sus notificaciones) que involucran esta publicación."""
    matches = (
        MatchCambio.query
        .join(MatchParticipacion)
        .filter(MatchParticipacion.publicacion_id == pub_id)
        .all()
    )
    for match in matches:
        Notificacion.query.filter_by(match_id=match.id).delete()
        db.session.delete(match)
    # Flush antes de continuar: garantiza que MatchParticipacion (que puede referenciar
    # TurnoAceptado via turno_aceptado_id) se elimine antes que TurnoAceptado.
    db.session.flush()


def editar_publicacion(pub, turnos_cedidos, turnos_aceptados, mensaje=None, tipo=None):
    """
    Reemplaza los turnos de una publicación activa y recalcula matches.
    turnos_cedidos/aceptados: listas de (fecha: date, franja_horaria_id: int)
    """
    _cancelar_sinteticas_de(pub.id)
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


def eliminar_publicacion(pub):
    """Borra completamente una publicación y todos sus datos asociados."""
    unidad_id = pub.usuario.unidad_id if pub.usuario else None
    _cancelar_sinteticas_de(pub.id)
    _eliminar_matches_de_publicacion(pub.id)
    Notificacion.query.filter_by(publicacion_id=pub.id).delete()
    db.session.delete(pub)
    db.session.add(AuditEliminacion(unidad_id=unidad_id))
    db.session.commit()
