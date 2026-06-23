from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Feedback
from app.services.email import enviar_notificacion_feedback

bp = Blueprint("feedback", __name__)

TIPOS = {"error": _("Error en la app"), "sugerencia": _("Sugerencia de mejora")}


@bp.route("/feedback", methods=["GET", "POST"])
def nuevo():
    email_prefill = current_user.email if current_user.is_authenticated else ""

    if request.method == "POST":
        tipo = request.form.get("tipo", "").strip()
        descripcion = request.form.get("descripcion", "").strip()[:500]
        email_contacto = request.form.get("email_contacto", "").strip()

        if not tipo or not descripcion:
            flash(_("Por favor, completa todos los campos obligatorios."), "danger")
            return render_template("feedback/nuevo.html",
                                   email_prefill=email_contacto or email_prefill)

        if tipo not in TIPOS:
            flash(_("Tipo de mensaje no válido."), "danger")
            return render_template("feedback/nuevo.html",
                                   email_prefill=email_contacto or email_prefill)

        fb = Feedback(
            tipo=tipo,
            descripcion=descripcion,
            email_contacto=email_contacto or None,
            usuario_id=current_user.id if current_user.is_authenticated else None,
        )
        db.session.add(fb)
        db.session.commit()
        enviar_notificacion_feedback(fb)

        flash(_("Gracias, hemos recibido tu mensaje."), "success")
        return redirect(url_for("main.index"))

    return render_template("feedback/nuevo.html", email_prefill=email_prefill)


# ── RUTA DE DIAGNÓSTICO TEMPORAL ─────────────────────────────────────────────
# Visitar /feedback/diagnostico en producción para ver qué paso falla.
# Borrar esta ruta una vez resuelto el problema.
@bp.get("/feedback/diagnostico")
@login_required
def diagnostico_email():
    from flask import current_app
    from flask_mail import Message
    from app.extensions import mail

    pasos = []

    dest = current_app.config.get("FEEDBACK_RECIPIENT_EMAIL", "")
    pasos.append(f"FEEDBACK_RECIPIENT_EMAIL = {dest!r}")

    for clave in ("MAIL_SERVER", "MAIL_PORT", "MAIL_USERNAME",
                  "MAIL_USE_TLS", "MAIL_USE_SSL", "MAIL_DEFAULT_SENDER"):
        pasos.append(f"{clave} = {current_app.config.get(clave)!r}")

    if not dest:
        pasos.append("PARADA: destinatario vacío — la función retorna sin enviar nada.")
        return jsonify(pasos)

    pasos.append("Intentando mail.send() de forma síncrona (sin hilo)…")
    try:
        msg = Message(
            subject="[Turnero] Email de prueba de diagnóstico",
            recipients=[dest],
            body="Si recibes este mensaje, el envío de email funciona correctamente.",
        )
        mail.send(msg)
        pasos.append("OK: mail.send() completado sin excepción.")
    except Exception as exc:
        pasos.append(f"ERROR en mail.send(): {type(exc).__name__}: {exc}")

    return jsonify(pasos)
