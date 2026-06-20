"""Servicios para confirmar y rechazar matches."""
from datetime import datetime, timezone

from app.extensions import db
from app.models import Notificacion


def _participacion_del_usuario(match, usuario_id):
    for p in match.participaciones:
        if p.publicacion.usuario_id == usuario_id:
            return p
    return None


def confirmar_participacion(match, usuario_id):
    """
    Marca la participación del usuario como confirmada.
    Si todas las partes confirman: cierra el match, resuelve los turnos cedidos
    y actualiza el estado de las publicaciones.
    Si no: pone el match en 'confirmado_parcial' y notifica a los demás.
    """
    participacion = _participacion_del_usuario(match, usuario_id)
    participacion.confirmado = True
    participacion.fecha_confirmacion = datetime.now(timezone.utc)

    if match.todas_confirmadas():
        match.estado = "confirmado_total"
        for p in match.participaciones:
            p.turno_cedido.estado = "resuelto"
            p.publicacion.actualizar_estado()
    else:
        match.estado = "confirmado_parcial"
        for p in match.participaciones:
            if p.publicacion.usuario_id != usuario_id:
                db.session.add(Notificacion(
                    usuario_id=p.publicacion.usuario_id,
                    match_id=match.id,
                    tipo="confirmacion_parcial",
                ))

    db.session.commit()


def rechazar_match(match, usuario_id):
    """
    Rechaza el match y notifica a los demás participantes.
    Las publicaciones siguen activas: no cambian de estado.
    """
    match.estado = "rechazado"
    for p in match.participaciones:
        if p.publicacion.usuario_id != usuario_id:
            db.session.add(Notificacion(
                usuario_id=p.publicacion.usuario_id,
                match_id=match.id,
                tipo="rechazo",
            ))
    db.session.commit()
