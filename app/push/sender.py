"""Envío de notificaciones Web Push.

Se silencian todos los errores de transporte: suscripción expirada,
permiso revocado, servicio push caído, etc. El flujo de negocio
no debe depender de si la notificación llega o no.
"""
import json
import threading

from flask import current_app
from pywebpush import WebPushException, webpush

# Mapa de tipo de notificación → atributo de preferencia en Usuario
_PREF_ATTR = {
    "match": "notif_match",
    "match_parcial": "notif_match",
    "confirmacion_parcial": "notif_confirmacion_parcial",
    "desconfirmacion": "notif_confirmacion_parcial",
    "confirmado_total": "notif_confirmado_total",
    "publicacion": "notif_publicacion",
    "contraoferta": "notif_match",
    "busqueda_guardada": "notif_busqueda_guardada",
    "aviso_oportunidad_3": "notif_match",
}

# Mapa de tipo de notificación → URL de destino al tocar la push
_URL_POR_TIPO = {
    "match": "/?estado=compatible",
    "match_parcial": "/?estado=compatible",
    "confirmacion_parcial": "/?estado=pendiente",
    "desconfirmacion": "/?estado=pendiente",
    "confirmado_total": "/?estado=confirmada",
    "publicacion": "/avisos",
    "contraoferta": "/avisos",
    "busqueda_guardada": "/avisos",
    "aviso_oportunidad_3": "/avisos",
}

# Textos por tipo: (título, cuerpo_singular, cuerpo_plural)
_TEXTOS = {
    "match": (
        "Turnero",
        "Tienes 1 compatible nuevo",
        "Tienes {} compatibles nuevos",
    ),
    "match_parcial": (
        "Turnero",
        "Tienes 1 coincidencia parcial nueva",
        "Tienes {} coincidencias parciales nuevas",
    ),
    "confirmacion_parcial": (
        "Turnero",
        "Tienes 1 cambio pendiente de confirmar",
        "Tienes {} cambios pendientes de confirmar",
    ),
    "desconfirmacion": (
        "Turnero",
        "Un compañero ha retirado su confirmación de un cambio",
        "Hay {} compañeros que han retirado su confirmación de un cambio",
    ),
    "confirmado_total": (
        "Turnero",
        "¡Tienes 1 cambio confirmado!",
        "¡Tienes {} cambios confirmados!",
    ),
    "publicacion": (
        "Turnero",
        "Hay 1 publicación nueva de compañeros",
        "Hay {} publicaciones nuevas de compañeros",
    ),
    "contraoferta": (
        "Turnero",
        "Tienes 1 contraoferta nueva",
        "Tienes {} contraofertas nuevas",
    ),
    "busqueda_guardada": (
        "Turnero",
        "Hay 1 publicación nueva que coincide con tus alertas",
        "Hay {} publicaciones nuevas que coinciden con tus alertas",
    ),
    "aviso_oportunidad_3": (
        "Turnero",
        "Se ha generado 1 oportunidad de cambio a 3 con tu publicación",
        "Se han generado {} oportunidades de cambio a 3 con tus publicaciones",
    ),
}


def _contar_pendientes(usuario, tipo):
    """Cuenta los elementos pendientes del tipo dado para el usuario."""
    from sqlalchemy import func, select as sa_select

    from app.extensions import db
    from app.models import MatchCambio, MatchParticipacion, Notificacion, PublicacionCambio

    if tipo in ("match", "match_parcial"):
        return db.session.scalar(
            sa_select(func.count(Notificacion.id)).where(
                Notificacion.usuario_id == usuario.id,
                Notificacion.tipo == "nuevo_match",
                Notificacion.leida.is_(False),
            )
        )

    if tipo == "confirmacion_parcial":
        return db.session.scalar(
            sa_select(func.count(MatchParticipacion.id))
            .join(MatchCambio, MatchParticipacion.match_id == MatchCambio.id)
            .join(PublicacionCambio, MatchParticipacion.publicacion_id == PublicacionCambio.id)
            .where(
                PublicacionCambio.usuario_id == usuario.id,
                MatchParticipacion.confirmado.is_(False),
                MatchCambio.estado == "confirmado_parcial",
            )
        )

    if tipo == "confirmado_total":
        return db.session.scalar(
            sa_select(func.count(MatchParticipacion.id))
            .join(MatchCambio, MatchParticipacion.match_id == MatchCambio.id)
            .join(PublicacionCambio, MatchParticipacion.publicacion_id == PublicacionCambio.id)
            .where(
                PublicacionCambio.usuario_id == usuario.id,
                MatchCambio.estado == "confirmado_total",
            )
        )

    if tipo == "publicacion":
        return db.session.scalar(
            sa_select(func.count(Notificacion.id)).where(
                Notificacion.usuario_id == usuario.id,
                Notificacion.tipo == "nueva_publicacion_seguido",
                Notificacion.leida.is_(False),
            )
        )

    if tipo == "busqueda_guardada":
        return db.session.scalar(
            sa_select(func.count(Notificacion.id)).where(
                Notificacion.usuario_id == usuario.id,
                Notificacion.tipo == "alerta_busqueda_guardada",
                Notificacion.leida.is_(False),
            )
        )

    if tipo == "aviso_oportunidad_3":
        return db.session.scalar(
            sa_select(func.count(Notificacion.id)).where(
                Notificacion.usuario_id == usuario.id,
                Notificacion.tipo == "aviso_oportunidad_3",
                Notificacion.leida.is_(False),
            )
        )

    return 1


def _textos_para(tipo, n):
    titulo, singular, plural = _TEXTOS.get(tipo, ("Turnero", "Nueva notificación", "Nuevas notificaciones"))
    cuerpo = singular if n == 1 else plural.format(n)
    return titulo, cuerpo


def enviar_push(usuario, titulo, cuerpo, url="/", tag=None, urgente=False):
    """
    Envía una notificación push al usuario en un hilo daemon para no bloquear
    el worker. No hace nada si el usuario no tiene suscripción guardada
    o si las claves VAPID no están configuradas.

    `urgente=True` añade la cabecera Urgency: high (RFC 8030) para que el
    servicio push la entregue con prioridad incluso en dispositivos con
    ahorro de batería.
    """
    if not usuario.push_subscription:
        return

    vapid_private_key = current_app.config.get("VAPID_PRIVATE_KEY", "")
    if not vapid_private_key:
        return

    app = current_app._get_current_object()
    usuario_id = usuario.id
    subscription = json.loads(usuario.push_subscription)
    vapid_claims = {"sub": f"mailto:{current_app.config.get('VAPID_CLAIM_EMAIL', '')}"}
    payload = {"title": titulo, "body": cuerpo, "url": url}
    if tag:
        payload["tag"] = tag
    data = json.dumps(payload)
    headers = {"Urgency": "high"} if urgente else None

    def _send():
        try:
            webpush(
                subscription_info=subscription,
                data=data,
                vapid_private_key=vapid_private_key,
                vapid_claims=vapid_claims,
                headers=headers,
            )
        except Exception as exc:
            app.logger.warning("Push no entregado a usuario %s: %s", usuario_id, exc)

    # En tests se ejecuta síncronamente para que los mocks funcionen
    if app.config.get("TESTING"):
        _send()
    else:
        threading.Thread(target=_send, daemon=True).start()


def enviar_push_condicional(usuario, tipo):
    """
    Envía push solo si el usuario tiene habilitadas las notificaciones
    globalmente (push_activo) y el tipo específico dado. El texto refleja
    cuántos elementos pendientes tiene el usuario de ese tipo, y el tag
    hace que el SO reemplace la notificación anterior del mismo tipo.

    tipo: 'match' | 'confirmacion_parcial' | 'confirmado_total' | 'publicacion'
    """
    if not getattr(usuario, "push_activo", True):
        return
    attr = _PREF_ATTR.get(tipo)
    if attr and not getattr(usuario, attr, True):
        return

    n = _contar_pendientes(usuario, tipo)
    titulo, cuerpo = _textos_para(tipo, n or 1)
    url = _URL_POR_TIPO.get(tipo, "/")
    enviar_push(usuario, titulo, cuerpo, url, tag=tipo)
