"""Ruta que expone el asistente de parseo de mensajes de WhatsApp.

El asistente nunca puede impedir publicar: cualquier fallo (de la API, del
resolvedor, de datos) devuelve al usuario al formulario en blanco con un
aviso, nunca un error 500 ni un bloqueo.
"""
from datetime import date, datetime, time as dtime

from flask import Blueprint, flash, redirect, request, session, url_for
from flask_babel import _
from flask_login import current_user, login_required

from app.extensions import db
from app.models import FranjaHoraria, ParseoAsistente
from app.models.publicacion import TIPOS_PUBLICACION
from app.services.asistente.cliente import extraer_propuesta
from app.services.asistente.resolver import resolver_propuesta
from app.services.unidad_usuario import unidad_activa_o_403

bp = Blueprint("asistente", __name__, url_prefix="/asistente")

LIMITE_PARSEOS_DIA = 20


def _parseos_hoy(usuario_id):
    inicio_dia = datetime.combine(date.today(), dtime.min)
    return ParseoAsistente.query.filter(
        ParseoAsistente.usuario_id == usuario_id,
        ParseoAsistente.creado_en >= inicio_dia,
    ).count()


def _contexto_para(grupo_id):
    franjas = (
        FranjaHoraria.query
        .filter_by(grupo_intercambio_id=grupo_id)
        .order_by(FranjaHoraria.hora_inicio)
        .all()
    )
    return {
        "franjas": [
            {
                "nombre": f.nombre,
                "hora_inicio": f.hora_inicio.strftime("%H:%M"),
                "hora_fin": f.hora_fin.strftime("%H:%M"),
            }
            for f in franjas
        ],
        "tipos_validos": list(TIPOS_PUBLICACION),
        "hoy": date.today(),
    }


def _volver_al_formulario(mensaje):
    flash(mensaje, "warning")
    return redirect(url_for("publicaciones.nueva"))


@bp.post("/parsear")
@login_required
def parsear():
    if _parseos_hoy(current_user.id) >= LIMITE_PARSEOS_DIA:
        return _volver_al_formulario(
            _("Has alcanzado el límite diario de %(n)s usos del asistente. "
              "Rellena el formulario manualmente.", n=LIMITE_PARSEOS_DIA)
        )

    texto = request.form.get("texto", "").strip()
    if not texto:
        return redirect(url_for("publicaciones.nueva"))

    db.session.add(ParseoAsistente(usuario_id=current_user.id))
    db.session.commit()

    aviso_error = _(
        "El asistente no ha podido interpretar el mensaje. "
        "Rellena el formulario manualmente."
    )

    try:
        unidad_activa = unidad_activa_o_403(current_user, None)
        contexto = _contexto_para(unidad_activa.grupo_intercambio_id)
        propuesta = extraer_propuesta(texto, contexto)
        cedidos, aceptados, problemas = resolver_propuesta(propuesta, current_user, date.today())
    except Exception:
        return _volver_al_formulario(aviso_error)

    if problemas:
        return _volver_al_formulario(aviso_error)

    session["asistente_prefill"] = {
        "tipo": propuesta.tipo,
        "cedidos": [[fecha.isoformat(), franja_id] for fecha, franja_id in cedidos],
        "aceptados": [
            [fecha.isoformat(), franja_id if franja_id is not None else 0]
            for fecha, franja_id in aceptados
        ],
    }
    return redirect(url_for("publicaciones.nueva"))
