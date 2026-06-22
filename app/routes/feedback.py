from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user
from flask_mail import Message

from app.extensions import mail

bp = Blueprint("feedback", __name__)

DESTINO = "domingofestivo@gmail.com"
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

        tipo_label = TIPOS.get(tipo, tipo)
        asunto = f"[CambiaTurnos] {tipo_label}"
        cuerpo = (
            f"Tipo: {tipo_label}\n"
            f"Email de contacto: {email_contacto or '—'}\n\n"
            f"{descripcion}"
        )

        try:
            mail.send(Message(subject=asunto, recipients=[DESTINO], body=cuerpo))
            flash(_("Gracias, hemos recibido tu mensaje."), "success")
            return redirect(url_for("main.index"))
        except Exception:
            flash(_("No se pudo enviar el mensaje. Inténtalo de nuevo."), "danger")
            return render_template("feedback/nuevo.html",
                                   email_prefill=email_contacto or email_prefill)

    return render_template("feedback/nuevo.html", email_prefill=email_prefill)
