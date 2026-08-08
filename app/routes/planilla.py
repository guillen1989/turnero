import calendar
from datetime import date

from flask import Blueprint, render_template, request, redirect, session, url_for, flash
from flask_babel import _
from flask_login import login_required, current_user

from app.extensions import db
from app.models.franja_horaria import FranjaHoraria
from app.models.planilla import PlanillaMes, TIPOS_ESTADO_DIA, ETIQUETAS_ESTADO
from app.services.planilla import (
    añadir_turno, eliminar_turno,
    establecer_estado_dia, limpiar_dia,
    publicar_mes, despublicar_mes,
    get_turnos_mes, get_estados_mes,
    dias_sin_cumplimentar,
    get_notas_mes, guardar_nota_dia,
    marcar_saliente, quitar_saliente, get_salientes_mes,
)
from app.services.compat_planilla_persistente import actualizar_compat_tras_publicar_planilla
from app.services.volcar_cambios import get_matches_pendientes_volcar, volcar_matches_a_planilla
from app.services.eventos import registrar_evento
from app.services.unidad_usuario import unidad_activa_o_403, unidades_de


def _resolver_seleccion(seleccion, grupo_id):
    """Dado el valor del campo 'seleccion', devuelve (tipo_estado, franja_id) o (None, None) si inválido.
    tipo_estado es str si es un estado del día; franja_id es int si es un turno de trabajo.
    """
    if seleccion in TIPOS_ESTADO_DIA:
        return seleccion, None
    try:
        franja_id = int(seleccion)
        franja = db.session.get(FranjaHoraria, franja_id)
        if franja and franja.grupo_intercambio_id == grupo_id:
            return None, franja_id
    except (ValueError, TypeError):
        pass
    return None, None

bp = Blueprint("planilla", __name__, url_prefix="/planilla")


@bp.route("/")
@login_required
def index():
    hoy = date.today()
    anyo = request.args.get("anyo", hoy.year, type=int)
    mes  = request.args.get("mes",  hoy.month, type=int)

    unidad_id = request.args.get("unidad_id", type=int)
    unidad_activa = unidad_activa_o_403(current_user, unidad_id)

    _primer_dia_semana, num_dias = calendar.monthrange(anyo, mes)
    dias = [date(anyo, mes, d) for d in range(1, num_dias + 1)]

    turnos = get_turnos_mes(current_user, anyo, mes, unidad=unidad_activa)
    turnos_por_dia = {}
    for turno in turnos:
        turnos_por_dia.setdefault(turno.fecha, []).append(turno)

    estados_por_dia   = get_estados_mes(current_user, anyo, mes, unidad=unidad_activa)
    salientes_por_dia = get_salientes_mes(current_user, anyo, mes, unidad=unidad_activa)
    notas_por_dia     = get_notas_mes(current_user, anyo, mes, unidad=unidad_activa)
    num_vacios        = len(dias_sin_cumplimentar(current_user, anyo, mes, unidad=unidad_activa))
    matches_pendientes = get_matches_pendientes_volcar(current_user)

    planilla_mes_obj = PlanillaMes.query.filter_by(
        usuario_id=current_user.id, anyo=anyo, mes=mes, unidad_id=unidad_activa.id,
    ).first()

    franjas = (
        FranjaHoraria.query
        .filter_by(grupo_intercambio_id=unidad_activa.grupo_intercambio_id)
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
        salientes_por_dia=salientes_por_dia,
        notas_por_dia=notas_por_dia,
        num_vacios=num_vacios,
        matches_pendientes=matches_pendientes,
        planilla_mes=planilla_mes_obj,
        franjas=franjas,
        etiquetas_estado=ETIQUETAS_ESTADO,
        prev_anyo=prev_anyo, prev_mes=prev_mes,
        next_anyo=next_anyo, next_mes=next_mes,
        hoy=hoy,
        es_demo=current_user.es_demo,
        unidad_activa=unidad_activa,
        unidades=unidades_de(current_user),
    )


@bp.route("/dia/añadir", methods=["POST"])
@login_required
def dia_añadir():
    """Añade un turno de trabajo o establece un estado especial para el día."""
    fecha_str = request.form.get("fecha", "")
    seleccion = request.form.get("seleccion", "").strip()
    anyo = request.form.get("anyo", type=int)
    mes  = request.form.get("mes",  type=int)

    unidad_id = request.form.get("unidad_id", type=int)
    unidad_activa = unidad_activa_o_403(current_user, unidad_id)
    grupo_id = unidad_activa.grupo_intercambio_id

    try:
        fecha = date.fromisoformat(fecha_str)
    except ValueError:
        flash(_("Fecha inválida."), "error")
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    if not seleccion:
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    if seleccion == "saliente":
        marcar_saliente(current_user, fecha, unidad=unidad_activa)
    elif seleccion in TIPOS_ESTADO_DIA:
        establecer_estado_dia(current_user, fecha, seleccion, unidad=unidad_activa)
    else:
        try:
            franja_id = int(seleccion)
        except ValueError:
            flash(_("Selección no válida."), "error")
            return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

        franja = db.session.get(FranjaHoraria, franja_id)
        if not franja or franja.grupo_intercambio_id != grupo_id:
            flash(_("Turno no válido."), "error")
            return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

        añadir_turno(current_user, fecha, franja_id)

    return redirect(url_for("planilla.index", anyo=anyo, mes=mes, unidad_id=unidad_activa.id,
                            _anchor=f"dia-{fecha.isoformat()}"))


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
    return redirect(url_for("planilla.index", anyo=anyo, mes=mes, _anchor=f"dia-{fecha.isoformat()}",
                            unidad_id=session.get("unidad_activa_id")))


@bp.route("/saliente/quitar", methods=["POST"])
@login_required
def saliente_quitar():
    fecha_str = request.form.get("fecha", "")
    anyo = request.form.get("anyo", type=int)
    mes  = request.form.get("mes",  type=int)

    try:
        fecha = date.fromisoformat(fecha_str)
    except ValueError:
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    quitar_saliente(current_user, fecha)
    return redirect(url_for("planilla.index", anyo=anyo, mes=mes, _anchor=f"dia-{fecha.isoformat()}",
                            unidad_id=session.get("unidad_activa_id")))


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

    unidad_id = request.form.get("unidad_id", type=int)
    unidad_activa = unidad_activa_o_403(current_user, unidad_id)

    limpiar_dia(current_user, fecha, unidad=unidad_activa)
    return redirect(url_for("planilla.index", anyo=anyo, mes=mes, _anchor=f"dia-{fecha.isoformat()}",
                            unidad_id=unidad_activa.id))


@bp.route("/<int:anyo>/<int:mes>/publicar", methods=["POST"])
@login_required
def mes_publicar(anyo, mes):
    unidad_id = session.get("unidad_activa_id")
    unidad_activa = unidad_activa_o_403(current_user, unidad_id)
    vacios = dias_sin_cumplimentar(current_user, anyo, mes, unidad=unidad_activa)
    if vacios:
        n = len(vacios)
        primero = vacios[0].strftime("%-d/%m")
        flash(
            _(
                "La planilla está incompleta: %(n)s día(s) sin cumplimentar "
                "(el primero: %(primero)s). Añade un turno o marca cada día antes de publicar.",
                n=n, primero=primero,
            ),
            "error",
        )
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    planilla = publicar_mes(current_user, anyo, mes, unidad=unidad_activa)
    actualizar_compat_tras_publicar_planilla(current_user, anyo, mes)
    registrar_evento(current_user.id, "planilla_publicada", planilla.id)
    flash(_("Planilla del mes publicada. Tus compañeros ya pueden ver tu disponibilidad."), "success")
    return redirect(url_for("planilla.index", anyo=anyo, mes=mes,
                            unidad_id=session.get("unidad_activa_id")))


@bp.route("/<int:anyo>/<int:mes>/despublicar", methods=["POST"])
@login_required
def mes_despublicar(anyo, mes):
    unidad_id = session.get("unidad_activa_id")
    unidad_activa = unidad_activa_o_403(current_user, unidad_id)
    despublicar_mes(current_user, anyo, mes, unidad=unidad_activa)
    flash(_("Planilla retirada. Tus compañeros ya no verán tu disponibilidad este mes."), "info")
    return redirect(url_for("planilla.index", anyo=anyo, mes=mes,
                            unidad_id=session.get("unidad_activa_id")))


@bp.route("/mostrar-disponibilidad/toggle", methods=["POST"])
@login_required
def toggle_mostrar_disponibilidad():
    """Alterna si los compañeros pueden ver los días libres del usuario."""
    current_user.mostrar_disponibilidad = not current_user.mostrar_disponibilidad
    db.session.commit()

    if current_user.mostrar_disponibilidad:
        flash(_("Ahora tus compañeros pueden ver tus días libres."), "success")
    else:
        flash(_("Has ocultado tus días libres. Tus compañeros no verán cuándo estás libre."), "info")

    anyo = request.form.get("anyo", type=int)
    mes = request.form.get("mes", type=int)
    return redirect(url_for("planilla.index", anyo=anyo, mes=mes,
                            unidad_id=session.get("unidad_activa_id")))


@bp.route("/rango/aplicar", methods=["POST"])
@login_required
def rango_aplicar():
    """Rellena un rango de días consecutivos del mes con un mismo turno o estado."""
    dia_inicio = request.form.get("dia_inicio", type=int)
    dia_fin    = request.form.get("dia_fin",    type=int)
    seleccion  = request.form.get("seleccion",  "").strip()
    anyo = request.form.get("anyo", type=int)
    mes  = request.form.get("mes",  type=int)

    unidad_id = request.form.get("unidad_id", type=int)
    unidad_activa = unidad_activa_o_403(current_user, unidad_id)
    grupo_id = unidad_activa.grupo_intercambio_id

    _primer_dia_semana, num_dias = calendar.monthrange(anyo, mes)

    if not dia_inicio or not dia_fin or not seleccion:
        flash(_("Completa todos los campos del relleno rápido."), "error")
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    if dia_fin < dia_inicio:
        dia_inicio, dia_fin = dia_fin, dia_inicio

    dia_inicio = max(1, dia_inicio)
    dia_fin    = min(num_dias, dia_fin)

    tipo_estado, franja_id = _resolver_seleccion(seleccion, grupo_id=grupo_id)
    if tipo_estado is None and franja_id is None:
        flash(_("Selección no válida."), "error")
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    try:
        for d in range(dia_inicio, dia_fin + 1):
            fecha = date(anyo, mes, d)
            if tipo_estado:
                establecer_estado_dia(current_user, fecha, tipo_estado, unidad=unidad_activa, commit=False)
            else:
                añadir_turno(current_user, fecha, franja_id, unidad=unidad_activa, commit=False)
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash(_("Error al aplicar los cambios. No se ha modificado ningún día."), "error")
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    n = dia_fin - dia_inicio + 1
    flash(_("%(n)s día(s) actualizados.", n=n), "success")
    return redirect(url_for("planilla.index", anyo=anyo, mes=mes))


@bp.route("/multiples/aplicar", methods=["POST"])
@login_required
def multiples_aplicar():
    """Aplica un turno o estado a una lista de días concretos enviados desde el selector múltiple."""
    fechas_strs = request.form.getlist("fecha[]")
    seleccion   = request.form.get("seleccion",  "").strip()
    anyo = request.form.get("anyo", type=int)
    mes  = request.form.get("mes",  type=int)

    unidad_id = request.form.get("unidad_id", type=int)
    unidad_activa = unidad_activa_o_403(current_user, unidad_id)
    grupo_id = unidad_activa.grupo_intercambio_id

    if not seleccion or not fechas_strs:
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    tipo_estado, franja_id = _resolver_seleccion(seleccion, grupo_id=grupo_id)
    if tipo_estado is None and franja_id is None:
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    try:
        count = 0
        for fecha_str in fechas_strs:
            try:
                fecha = date.fromisoformat(fecha_str)
                if fecha.year != anyo or fecha.month != mes:
                    continue  # sólo fechas del mes visible
                if tipo_estado:
                    establecer_estado_dia(current_user, fecha, tipo_estado, unidad=unidad_activa, commit=False)
                else:
                    añadir_turno(current_user, fecha, franja_id, unidad=unidad_activa, commit=False)
                count += 1
            except ValueError:
                pass
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash(_("Error al aplicar los cambios. No se ha modificado ningún día."), "error")
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    if count:
        flash(_("%(count)s día(s) actualizados.", count=count), "success")
    return redirect(url_for("planilla.index", anyo=anyo, mes=mes))


@bp.route("/dia/nota", methods=["POST"])
@login_required
def dia_nota():
    """Guarda o actualiza la nota del día. Si el texto está vacío, la elimina."""
    fecha_str = request.form.get("fecha", "")
    texto = request.form.get("texto", "")
    anyo = request.form.get("anyo", type=int)
    mes  = request.form.get("mes",  type=int)

    try:
        fecha = date.fromisoformat(fecha_str)
    except ValueError:
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    unidad_id = request.form.get("unidad_id", type=int)
    unidad_activa = unidad_activa_o_403(current_user, unidad_id)
    guardar_nota_dia(current_user, fecha, texto, unidad=unidad_activa)
    return redirect(url_for("planilla.index", anyo=anyo, mes=mes, _anchor=f"dia-{fecha.isoformat()}",
                            unidad_id=session.get("unidad_activa_id")))


@bp.route("/volcar-cambios", methods=["POST"])
@login_required
def volcar_cambios():
    """Aplica los cambios confirmados seleccionados a la planilla del usuario."""
    anyo = request.form.get("anyo", type=int)
    mes  = request.form.get("mes",  type=int)
    ids_str = request.form.getlist("participacion_id[]")
    unidad_id = request.form.get("unidad_id", type=int)
    unidad_activa = unidad_activa_o_403(current_user, unidad_id)

    ids = []
    for s in ids_str:
        try:
            ids.append(int(s))
        except ValueError:
            pass

    if ids:
        n = volcar_matches_a_planilla(current_user, ids, unidad=unidad_activa)
        if n:
            flash(
                _(
                    "%(n)s cambio(s) volcado(s) a tu planilla. Las notas de los días afectados han sido actualizadas.",
                    n=n,
                ),
                "success",
            )

    return redirect(url_for("planilla.index", anyo=anyo, mes=mes,
                            unidad_id=session.get("unidad_activa_id")))


@bp.route("/vacios/aplicar", methods=["POST"])
@login_required
def vacios_aplicar():
    """Aplica un turno o estado a todos los días del mes que aún no tienen nada asignado."""
    seleccion = request.form.get("seleccion", "").strip()
    anyo = request.form.get("anyo", type=int)
    mes  = request.form.get("mes",  type=int)

    unidad_id = request.form.get("unidad_id", type=int)
    unidad_activa = unidad_activa_o_403(current_user, unidad_id)
    grupo_id = unidad_activa.grupo_intercambio_id

    if not seleccion:
        flash(_("Elige qué aplicar a los días vacíos."), "error")
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    tipo_estado, franja_id = _resolver_seleccion(seleccion, grupo_id=grupo_id)
    if tipo_estado is None and franja_id is None:
        flash(_("Selección no válida."), "error")
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    vacios = dias_sin_cumplimentar(current_user, anyo, mes, unidad=unidad_activa)
    if not vacios:
        flash(_("No hay días vacíos en este mes."), "info")
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    try:
        for fecha in vacios:
            if tipo_estado:
                establecer_estado_dia(current_user, fecha, tipo_estado, unidad=unidad_activa, commit=False)
            else:
                añadir_turno(current_user, fecha, franja_id, unidad=unidad_activa, commit=False)
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash(_("Error al aplicar los cambios. No se ha modificado ningún día."), "error")
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    flash(_("%(n)s día(s) vacío(s) rellenados.", n=len(vacios)), "success")
    return redirect(url_for("planilla.index", anyo=anyo, mes=mes))


# Mantener la ruta antigua para compatibilidad con tests existentes
@bp.route("/turno/añadir", methods=["POST"])
@login_required
def turno_añadir():
    fecha_str = request.form.get("fecha", "")
    franja_id = request.form.get("franja_id", type=int)
    anyo = request.form.get("anyo", type=int)
    mes  = request.form.get("mes",  type=int)

    unidad_id = request.form.get("unidad_id", type=int)
    unidad_activa = unidad_activa_o_403(current_user, unidad_id)
    grupo_id = unidad_activa.grupo_intercambio_id

    try:
        fecha = date.fromisoformat(fecha_str)
    except ValueError:
        flash(_("Fecha inválida."), "error")
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    if not franja_id:
        flash(_("Selecciona un turno."), "error")
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    franja = db.session.get(FranjaHoraria, franja_id)
    if not franja or franja.grupo_intercambio_id != grupo_id:
        flash(_("Turno no válido."), "error")
        return redirect(url_for("planilla.index", anyo=anyo, mes=mes))

    añadir_turno(current_user, fecha, franja_id, unidad=unidad_activa)
    return redirect(url_for("planilla.index", anyo=anyo, mes=mes, unidad_id=unidad_activa.id))
