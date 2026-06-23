from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Notificacion, SuscripcionPublicaciones, Unidad, Usuario

bp = Blueprint("notificaciones", __name__)


@bp.get("/notificaciones")
@login_required
def panel():
    colegas = _colegas_del_usuario(current_user)
    ids_suscritos = {
        s.publicador_id
        for s in SuscripcionPublicaciones.query.filter_by(suscriptor_id=current_user.id).all()
    }
    return render_template(
        "notificaciones/panel.html",
        colegas=colegas,
        ids_suscritos=ids_suscritos,
    )


@bp.post("/notificaciones/guardar")
@login_required
def guardar():
    current_user.push_activo = "push_activo" in request.form
    current_user.notif_match = "notif_match" in request.form
    current_user.notif_confirmacion_parcial = "notif_confirmacion_parcial" in request.form
    current_user.notif_confirmado_total = "notif_confirmado_total" in request.form
    db.session.commit()
    flash(_("Preferencias de notificaciones guardadas."), "success")
    return redirect(url_for("notificaciones.panel"))


@bp.post("/notificaciones/suscribir/<int:uid>")
@login_required
def suscribir(uid):
    if uid == current_user.id:
        flash(_("No puedes suscribirte a tus propias publicaciones."), "warning")
        return redirect(url_for("notificaciones.panel"))
    try:
        db.session.add(SuscripcionPublicaciones(
            suscriptor_id=current_user.id,
            publicador_id=uid,
        ))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
    return redirect(url_for("notificaciones.panel"))


@bp.post("/notificaciones/cancelar/<int:uid>")
@login_required
def cancelar_suscripcion(uid):
    SuscripcionPublicaciones.query.filter_by(
        suscriptor_id=current_user.id,
        publicador_id=uid,
    ).delete()
    db.session.commit()
    return redirect(url_for("notificaciones.panel"))


@bp.get("/avisos")
@login_required
def avisos():
    notifs = (
        Notificacion.query
        .filter_by(usuario_id=current_user.id, tipo="nueva_publicacion_seguido")
        .order_by(Notificacion.fecha.desc())
        .all()
    )
    for n in notifs:
        n.leida = True
    db.session.commit()
    return render_template("notificaciones/avisos.html", avisos=notifs)


def _colegas_del_usuario(usuario):
    """Usuarios del mismo grupo de intercambio y categoría, excluyendo al propio usuario."""
    grupo_id = usuario.unidad.grupo_intercambio_id
    return (
        Usuario.query
        .join(Unidad, Usuario.unidad_id == Unidad.id)
        .filter(
            Unidad.grupo_intercambio_id == grupo_id,
            Usuario.categoria_id == usuario.categoria_id,
            Usuario.id != usuario.id,
        )
        .order_by(Usuario.nombre)
        .all()
    )
