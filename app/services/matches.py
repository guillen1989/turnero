"""Servicios para confirmar y rechazar matches."""
from datetime import datetime, timezone

from app.extensions import db
from app.models import Notificacion
from app.push.sender import enviar_push_condicional
from app.services.eventos import registrar_evento


def _participacion_del_usuario(match, usuario_id):
    for p in match.participaciones:
        if p.publicacion.usuario_id == usuario_id:
            return p
    return None


def calcular_trabajas(match):
    """Para cada participación devuelve un dict {fecha, franja} del turno que trabaja,
    o None si no trabaja nada (coincidencia parcial).

    Regla: en el ciclo A→B→C→A cada participante trabaja el turno cedido del
    participante anterior.  Para coincidencias parciales (regalo/petición), quien
    tiene turno_aceptado ya lo trabaja explícitamente; quien no tiene ningún
    'trabaja' recibe None.
    """
    partes = sorted(match.participaciones, key=lambda p: p.id)
    n = len(partes)
    trabajas = {}
    for i, part in enumerate(partes):
        if part.turno_aceptado:
            ta = part.turno_aceptado
            cualquier = ta.cualquier_franja
            trabajas[part.id] = {
                "fecha": ta.fecha.strftime("%d/%m/%Y"),
                "franja": None if cualquier else ta.franja_horaria.nombre,
            }
        elif part.turno_cedido:
            prev = partes[(i - 1) % n]
            tc = prev.turno_cedido  # None para coincidencias parciales
            trabajas[part.id] = (
                {"fecha": tc.fecha.strftime("%d/%m/%Y"), "franja": tc.franja_horaria.nombre}
                if tc else None
            )
        else:
            trabajas[part.id] = None
    return trabajas


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
        match.fecha_confirmacion_total = datetime.now(timezone.utc)
        for p in match.participaciones:
            if p.turno_cedido_id is not None:
                p.turno_cedido.estado = "resuelto"
                p.publicacion.actualizar_estado()
            else:
                # Participante de tipo 'regalo': no tiene turno_cedido que resolver.
                p.publicacion.estado = "confirmada"
            if p.turno_aceptado_id is not None:
                p.turno_aceptado.estado = "resuelto"
        for p in match.participaciones:
            db.session.add(Notificacion(
                usuario_id=p.publicacion.usuario_id,
                match_id=match.id,
                tipo="confirmado_total",
            ))
            if p.publicacion.usuario_id != usuario_id:
                enviar_push_condicional(p.publicacion.usuario, "confirmado_total")
            registrar_evento(p.publicacion.usuario_id, "match_confirmed", match.id)
    else:
        match.estado = "confirmado_parcial"
        for p in match.participaciones:
            if p.publicacion.usuario_id != usuario_id:
                db.session.add(Notificacion(
                    usuario_id=p.publicacion.usuario_id,
                    match_id=match.id,
                    tipo="confirmacion_parcial",
                ))
                enviar_push_condicional(p.publicacion.usuario, "confirmacion_parcial")

    db.session.commit()


def desconfirmar_participacion(match, usuario_id):
    """
    Revierte la confirmación propia de un match aún no cerrado, por si el
    usuario cambia de idea. No toca turnos ni publicaciones: solo pudieron
    resolverse cuando el match llegó a 'confirmado_total', estado ya
    excluido por _get_match_validado antes de llegar aquí.
    Si alguna otra parte sigue confirmada (cadenas de 3+), el match
    permanece en 'confirmado_parcial'; si no, vuelve a 'propuesto'.
    """
    participacion = _participacion_del_usuario(match, usuario_id)
    participacion.confirmado = False
    participacion.fecha_confirmacion = None

    match.estado = "confirmado_parcial" if any(
        p.confirmado for p in match.participaciones
    ) else "propuesto"

    for p in match.participaciones:
        if p.publicacion.usuario_id != usuario_id:
            db.session.add(Notificacion(
                usuario_id=p.publicacion.usuario_id,
                match_id=match.id,
                tipo="desconfirmacion",
            ))
            enviar_push_condicional(p.publicacion.usuario, "desconfirmacion")
        registrar_evento(p.publicacion.usuario_id, "match_unconfirmed", match.id)

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
            enviar_push_condicional(p.publicacion.usuario, "confirmacion_parcial")
        registrar_evento(p.publicacion.usuario_id, "match_cancelled", match.id)
    db.session.commit()
