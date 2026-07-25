import os

from flask import abort, flash, jsonify, redirect, request, url_for
from flask_babel import _

from app.extensions import csrf, db
from app.routes.admin import admin_required, bp
from app.services.demo import reset_demo


@bp.route("/demo/reset", methods=["POST"])
@admin_required
def demo_reset():
    try:
        reset_demo()
        flash(_("Unidad de demostración regenerada correctamente."), "success")
    except Exception as e:
        db.session.rollback()
        flash(_("Error al regenerar la demo: %(error)s", error=str(e)), "danger")
    return redirect(url_for("admin.index"))


@bp.route("/demo/reset-cron", methods=["POST"])
@csrf.exempt
def demo_reset_cron():
    """Endpoint para cron externo (cron-job.org). Requiere token en Authorization header."""
    token = os.environ.get("DEMO_RESET_TOKEN", "")
    if not token:
        abort(404)
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {token}":
        abort(403)
    reset_demo()
    return jsonify({"ok": True, "mensaje": "Demo regenerada."})
