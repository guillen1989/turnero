import secrets

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Feedback

bp = Blueprint("feedback", __name__)

TIPOS = {
    "error": _("Error en la app"),
    "sugerencia": _("Sugerencia de mejora"),
    "recuperacion": _("Recuperación de contraseña"),
}


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
        flash(_("Gracias, hemos recibido tu mensaje."), "success")
        return redirect(url_for("main.index"))

    return render_template("feedback/nuevo.html", email_prefill=email_prefill)


@bp.route("/recuperar-contrasena", methods=["GET", "POST"])
def recuperar_contrasena():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        if not email:
            flash(_("Introduce tu dirección de email."), "danger")
            return render_template("feedback/recuperar.html")

        fb = Feedback(
            tipo="recuperacion",
            descripcion=_("Solicitud de recuperación de contraseña."),
            email_contacto=email,
            usuario_id=None,
        )
        db.session.add(fb)
        db.session.commit()
        flash(_("Hemos recibido tu solicitud. El administrador te contactará en breve."), "success")
        return redirect(url_for("auth.login"))

    return render_template("feedback/recuperar.html")
