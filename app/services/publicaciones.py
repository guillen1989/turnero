from app.extensions import db
from app.models import MatchCambio, MatchParticipacion, Notificacion, PublicacionCambio, SuscripcionPublicaciones, TurnoCedido, TurnoAceptado, Usuario
from app.push.sender import enviar_push_condicional
from app.services.eventos import registrar_evento



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
    """Marca la publicación como cancelada. Requiere que esté activa."""
    pub.estado = "cancelada"
    db.session.commit()
    registrar_evento(pub.usuario_id, "publication_cancelled", pub.id)
    db.session.commit()


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
    _eliminar_matches_de_publicacion(pub.id)
    db.session.delete(pub)
    db.session.commit()
