from app.extensions import db
from app.models import MatchCambio, MatchParticipacion, Notificacion, PublicacionCambio, TurnoCedido, TurnoAceptado


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
        db.session.add(TurnoAceptado(
            publicacion_id=pub.id,
            fecha=fecha,
            franja_horaria_id=franja_id,
        ))

    db.session.commit()
    return pub


def cancelar_publicacion(pub):
    """Marca la publicación como cancelada. Requiere que esté activa."""
    pub.estado = "cancelada"
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
        db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=fecha, franja_horaria_id=franja_id))

    pub.estado = "abierta"
    db.session.commit()
    return pub


def eliminar_publicacion(pub):
    """Borra completamente una publicación y todos sus datos asociados."""
    _eliminar_matches_de_publicacion(pub.id)
    db.session.delete(pub)
    db.session.commit()
