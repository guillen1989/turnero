import secrets

from flask import abort, flash, redirect, render_template, request, url_for
from flask_babel import _

from app.extensions import db
from app.models import Feedback, Notificacion, Usuario
from app.routes.admin import admin_required, bp


@bp.route("/feedback")
@admin_required
def feedback():
    tab = request.args.get("tab", "sin_leer")
    sin_leer = (
        Feedback.query
        .filter_by(leido=False)
        .order_by(Feedback.fecha_creacion.desc())
        .all()
    )
    leidos = (
        Feedback.query
        .filter_by(leido=True)
        .order_by(Feedback.fecha_creacion.desc())
        .all()
    )
    return render_template("admin/feedback.html", sin_leer=sin_leer, leidos=leidos, tab=tab)


@bp.route("/feedback/<int:id>/marcar-leido", methods=["POST"])
@admin_required
def feedback_marcar_leido(id):
    fb = db.session.get(Feedback, id) or abort(404)
    fb.leido = True
    db.session.commit()
    return redirect(url_for("admin.feedback"))


@bp.route("/feedback/marcar-leidos", methods=["POST"])
@admin_required
def feedback_marcar_leidos():
    ids = request.form.getlist("ids", type=int)
    if ids:
        Feedback.query.filter(Feedback.id.in_(ids)).update({"leido": True}, synchronize_session=False)
        db.session.commit()
    return redirect(url_for("admin.feedback", tab="sin_leer"))


@bp.route("/feedback/<int:id>/restablecer-contrasena", methods=["POST"])
@admin_required
def feedback_restablecer_contrasena(id):
    fb = db.session.get(Feedback, id) or abort(404)
    usuario = Usuario.query.filter_by(email=fb.email_contacto).first()
    if not usuario:
        flash(_("No se encontró ningún usuario con el email %(email)s.", email=fb.email_contacto), "danger")
        return redirect(url_for("admin.feedback"))

    contrasena_temporal = secrets.token_urlsafe(8)
    usuario.set_password(contrasena_temporal)
    fb.leido = True
    db.session.add(Notificacion(
        usuario_id=usuario.id,
        unidad_id=usuario.unidad_id,
        tipo="contrasena_restablecida",
        mensaje=_("Un administrador te ha restablecido la contraseña. Nueva contraseña temporal: %(pwd)s",
                   pwd=contrasena_temporal),
    ))
    db.session.commit()

    flash(
        _("Contraseña restablecida para %(email)s. Se le ha enviado un aviso con la nueva contraseña.",
          email=fb.email_contacto),
        "success",
    )
    return redirect(url_for("admin.feedback"))
