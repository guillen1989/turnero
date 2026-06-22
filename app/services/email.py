"""Servicio de avisos por email cuando se detecta un match."""
from datetime import date

from flask import current_app
from flask_babel import _

from app.extensions import db
from app.models.aviso_email import AvisoEmail


def _enviar_correo(destinatario, asunto, cuerpo):
    """Envía un correo. Silencia excepciones para no bloquear el flujo principal."""
    try:
        from flask_mail import Message
        from app.extensions import mail
        msg = Message(subject=asunto, recipients=[destinatario], body=cuerpo)
        mail.send(msg)
    except Exception as exc:
        current_app.logger.warning("Error enviando email a %s: %s", destinatario, exc)


def _avisos_hoy(usuario_id, hoy):
    return AvisoEmail.query.filter_by(usuario_id=usuario_id, fecha=hoy).count()


def enviar_notificacion_feedback(feedback):
    """Notifica al administrador cuando se recibe un nuevo mensaje de feedback."""
    destinatario = current_app.config.get("FEEDBACK_RECIPIENT_EMAIL", "")
    if not destinatario:
        return

    tipos = {"error": "Error en la app", "sugerencia": "Sugerencia de mejora"}
    tipo_label = tipos.get(feedback.tipo, feedback.tipo)
    asunto = f"[CambiaTurnos] Nuevo feedback: {tipo_label}"
    cuerpo = (
        f"Tipo: {tipo_label}\n"
        f"Descripción: {feedback.descripcion}\n"
        f"Email de contacto: {feedback.email_contacto or '(no indicado)'}\n"
        f"Usuario ID: {feedback.usuario_id or '(anónimo)'}\n"
    )
    _enviar_correo(destinatario, asunto, cuerpo)


def enviar_aviso_match(usuario, publicacion, hoy=None):
    """
    Envía un aviso por email al usuario si:
    - tiene avisos_email=True
    - no ha alcanzado su límite diario de avisos

    El último email del día incluye advertencia sobre el límite.
    """
    if not usuario.avisos_email:
        return

    if hoy is None:
        hoy = date.today()

    enviados = _avisos_hoy(usuario.id, hoy)
    limite = usuario.limite_avisos_email or 3

    if enviados >= limite:
        return

    es_ultimo = (enviados == limite - 1)

    if es_ultimo:
        cuerpo = _(
            "Hola %(nombre)s,\n\n"
            "Hay un nuevo cambio compatible con tu publicación. Accede a la app para verlo.\n\n"
            "AVISO: Este es tu último aviso de hoy (límite de %(limite)d emails al día). "
            "Puede haber más matches que no recibirás por correo. Revisa la app.",
            nombre=usuario.nombre,
            limite=limite,
        )
    else:
        cuerpo = _(
            "Hola %(nombre)s,\n\n"
            "Hay un nuevo cambio compatible con tu publicación. Accede a la app para verlo.",
            nombre=usuario.nombre,
        )

    asunto = _("Nuevo cambio disponible — CambiaTurnos")
    _enviar_correo(usuario.email, asunto, cuerpo)

    db.session.add(AvisoEmail(usuario_id=usuario.id, fecha=hoy, publicacion_id=publicacion.id))
    db.session.commit()
