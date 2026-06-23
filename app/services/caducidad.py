from datetime import date

from flask import current_app
from sqlalchemy import exists, select as sa_select, update as sa_update

from app.extensions import db
from app.models import PublicacionCambio, TurnoCedido, TurnoAceptado

# Fecha de la última ejecución en este proceso. Con un único worker de gunicorn
# esto evita repetir el UPDATE en cada request del mismo día calendario.
_ultima_caducidad: date | None = None


def caducar_publicaciones_expiradas(hoy=None):
    """
    Marca como 'caducada' toda publicación activa cuyos turnos relevantes
    tienen todos fecha estrictamente anterior a `hoy`.

    Ejecuta dos UPDATE SQL directos sin cargar objetos en memoria:
    - Para cambio/peticion/junte: caduca si no queda ningún turno cedido
      abierto con fecha >= hoy (pero sí existe al menos uno).
    - Para regalo: caduca si no queda ningún turno aceptado con fecha >= hoy.

    Acepta `hoy` como parámetro para que los tests puedan fijar la fecha.
    Cuando se llama sin parámetro (producción) se ejecuta como mucho una vez
    por día calendario en el mismo proceso.
    Devuelve el número total de publicaciones caducadas.
    """
    global _ultima_caducidad
    hoy_real = hoy if hoy is not None else date.today()

    # En producción evita repetir el UPDATE más de una vez por día.
    # En tests (hoy explícito o TESTING=True) siempre ejecuta.
    testing = current_app.config.get("TESTING", False)
    if hoy is None and not testing and _ultima_caducidad == hoy_real:
        return 0

    tiene_cedido_abierto = exists(
        sa_select(TurnoCedido.id).where(
            TurnoCedido.publicacion_id == PublicacionCambio.id,
            TurnoCedido.estado == "abierto",
        )
    )
    tiene_cedido_vigente = exists(
        sa_select(TurnoCedido.id).where(
            TurnoCedido.publicacion_id == PublicacionCambio.id,
            TurnoCedido.estado == "abierto",
            TurnoCedido.fecha >= hoy_real,
        )
    )
    stmt_cedidos = (
        sa_update(PublicacionCambio)
        .where(
            PublicacionCambio.estado.in_(("abierta", "parcialmente_resuelta")),
            PublicacionCambio.tipo.in_(("cambio", "peticion", "junte")),
            tiene_cedido_abierto,
            ~tiene_cedido_vigente,
        )
        .values(estado="caducada")
        .execution_options(synchronize_session=False)
    )

    tiene_aceptado = exists(
        sa_select(TurnoAceptado.id).where(
            TurnoAceptado.publicacion_id == PublicacionCambio.id,
        )
    )
    tiene_aceptado_vigente = exists(
        sa_select(TurnoAceptado.id).where(
            TurnoAceptado.publicacion_id == PublicacionCambio.id,
            TurnoAceptado.fecha >= hoy_real,
        )
    )
    stmt_regalos = (
        sa_update(PublicacionCambio)
        .where(
            PublicacionCambio.estado.in_(("abierta", "parcialmente_resuelta")),
            PublicacionCambio.tipo == "regalo",
            tiene_aceptado,
            ~tiene_aceptado_vigente,
        )
        .values(estado="caducada")
        .execution_options(synchronize_session=False)
    )

    n1 = db.session.execute(stmt_cedidos).rowcount
    n2 = db.session.execute(stmt_regalos).rowcount
    total = n1 + n2
    if total:
        db.session.commit()

    if hoy is None:
        _ultima_caducidad = hoy_real

    return total
