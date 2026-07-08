import calendar
from datetime import date

from flask import Blueprint, render_template, request
from flask_login import login_required, current_user

from app.models.franja_horaria import FranjaHoraria
from app.services.calendario_mercado import CUALQUIER_FRANJA, construir_calendario_mes

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

    _, num_dias = calendar.monthrange(anyo, mes)
    dias = [date(anyo, mes, d) for d in range(1, num_dias + 1)]

    calendario_mes = construir_calendario_mes(current_user, anyo, mes, modo)

    franjas = (
        FranjaHoraria.query
        .filter_by(grupo_intercambio_id=current_user.grupo_intercambio.id)
        .order_by(FranjaHoraria.hora_inicio)
        .all()
    )
    nombre_franja = {f.id: f.nombre for f in franjas}

    prev_mes = mes - 1 if mes > 1 else 12
    prev_anyo = anyo if mes > 1 else anyo - 1
    next_mes = mes + 1 if mes < 12 else 1
    next_anyo = anyo if mes < 12 else anyo + 1

    return render_template(
        "calendario/calendario.html",
        anyo=anyo, mes=mes, dias=dias, modo=modo,
        calendario_mes=calendario_mes,
        franjas=franjas,
        nombre_franja=nombre_franja,
        cualquier_franja_clave=CUALQUIER_FRANJA,
        prev_anyo=prev_anyo, prev_mes=prev_mes,
        next_anyo=next_anyo, next_mes=next_mes,
        hoy=hoy,
    )
