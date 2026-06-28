import calendar
from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models.franja_horaria import FranjaHoraria
from app.models.planilla import PlanillaMes
from app.services.planilla import (
    añadir_turno, eliminar_turno, publicar_mes, despublicar_mes, get_turnos_mes,
)

bp = Blueprint("planilla", __name__, url_prefix="/planilla")


@bp.route("/")
@login_required
def index():
    hoy = date.today()
    anyo = request.args.get("anyo", hoy.year, type=int)
    mes = request.args.get("mes", hoy.month, type=int)

    _, num_dias = calendar.monthrange(anyo, mes)
    dias = [date(anyo, mes, d) for d in range(1, num_dias + 1)]

    turnos = get_turnos_mes(current_user, anyo, mes)
    turnos_por_dia = {}
    for turno in turnos:
        turnos_por_dia.setdefault(turno.fecha, []).append(turno)

    planilla_mes_obj = PlanillaMes.query.filter_by(
        usuario_id=current_user.id, anyo=anyo, mes=mes
    ).first()

    franjas = (
        FranjaHoraria.query
        .filter_by(grupo_intercambio_id=current_user.grupo_intercambio.id)
        .order_by(FranjaHoraria.hora_inicio)
        .all()
    )

    prev_mes = mes - 1 if mes > 1 else 12
    prev_anyo = anyo if mes > 1 else anyo - 1
    next_mes = mes + 1 if mes < 12 else 1
    next_anyo = anyo if mes < 12 else anyo + 1

    return render_template(
        "planilla/planilla.html",
        anyo=anyo, mes=mes, dias=dias,
        turnos_por_dia=turnos_por_dia,
        planilla_mes=planilla_mes_obj,
        franjas=franjas,
        prev_anyo=prev_anyo, prev_mes=prev_mes,
        next_anyo=next_anyo, next_mes=next_mes,
        hoy=hoy,
    )


@bp.route("/turno/añadir", methods=["POST"])
@login_required
def turno_añadir():
    fecha_str = request.form.get("fecha", "")
    franja_id = request.form.get("franja_id", type=int)
    anyo = request.form.get("anyo", type=int)
    mes = request.form.get("mes", type=int)

    try:
        fecha = date.fromisoformat(fecha_str)
    except ValueError:
        flash("Fecha inválida.", "error")
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    if not franja_id:
        flash("Selecciona un turno.", "error")
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    franja = db.session.get(FranjaHoraria, franja_id)
    if not franja or franja.grupo_intercambio_id != current_user.grupo_intercambio.id:
        flash("Turno no válido.", "error")
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    añadir_turno(current_user, fecha, franja_id)
    return redirect(url_for("planilla.index", anyo=anyo, mes=mes))


@bp.route("/turno/eliminar", methods=["POST"])
@login_required
def turno_eliminar():
    fecha_str = request.form.get("fecha", "")
    franja_id = request.form.get("franja_id", type=int)
    anyo = request.form.get("anyo", type=int)
    mes = request.form.get("mes", type=int)

    try:
        fecha = date.fromisoformat(fecha_str)
    except ValueError:
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    eliminar_turno(current_user, fecha, franja_id)
    return redirect(url_for("planilla.index", anyo=anyo, mes=mes))


@bp.route("/<int:anyo>/<int:mes>/publicar", methods=["POST"])
@login_required
def mes_publicar(anyo, mes):
    publicar_mes(current_user, anyo, mes)
    flash("Planilla del mes publicada. Tus compañeros ya pueden ver tu disponibilidad.", "success")
    return redirect(url_for("planilla.index", anyo=anyo, mes=mes))


@bp.route("/<int:anyo>/<int:mes>/despublicar", methods=["POST"])
@login_required
def mes_despublicar(anyo, mes):
    despublicar_mes(current_user, anyo, mes)
    flash("Planilla retirada. Tus compañeros ya no verán tu disponibilidad este mes.", "info")
    return redirect(url_for("planilla.index", anyo=anyo, mes=mes))
