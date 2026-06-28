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


def _resolver_seleccion(seleccion):
    """Dado el valor del campo 'seleccion', devuelve (tipo_estado, franja_id) o (None, None) si inválido.
    tipo_estado es str si es un estado del día; franja_id es int si es un turno de trabajo.
    """
    if seleccion in TIPOS_ESTADO_DIA:
        return seleccion, None
    try:
        franja_id = int(seleccion)
        franja = db.session.get(FranjaHoraria, franja_id)
        if franja and franja.grupo_intercambio_id == current_user.grupo_intercambio.id:
            return None, franja_id
    except (ValueError, TypeError):
        pass
    return None, None

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


@bp.route("/rango/aplicar", methods=["POST"])
@login_required
def rango_aplicar():
    """Rellena un rango de días consecutivos del mes con un mismo turno o estado."""
    dia_inicio = request.form.get("dia_inicio", type=int)
    dia_fin    = request.form.get("dia_fin",    type=int)
    seleccion  = request.form.get("seleccion",  "").strip()
    anyo = request.form.get("anyo", type=int)
    mes  = request.form.get("mes",  type=int)

    _, num_dias = calendar.monthrange(anyo, mes)

    if not dia_inicio or not dia_fin or not seleccion:
        flash("Completa todos los campos del relleno rápido.", "error")
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    if dia_fin < dia_inicio:
        dia_inicio, dia_fin = dia_fin, dia_inicio

    dia_inicio = max(1, dia_inicio)
    dia_fin    = min(num_dias, dia_fin)

    tipo_estado, franja_id = _resolver_seleccion(seleccion)
    if tipo_estado is None and franja_id is None:
        flash("Selección no válida.", "error")
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    for d in range(dia_inicio, dia_fin + 1):
        fecha = date(anyo, mes, d)
        if tipo_estado:
            establecer_estado_dia(current_user, fecha, tipo_estado)
        else:
            añadir_turno(current_user, fecha, franja_id)

    n = dia_fin - dia_inicio + 1
    flash(f"{n} día(s) actualizados.", "success")
    return redirect(url_for("planilla.index", anyo=anyo, mes=mes))


@bp.route("/multiples/aplicar", methods=["POST"])
@login_required
def multiples_aplicar():
    """Aplica un turno o estado a una lista de días concretos enviados desde el selector múltiple."""
    fechas_strs = request.form.getlist("fecha[]")
    seleccion   = request.form.get("seleccion",  "").strip()
    anyo = request.form.get("anyo", type=int)
    mes  = request.form.get("mes",  type=int)

    if not seleccion or not fechas_strs:
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    tipo_estado, franja_id = _resolver_seleccion(seleccion)
    if tipo_estado is None and franja_id is None:
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    count = 0
    for fecha_str in fechas_strs:
        try:
            fecha = date.fromisoformat(fecha_str)
            if fecha.year != anyo or fecha.month != mes:
                continue  # sólo fechas del mes visible
            if tipo_estado:
                establecer_estado_dia(current_user, fecha, tipo_estado)
            else:
                añadir_turno(current_user, fecha, franja_id)
            count += 1
        except ValueError:
            pass

    if count:
        flash(f"{count} día(s) actualizados.", "success")
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
