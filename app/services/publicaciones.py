from app.extensions import db
from app.models import PublicacionCambio, TurnoCedido, TurnoAceptado


def publicar_cambio(usuario_id, turnos_cedidos, turnos_aceptados):
    """
    Crea una PublicacionCambio con los turnos indicados.
    turnos_cedidos/aceptados: listas de (fecha: date, franja_horaria_id: int)
    """
    pub = PublicacionCambio(usuario_id=usuario_id)
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
