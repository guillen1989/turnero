import calendar
from datetime import date

from flask import Blueprint, abort, render_template, request
from flask_login import current_user, login_required

from app.services.planilla_supervision import (
    get_cambios_autorizados_mes_unidad,
    get_estados_mes_unidad,
    get_turnos_mes_unidad,
)

bp = Blueprint("planilla_supervision", __name__, url_prefix="/planilla/supervision")

ETIQUETAS_ESTADO = {
    "libre":         "Libre",
    "vacaciones":    "Vacaciones",
    "no_disponible": "No disponible",
}


def _exigir_supervisora():
    if not current_user.es_supervisora:
        abort(403)


@bp.get("/")
@login_required
def index():
    _exigir_supervisora()
    unidad = current_user.unidad

    hoy = date.today()
    anyo = request.args.get("anyo", hoy.year, type=int)
    mes = request.args.get("mes", hoy.month, type=int)

    _, num_dias = calendar.monthrange(anyo, mes)
    dias = [date(anyo, mes, d) for d in range(1, num_dias + 1)]

    trabajadores = unidad.usuarios.order_by("nombre").all()

    turnos_por_usuario_dia = get_turnos_mes_unidad(unidad, anyo, mes)
    estados_por_usuario_dia = get_estados_mes_unidad(unidad, anyo, mes)
    cambios_por_usuario_dia = get_cambios_autorizados_mes_unidad(unidad, anyo, mes)

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
        etiquetas_estado=ETIQUETAS_ESTADO,
        hoy=hoy,
        prev_anyo=prev_anyo, prev_mes=prev_mes,
        next_anyo=next_anyo, next_mes=next_mes,
    )
