from datetime import time as _time

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user, login_required

from app.extensions import db
from app.models import FranjaHoraria
from app.services.turnos import PLANTILLAS, agregar_franja, aplicar_plantilla, eliminar_franja

bp = Blueprint("unidad", __name__, url_prefix="/unidad")


def _parse_time(s):
    parts = s.strip().split(":")
    if len(parts) != 2:
        raise ValueError
    try:
        return _time(int(parts[0]), int(parts[1]))
    except (ValueError, TypeError):
        raise ValueError


@bp.get("/turnos")
@login_required
def turnos():
    grupo = current_user.unidad.grupo_intercambio
    franjas = (
        FranjaHoraria.query
        .filter_by(grupo_intercambio_id=grupo.id)
        .order_by(FranjaHoraria.hora_inicio)
        .all()
    )
    return render_template(
        "unidad/turnos.html",
        franjas=franjas,
        plantillas=PLANTILLAS,
        unidad=current_user.unidad,
    )


@bp.post("/turnos/plantilla")
@login_required
def aplicar_plantilla_route():
    plantilla_id = request.form.get("plantilla_id", "")
    grupo = current_user.unidad.grupo_intercambio
    try:
        aplicar_plantilla(grupo, plantilla_id)
        db.session.commit()
        flash(_("Plantilla aplicada. Revisa los turnos resultantes."), "success")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("unidad.turnos"))


@bp.post("/turnos")
@login_required
def agregar_franja_route():
    nombre = request.form.get("nombre", "").strip()
    hora_inicio_str = request.form.get("hora_inicio", "").strip()
    hora_fin_str = request.form.get("hora_fin", "").strip()

    if not nombre:
        flash(_("El nombre del turno es obligatorio."), "danger")
        return redirect(url_for("unidad.turnos"))

    try:
        hora_inicio = _parse_time(hora_inicio_str)
        hora_fin = _parse_time(hora_fin_str)
    except ValueError:
        flash(_("Formato de hora no válido. Usa HH:MM."), "danger")
        return redirect(url_for("unidad.turnos"))

    grupo = current_user.unidad.grupo_intercambio
    try:
        agregar_franja(grupo, nombre, hora_inicio, hora_fin)
        db.session.commit()
        flash(_("Turno «%(nombre)s» añadido.", nombre=nombre), "success")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("unidad.turnos"))


@bp.post("/turnos/<int:franja_id>/eliminar")
@login_required
def eliminar_franja_route(franja_id):
    grupo = current_user.unidad.grupo_intercambio
    try:
        eliminar_franja(franja_id, grupo.id)
        db.session.commit()
        flash(_("Turno eliminado."), "success")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("unidad.turnos"))
