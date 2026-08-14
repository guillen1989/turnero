from flask import Blueprint, abort, flash, redirect, request, url_for
from flask_babel import _
from flask_login import current_user, login_required

from app.extensions import db
from app.models import DocumentoCambio, MatchCambio
from app.services.documento_cambio import (
    crear_documento_cambio_desde_match, firmar_documento, match_admite_documento_cambio,
)
from app.services.feature_flags import feature_activa_para_usuario_actual
from app.services.matches import confirmar_participacion, desconfirmar_participacion, rechazar_match

bp = Blueprint("matches", __name__)

_ESTADOS_CERRADOS = ("confirmado_total", "rechazado")


def _redirect_a_dashboard():
    estado = request.form.get("redirect_estado", "")
    if estado:
        return redirect(url_for("main.index", estado=estado))
    return redirect(url_for("main.index"))


def _get_match_validado(match_id):
    """Devuelve el match o aborta con 403/404/409 según corresponda."""
    match = db.get_or_404(MatchCambio, match_id)
    usuario_ids = {p.publicacion.usuario_id for p in match.participaciones}
    if current_user.id not in usuario_ids:
        abort(403)
    if match.estado in _ESTADOS_CERRADOS:
        abort(409)
    return match


@bp.post("/matches/<int:match_id>/confirmar")
@login_required
def confirmar(match_id):
    match = _get_match_validado(match_id)

    if match_admite_documento_cambio(match) and feature_activa_para_usuario_actual("hoja_cambio_digital"):
        firma = request.form.get("firma", "").strip()
        if not firma.startswith("data:image/"):
            flash(_("Debes firmar el cambio antes de confirmarlo."), "danger")
            return _redirect_a_dashboard()

        documento = DocumentoCambio.query.filter_by(match_id=match.id).first()
        if documento is None:
            documento = crear_documento_cambio_desde_match(match)
        ya_firmado = any(f.usuario_id == current_user.id for f in documento.firmas)
        if not ya_firmado:
            firmar_documento(documento, current_user, firma)

        if request.form.get("guardar_firma") and not current_user.firma_guardada:
            current_user.firma_guardada = firma
            db.session.commit()

    confirmar_participacion(match, current_user.id)
    flash(_("Has confirmado tu parte del cambio."), "success")
    return _redirect_a_dashboard()


@bp.post("/matches/<int:match_id>/desconfirmar")
@login_required
def desconfirmar(match_id):
    match = _get_match_validado(match_id)
    participacion = next(
        (p for p in match.participaciones if p.publicacion.usuario_id == current_user.id),
        None,
    )
    if participacion is None or not participacion.confirmado:
        abort(409)
    desconfirmar_participacion(match, current_user.id)
    flash(_("Has retirado tu confirmación del cambio."), "info")
    return _redirect_a_dashboard()


@bp.post("/matches/<int:match_id>/rechazar")
@login_required
def rechazar(match_id):
    match = _get_match_validado(match_id)
    rechazar_match(match, current_user.id)
    db.session.commit()
    flash(_("Has rechazado el cambio."), "info")
    return _redirect_a_dashboard()
