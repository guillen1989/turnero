import calendar
from datetime import date

from flask import Blueprint, render_template, request
from flask_babel import _
from flask_login import login_required, current_user

from app.models.franja_horaria import FranjaHoraria
from app.services.calendario_mercado import (
    CUALQUIER_FRANJA,
    construir_calendario_mes,
    preparar_celdas_mes,
    resumen_publicaciones,
)

bp = Blueprint("calendario", __name__, url_prefix="/calendario")

MODOS_VALIDOS = ("ofertas", "peticiones")


@bp.route("/")
@login_required
def index():
    hoy = date.today()
    anyo = request.args.get("anyo", hoy.year, type=int)
    mes = request.args.get("mes", hoy.month, type=int)
    modo = request.args.get("modo", "ofertas")
    if modo not in MODOS_VALIDOS:
        modo = "ofertas"

    _primer_dia_semana, num_dias = calendar.monthrange(anyo, mes)
    dias = [date(anyo, mes, d) for d in range(1, num_dias + 1)]

    calendario_mes = construir_calendario_mes(current_user, anyo, mes, modo)

    franjas = (
        FranjaHoraria.query
        .filter_by(grupo_intercambio_id=current_user.grupo_intercambio.id)
        .order_by(FranjaHoraria.hora_inicio)
        .all()
    )
    celdas = preparar_celdas_mes(dias, calendario_mes, franjas)

    claves_usadas = {clave for franjas_dia in calendario_mes.values() for clave in franjas_dia}
    nombre_franja_por_id = {f.id: f.nombre for f in franjas}
    nombre_franja_por_clave = {
        str(clave): (_("Cualquiera") if clave == CUALQUIER_FRANJA else nombre_franja_por_id.get(clave, "?"))
        for clave in claves_usadas
    }

    datos_mes = {
        dia.isoformat(): {str(clave): ids for clave, ids in franjas_dia.items()}
        for dia, franjas_dia in calendario_mes.items()
    }

    pub_ids = {pid for franjas_dia in calendario_mes.values() for ids in franjas_dia.values() for pid in ids}
    tipo_labels = {
        "cambio": _("Cambio"),
        "regalo": _("Regalo"),
        "peticion": _("Petición"),
        "cambio_dia": _("Cambio de turno en el día"),
    }
    datos_publicaciones = {
        str(p["id"]): {
            "usuario_nombre": p["usuario_nombre"],
            "tipo_label": tipo_labels.get(p["tipo"], p["tipo"]),
        }
        for p in resumen_publicaciones(pub_ids)
    }

    prev_mes = mes - 1 if mes > 1 else 12
    prev_anyo = anyo if mes > 1 else anyo - 1
    next_mes = mes + 1 if mes < 12 else 1
    next_anyo = anyo if mes < 12 else anyo + 1

    return render_template(
        "calendario/calendario.html",
        anyo=anyo, mes=mes, dias=dias, modo=modo,
        celdas=celdas,
        nombre_franja_por_clave=nombre_franja_por_clave,
        datos_mes=datos_mes,
        datos_publicaciones=datos_publicaciones,
        prev_anyo=prev_anyo, prev_mes=prev_mes,
        next_anyo=next_anyo, next_mes=next_mes,
        hoy=hoy,
    )
