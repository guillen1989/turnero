"""Envío de notificaciones Web Push.

Se silencian todos los errores de transporte: suscripción expirada,
permiso revocado, servicio push caído, etc. El flujo de negocio
no debe depender de si la notificación llega o no.
"""
import json

from flask import current_app
from pywebpush import WebPushException, webpush

# Mapa de tipo de notificación → atributo de preferencia en Usuario
_PREF_ATTR = {
    "match": "notif_match",
    "confirmacion_parcial": "notif_confirmacion_parcial",
    "confirmado_total": "notif_confirmado_total",
}


def enviar_push(usuario, titulo, cuerpo):
    """
    Envía una notificación push al usuario.
    No hace nada si el usuario no tiene suscripción guardada
    o si las claves VAPID no están configuradas.
    """
    if not usuario.push_subscription:
        return

    vapid_private_key = current_app.config.get("VAPID_PRIVATE_KEY", "")
    if not vapid_private_key:
        return

    vapid_claims = {
        "sub": f"mailto:{current_app.config.get('VAPID_CLAIM_EMAIL', '')}"
    }

    try:
        webpush(
            subscription_info=json.loads(usuario.push_subscription),
            data=json.dumps({"title": titulo, "body": cuerpo}),
            vapid_private_key=vapid_private_key,
            vapid_claims=vapid_claims,
        )
    except Exception as exc:
        current_app.logger.warning("Push no entregado a usuario %s: %s", usuario.id, exc)


def enviar_push_condicional(usuario, tipo, titulo, cuerpo):
    """
    Envía push solo si el usuario tiene habilitadas las notificaciones
    globalmente (push_activo) y el tipo específico dado.

    tipo: 'match' | 'confirmacion_parcial' | 'confirmado_total' | 'publicacion'
    """
    if not getattr(usuario, "push_activo", True):
        return
    attr = _PREF_ATTR.get(tipo)
    if attr and not getattr(usuario, attr, True):
        return
    enviar_push(usuario, titulo, cuerpo)
