import calendar
from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user, login_required

from app.extensions import db
from app.models.franja_horaria import FranjaHoraria
from app.models.planilla import ETIQUETAS_ESTADO, TIPOS_ESTADO_DIA
from app.models.usuario import Usuario
from app.services.planilla_supervision import (
    ajustar_turno_trabajador,
    get_ajustes_mes_unidad,
    get_cambios_autorizados_mes_unidad,
    get_conteos_presencia_mes_unidad,
    get_estados_mes_unidad,
    get_turnos_mes_unidad,
)

bp = Blueprint("planilla_supervision", __name__, url_prefix="/planilla/supervision")


def _exigir_supervisora():
    if not current_user.es_supervisora:
        abort(403)


def _usuario_de_la_unidad(usuario_id, unidad_id):
    if not usuario_id:
        return None
    usuario = db.session.get(Usuario, usuario_id)
    if usuario is None or usuario.unidad_id != unidad_id:
        return None
    return usuario


def _parsear_fecha(valor):
    try:
        return date.fromisoformat(valor)
    except (ValueError, TypeError):
        return None


def _resolver_seleccion(seleccion, grupo_id):
    """Devuelve (tipo_estado, franja_id, valido). 'vaciar' es una opción
    explícita y válida (deja el día sin turno ni estado)."""
    if seleccion == "vaciar":
        return None, None, True
    if seleccion in TIPOS_ESTADO_DIA:
        return seleccion, None, True
    try:
        franja_id = int(seleccion)
    except (ValueError, TypeError):
        return None, None, False
    franja = db.session.get(FranjaHoraria, franja_id)
    if franja and franja.grupo_intercambio_id == grupo_id:
        return None, franja_id, True
    return None, None, False


@bp.get("/")
@login_required
def index():
    _exigir_supervisora()
    unidad = current_user.unidad

    hoy = date.today()
    anyo = request.args.get("anyo", hoy.year, type=int)
    mes = request.args.get("mes", hoy.month, type=int)

    _primer_dia_semana, num_dias = calendar.monthrange(anyo, mes)
    dias = [date(anyo, mes, d) for d in range(1, num_dias + 1)]

    trabajadores = unidad.usuarios.order_by("nombre").all()

    turnos_por_usuario_dia = get_turnos_mes_unidad(unidad, anyo, mes)
    estados_por_usuario_dia = get_estados_mes_unidad(unidad, anyo, mes)
    cambios_por_usuario_dia = get_cambios_autorizados_mes_unidad(unidad, anyo, mes)
    ajustes_por_usuario_dia = get_ajustes_mes_unidad(unidad, anyo, mes)
    conteos_presencia = get_conteos_presencia_mes_unidad(unidad, anyo, mes)

    franjas = (
        FranjaHoraria.query
        .filter_by(grupo_intercambio_id=unidad.grupo_intercambio_id)
        .order_by(FranjaHoraria.hora_inicio)
        .all()
    )

    prev_mes = mes - 1 if mes > 1 else 12
    prev_anyo = anyo if mes > 1 else anyo - 1
    next_mes = mes + 1 if mes < 12 else 1
    next_anyo = anyo if mes < 12 else anyo + 1

    return render_template(
        "planilla_supervision/index.html",
        anyo=anyo, mes=mes, dias=dias,
        trabajadores=trabajadores,
        turnos_por_usuario_dia=turnos_por_usuario_dia,
        estados_por_usuario_dia=estados_por_usuario_dia,
        cambios_por_usuario_dia=cambios_por_usuario_dia,
        ajustes_por_usuario_dia=ajustes_por_usuario_dia,
        conteos_presencia=conteos_presencia,
        etiquetas_estado=ETIQUETAS_ESTADO,
        franjas=franjas,
        hoy=hoy,
        prev_anyo=prev_anyo, prev_mes=prev_mes,
        next_anyo=next_anyo, next_mes=next_mes,
    )


@bp.route("/reglas", methods=["GET", "POST"])
@login_required
def reglas():
    _exigir_supervisora()
    grupo = current_user.unidad.grupo_intercambio

    if request.method == "POST":
        limite = request.form.get("limite_dias_consecutivos", type=int)
        if not limite or limite < 1:
            flash(_("Introduce un número de días válido (mayor que 0)."), "danger")
        else:
            grupo.limite_dias_consecutivos = limite
            db.session.commit()
            flash(_("Reglas de comprobación actualizadas."), "success")
        return redirect(url_for("planilla_supervision.reglas"))

    return render_template("planilla_supervision/reglas.html", grupo=grupo)


@bp.post("/ajustar")
@login_required
def ajustar():
    _exigir_supervisora()
    unidad = current_user.unidad

    trabajador = _usuario_de_la_unidad(
        request.form.get("usuario_id", type=int), unidad.id
    )
    if trabajador is None:
        abort(403)

    fecha = _parsear_fecha(request.form.get("fecha", ""))
    if fecha is None:
        abort(400)

    anyo = request.form.get("anyo", fecha.year, type=int)
    mes = request.form.get("mes", fecha.month, type=int)

    seleccion = request.form.get("seleccion", "")
    motivo = request.form.get("motivo", "").strip() or None

    tipo_estado, franja_id, valido = _resolver_seleccion(
        seleccion, unidad.grupo_intercambio_id
    )
    if not valido:
        flash(_("Selecciona una opción válida."), "danger")
        return redirect(url_for("planilla_supervision.index", anyo=anyo, mes=mes))

    ajustar_turno_trabajador(
        current_user, trabajador, fecha,
        tipo_estado=tipo_estado, franja_id=franja_id, motivo=motivo,
    )
    flash(_("Turno de %(nombre)s actualizado.", nombre=trabajador.nombre), "success")
    return redirect(url_for("planilla_supervision.index", anyo=anyo, mes=mes))
