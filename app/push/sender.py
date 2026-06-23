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
    "confirmacion_parcial": "notif_confirmacion_parcial",
    "confirmado_total": "notif_confirmado_total",
}

# Mapa de tipo de notificación → URL de destino al tocar la push
_URL_POR_TIPO = {
    "match": "/?estado=compatible",
    "confirmacion_parcial": "/?estado=pendiente",
    "confirmado_total": "/?estado=confirmada",
    "publicacion": "/avisos",
}


def enviar_push(usuario, titulo, cuerpo, url="/"):
    """
    Envía una notificación push al usuario en un hilo daemon para no bloquear
    el worker. No hace nada si el usuario no tiene suscripción guardada
    o si las claves VAPID no están configuradas.
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
    data = json.dumps({"title": titulo, "body": cuerpo, "url": url})

    def _send():
        try:
            webpush(
                subscription_info=subscription,
                data=data,
                vapid_private_key=vapid_private_key,
                vapid_claims=vapid_claims,
            )
        except Exception as exc:
            app.logger.warning("Push no entregado a usuario %s: %s", usuario_id, exc)

    # En tests se ejecuta síncronamente para que los mocks funcionen
    if app.config.get("TESTING"):
        _send()
    else:
        threading.Thread(target=_send, daemon=True).start()


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
    url = _URL_POR_TIPO.get(tipo, "/")
    enviar_push(usuario, titulo, cuerpo, url)
