from flask import Blueprint, redirect, request, url_for
from flask_login import current_user, login_required

from app.models import FranjaHoraria
from app.services.busquedas_guardadas import eliminar_busqueda, guardar_busqueda

bp = Blueprint("busquedas", __name__)

_TIPOS_VALIDOS = {"cambio", "regalo", "peticion", "junte", "cambio_dia"}


@bp.post("/busquedas-guardadas")
@login_required
def guardar():
    filtros = {}

    mes = request.form.get("mes", type=int)
    dia = request.form.get("dia", type=int)
    franja_id = request.form.get("franja", type=int)
    tipo = request.form.get("tipo", "").strip()
    nombre = request.form.get("usuario", "").strip()
    tipo_fecha = request.form.get("tipo_fecha", "").strip()

    if tipo in _TIPOS_VALIDOS:
        filtros["tipo"] = tipo
    if mes:
        filtros["mes"] = mes
    if dia:
        filtros["dia"] = dia
    if franja_id:
        franja = FranjaHoraria.query.get(franja_id)
        if franja and franja.grupo_intercambio_id == current_user.grupo_intercambio.id:
            filtros["franja_id"] = franja_id
            filtros["franja_nombre"] = franja.nombre
    if nombre:
        filtros["nombre"] = nombre
    if tipo_fecha in {"cedido", "aceptado"}:
        filtros["tipo_fecha"] = tipo_fecha

    guardar_busqueda(current_user.id, filtros)
    return redirect(url_for("main.cambios", tab="alertas"))


@bp.post("/busquedas-guardadas/<int:busqueda_id>/eliminar")
@login_required
def eliminar(busqueda_id):
    eliminar_busqueda(busqueda_id, current_user.id)
    return redirect(url_for("main.cambios", tab="alertas"))
