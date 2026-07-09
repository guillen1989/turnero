import requests
from flask import current_app, url_for

RESEND_API_URL = "https://api.resend.com/emails"
_TIMEOUT_SEGUNDOS = 10


def url_absoluta(endpoint, **values):
    """Construye una URL absoluta para usar en emails.

    Usa APP_BASE_URL (dominio propio) en vez del host de la petición entrante
    cuando está configurada: algunos filtros de correo corporativos bloquean
    o rebotan enlaces al dominio compartido *.up.railway.app.
    """
    base = current_app.config.get("APP_BASE_URL", "").rstrip("/")
    if base:
        return base + url_for(endpoint, **values)
    return url_for(endpoint, _external=True, **values)


def enviar_email(destinatario, asunto, cuerpo_html):
    """Envía un email transaccional vía la API HTTPS de Resend.

    HTTPS y no SMTP a propósito: Railway bloquea los puertos SMTP salientes
    en el plan Hobby, pero no el tráfico HTTPS saliente normal.
    Nunca lanza: un fallo de envío no debe tumbar el flujo que lo dispara.
    """
    api_key = current_app.config.get("RESEND_API_KEY", "")
    if not api_key:
        current_app.logger.warning("RESEND_API_KEY no configurada: email no enviado a %s", destinatario)
        return False

    remitente = current_app.config.get("RESEND_FROM_EMAIL", "noreply@turnero.xyz")

    try:
        respuesta = requests.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": remitente,
                "to": [destinatario],
                "subject": asunto,
                "html": cuerpo_html,
            },
            timeout=_TIMEOUT_SEGUNDOS,
        )
    except requests.exceptions.RequestException:
        current_app.logger.error("Error de red enviando email a %s vía Resend", destinatario, exc_info=True)
        return False

    if respuesta.status_code >= 300:
        current_app.logger.error(
            "Resend rechazó el email a %s (status %s): %s",
            destinatario, respuesta.status_code, respuesta.text,
        )
        return False

    return True
