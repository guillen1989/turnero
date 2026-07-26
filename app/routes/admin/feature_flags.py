from flask import flash, redirect, render_template, request, url_for
from flask_babel import _

from app.extensions import db
from app.models import FeatureFlag
from app.routes.admin import admin_required, bp
from app.routes.admin.helpers import _choices_unidades
from app.services.feature_flags import sincronizar_unidades_habilitadas


@bp.route("/feature-flags")
@admin_required
def feature_flags():
    flags = FeatureFlag.query.order_by(FeatureFlag.clave).all()
    return render_template(
        "admin/feature_flags.html", flags=flags, choices_unidades=_choices_unidades()
    )


@bp.route("/feature-flags/<int:flag_id>", methods=["POST"])
@admin_required
def feature_flag_actualizar(flag_id):
    flag = db.get_or_404(FeatureFlag, flag_id)
    flag.activo_global = request.form.get("activo_global") == "y"
    unidad_ids = [int(v) for v in request.form.getlist("unidades_habilitadas")]
    sincronizar_unidades_habilitadas(flag, unidad_ids)
    db.session.commit()
    flash(_("Flag «%(clave)s» actualizado.", clave=flag.clave), "success")
    return redirect(url_for("admin.feature_flags"))
