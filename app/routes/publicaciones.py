from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user, login_required

from app.models import FranjaHoraria
from app.services.publicaciones import publicar_cambio

bp = Blueprint("publicaciones", __name__)


def _extraer_turnos(prefix):
    """Extrae pares (fecha, franja_id) del form con claves fecha_{prefix}_N / franja_{prefix}_N."""
    turnos = []
    idx = 0
    while True:
        fecha_str = request.form.get(f"fecha_{prefix}_{idx}", "").strip()
        franja_str = request.form.get(f"franja_{prefix}_{idx}", "").strip()
        if not fecha_str or not franja_str:
            break
        try:
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            franja_id = int(franja_str)
            turnos.append((fecha, franja_id))
        except (ValueError, TypeError):
            pass
        idx += 1
    return turnos


@bp.route("/publicar", methods=["GET", "POST"])
@login_required
def nueva():
    franjas = (
        FranjaHoraria.query
        .filter_by(grupo_intercambio_id=current_user.unidad.grupo_intercambio_id)
        .order_by(FranjaHoraria.hora_inicio)
        .all()
    )

    if request.method == "POST":
        cedidos = _extraer_turnos("cedida")
        aceptados = _extraer_turnos("aceptada")

        if not cedidos:
            flash(_("Debes indicar al menos un turno que cedes."), "danger")
            return render_template("publicaciones/publicar.html", franjas=franjas)

        if not aceptados:
            flash(_("Debes indicar al menos un turno que aceptarías."), "danger")
            return render_template("publicaciones/publicar.html", franjas=franjas)

        publicar_cambio(current_user.id, cedidos, aceptados)
        flash(_("Publicación creada correctamente."), "success")
        return redirect(url_for("main.index"))

    return render_template("publicaciones/publicar.html", franjas=franjas)
