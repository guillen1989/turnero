from datetime import date

from app.extensions import db
from app.models import PublicacionCambio


def caducar_publicaciones_expiradas(hoy=None):
    """
    Marca como 'caducada' toda publicación activa cuyos turnos cedidos abiertos
    tienen todos fecha estrictamente anterior a `hoy`.

    Acepta `hoy` como parámetro para que los tests puedan fijar la fecha
    sin depender del reloj real.

    Devuelve la lista de publicaciones que han caducado en esta llamada.
    """
    if hoy is None:
        hoy = date.today()

    activas = PublicacionCambio.query.filter(
        PublicacionCambio.estado.in_(("abierta", "parcialmente_resuelta"))
    ).all()

    caducadas = []
    for pub in activas:
        turnos_abiertos = [t for t in pub.turnos_cedidos if t.estado == "abierto"]
        if turnos_abiertos and all(t.fecha < hoy for t in turnos_abiertos):
            pub.estado = "caducada"
            caducadas.append(pub)

    if caducadas:
        db.session.commit()

    return caducadas
