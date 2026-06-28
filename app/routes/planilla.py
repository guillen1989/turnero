import calendar
from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models.franja_horaria import FranjaHoraria
from app.models.planilla import PlanillaMes, TIPOS_ESTADO_DIA
from app.services.planilla import (
    añadir_turno, eliminar_turno,
    establecer_estado_dia, limpiar_dia,
    publicar_mes, despublicar_mes,
    get_turnos_mes, get_estados_mes,
    dias_sin_cumplimentar,
)
from app.services.compat_planilla_persistente import actualizar_compat_tras_publicar_planilla

bp = Blueprint("planilla", __name__, url_prefix="/planilla")

ETIQUETAS_ESTADO = {
    "libre":         "Libre",
    "vacaciones":    "Vacaciones",
    "no_disponible": "No disponible para cambios",
}


@bp.route("/")
@login_required
def index():
    hoy = date.today()
    anyo = request.args.get("anyo", hoy.year, type=int)
    mes  = request.args.get("mes",  hoy.month, type=int)

    _, num_dias = calendar.monthrange(anyo, mes)
    dias = [date(anyo, mes, d) for d in range(1, num_dias + 1)]

    turnos = get_turnos_mes(current_user, anyo, mes)
    turnos_por_dia = {}
    for turno in turnos:
        turnos_por_dia.setdefault(turno.fecha, []).append(turno)

    estados_por_dia = get_estados_mes(current_user, anyo, mes)

    planilla_mes_obj = PlanillaMes.query.filter_by(
        usuario_id=current_user.id, anyo=anyo, mes=mes
    ).first()

    franjas = (
        FranjaHoraria.query
        .filter_by(grupo_intercambio_id=current_user.grupo_intercambio.id)
        .order_by(FranjaHoraria.hora_inicio)
        .all()
    )

    prev_mes  = mes - 1 if mes > 1 else 12
    prev_anyo = anyo if mes > 1 else anyo - 1
    next_mes  = mes + 1 if mes < 12 else 1
    next_anyo = anyo if mes < 12 else anyo + 1

    return render_template(
        "planilla/planilla.html",
        anyo=anyo, mes=mes, dias=dias,
        turnos_por_dia=turnos_por_dia,
        estados_por_dia=estados_por_dia,
        planilla_mes=planilla_mes_obj,
        franjas=franjas,
        etiquetas_estado=ETIQUETAS_ESTADO,
        prev_anyo=prev_anyo, prev_mes=prev_mes,
        next_anyo=next_anyo, next_mes=next_mes,
        hoy=hoy,
    )


@bp.route("/dia/añadir", methods=["POST"])
@login_required
def dia_añadir():
    """Añade un turno de trabajo o establece un estado especial para el día."""
    fecha_str = request.form.get("fecha", "")
    seleccion = request.form.get("seleccion", "").strip()
    anyo = request.form.get("anyo", type=int)
    mes  = request.form.get("mes",  type=int)

    try:
        fecha = date.fromisoformat(fecha_str)
    except ValueError:
        flash("Fecha inválida.", "error")
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    if not seleccion:
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    if seleccion in TIPOS_ESTADO_DIA:
        establecer_estado_dia(current_user, fecha, seleccion)
    else:
        try:
            franja_id = int(seleccion)
        except ValueError:
            flash("Selección no válida.", "error")
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
    mes  = request.form.get("mes",  type=int)

    try:
        fecha = date.fromisoformat(fecha_str)
    except ValueError:
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    eliminar_turno(current_user, fecha, franja_id)
    return redirect(url_for("planilla.index", anyo=anyo, mes=mes))


@bp.route("/dia/limpiar", methods=["POST"])
@login_required
def dia_limpiar():
    """Elimina el estado especial del día (vuelve a sin especificar)."""
    fecha_str = request.form.get("fecha", "")
    anyo = request.form.get("anyo", type=int)
    mes  = request.form.get("mes",  type=int)

    try:
        fecha = date.fromisoformat(fecha_str)
    except ValueError:
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    limpiar_dia(current_user, fecha)
    return redirect(url_for("planilla.index", anyo=anyo, mes=mes))


@bp.route("/<int:anyo>/<int:mes>/publicar", methods=["POST"])
@login_required
def mes_publicar(anyo, mes):
    vacios = dias_sin_cumplimentar(current_user, anyo, mes)
    if vacios:
        n = len(vacios)
        primero = vacios[0].strftime("%-d/%m")
        flash(
            f"La planilla está incompleta: {n} día(s) sin cumplimentar "
            f"(el primero: {primero}). Añade un turno o marca cada día antes de publicar.",
            "error",
        )
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    publicar_mes(current_user, anyo, mes)
    actualizar_compat_tras_publicar_planilla(current_user, anyo, mes)
    flash("Planilla del mes publicada. Tus compañeros ya pueden ver tu disponibilidad.", "success")
    return redirect(url_for("planilla.index", anyo=anyo, mes=mes))


@bp.route("/<int:anyo>/<int:mes>/despublicar", methods=["POST"])
@login_required
def mes_despublicar(anyo, mes):
    despublicar_mes(current_user, anyo, mes)
    flash("Planilla retirada. Tus compañeros ya no verán tu disponibilidad este mes.", "info")
    return redirect(url_for("planilla.index", anyo=anyo, mes=mes))


# Mantener la ruta antigua para compatibilidad con tests existentes
@bp.route("/turno/añadir", methods=["POST"])
@login_required
def turno_añadir():
    fecha_str = request.form.get("fecha", "")
    franja_id = request.form.get("franja_id", type=int)
    anyo = request.form.get("anyo", type=int)
    mes  = request.form.get("mes",  type=int)

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
