from flask import Blueprint, abort, flash, redirect, request, url_for
from flask_babel import _
from flask_login import current_user, login_required

from app.extensions import db
from app.models import MatchCambio
from app.services.matches import confirmar_participacion, desconfirmar_participacion, rechazar_match

bp = Blueprint("matches", __name__)

_ESTADOS_CERRADOS = ("confirmado_total", "rechazado")


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
    firma = request.form.get("firma", "").strip()
    if match.tipo == "directo_2" and not firma:
        flash(_("Debes firmar el cambio antes de confirmarlo."), "danger")
        return redirect(url_for("main.index"))
    confirmar_participacion(match, current_user.id, firma_data=firma or None)
    flash(_("Has confirmado tu parte del cambio."), "success")
    return redirect(url_for("main.index"))


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
    return redirect(url_for("main.index"))


@bp.post("/matches/<int:match_id>/rechazar")
@login_required
def rechazar(match_id):
    match = _get_match_validado(match_id)
    rechazar_match(match, current_user.id)
    flash(_("Has rechazado el cambio."), "info")
    return redirect(url_for("main.index"))
