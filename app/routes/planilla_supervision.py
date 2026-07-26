import calendar
from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user, login_required

from app.extensions import db
from app.models.franja_horaria import FranjaHoraria
from app.models.planilla import ETIQUETAS_ESTADO, TIPOS_ESTADO_DIA
from app.models.unidad import Unidad
from app.models.usuario import Usuario
from app.services.planilla_supervision import (
    ajustar_turno_trabajador,
    editar_turno_trabajador,
    eliminar_turno_trabajador,
    get_ajustes_mes_unidad,
    get_cambios_autorizados_mes_unidad,
    get_conteos_presencia_mes_unidad,
    get_estados_mes_unidad,
    get_turnos_mes_unidad,
)
from app.services.supervision import puede_supervisar, unidades_supervisadas_de

bp = Blueprint("planilla_supervision", __name__, url_prefix="/planilla/supervision")


def _unidad_supervisada_o_403(unidad_id):
    unidades = unidades_supervisadas_de(current_user)
    if not unidades:
        abort(403)
    if unidad_id is None:
        return current_user.unidad if current_user.unidad in unidades else unidades[0]
    unidad = db.session.get(Unidad, unidad_id)
    if unidad is None or not puede_supervisar(current_user, unidad):
        abort(403)
    return unidad


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


def _franja_del_grupo(franja_id, grupo_id):
    if not franja_id:
        return None
    franja = db.session.get(FranjaHoraria, franja_id)
    if franja is None or franja.grupo_intercambio_id != grupo_id:
        return None
    return franja


def _turnos_a_json(turnos):
    return [{"franja_id": t.franja_horaria_id, "nombre": t.franja_horaria.nombre} for t in turnos]


def _estado_a_json(estado):
    if estado is None:
        return None
    return {"tipo": estado.tipo, "etiqueta": ETIQUETAS_ESTADO[estado.tipo]}


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
    if _franja_del_grupo(franja_id, grupo_id) is None:
        return None, None, False
    return None, franja_id, True


@bp.get("/")
@login_required
def index():
    unidad = _unidad_supervisada_o_403(request.args.get("unidad_id", type=int))

    hoy = date.today()
    anyo = request.args.get("anyo", hoy.year, type=int)
    mes = request.args.get("mes", hoy.month, type=int)

    _primer_dia_semana, num_dias = calendar.monthrange(anyo, mes)
    dias = [date(anyo, mes, d) for d in range(1, num_dias + 1)]

    trabajadores = [u for u in unidad.usuarios.order_by("nombre").all() if not u.eliminado]

    turnos_por_usuario_dia = get_turnos_mes_unidad(unidad, anyo, mes)
    estados_por_usuario_dia = get_estados_mes_unidad(unidad, anyo, mes)
    cambios_por_usuario_dia = get_cambios_autorizados_mes_unidad(unidad, anyo, mes)
    ajustes_por_usuario_dia = get_ajustes_mes_unidad(unidad, anyo, mes)
    conteos_presencia = get_conteos_presencia_mes_unidad(unidad, anyo, mes)

    turnos_json_por_usuario_dia = {
        clave: _turnos_a_json(turnos) for clave, turnos in turnos_por_usuario_dia.items()
    }
    estados_json_por_usuario_dia = {
        clave: _estado_a_json(estado) for clave, estado in estados_por_usuario_dia.items()
    }

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
        unidad=unidad,
        unidades_supervisadas=unidades_supervisadas_de(current_user),
        trabajadores=trabajadores,
        turnos_por_usuario_dia=turnos_por_usuario_dia,
        estados_por_usuario_dia=estados_por_usuario_dia,
        turnos_json_por_usuario_dia=turnos_json_por_usuario_dia,
        estados_json_por_usuario_dia=estados_json_por_usuario_dia,
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
    if request.method == "POST":
        unidad_id = request.form.get("unidad_id", type=int)
    else:
        unidad_id = request.args.get("unidad_id", type=int)
    unidad = _unidad_supervisada_o_403(unidad_id)
    grupo = unidad.grupo_intercambio

    if request.method == "POST":
        limite = request.form.get("limite_dias_consecutivos", type=int)
        if not limite or limite < 1:
            flash(_("Introduce un número de días válido (mayor que 0)."), "danger")
        else:
            grupo.limite_dias_consecutivos = limite
            db.session.commit()
            flash(_("Reglas de comprobación actualizadas."), "success")
        return redirect(url_for("planilla_supervision.reglas", unidad_id=unidad.id))

    return render_template(
        "planilla_supervision/reglas.html", grupo=grupo, unidad=unidad,
        unidades_supervisadas=unidades_supervisadas_de(current_user),
    )


@bp.post("/ajustar")
@login_required
def ajustar():
    unidad = _unidad_supervisada_o_403(request.form.get("unidad_id", type=int))

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
        return redirect(
            url_for("planilla_supervision.index", anyo=anyo, mes=mes, unidad_id=unidad.id)
        )

    # Elegir un turno siempre añade (permite doblajes); elegir un estado
    # especial o vaciar el día siempre sustituye lo que hubiera.
    sustituir = franja_id is None

    ajustar_turno_trabajador(
        current_user, trabajador, fecha,
        tipo_estado=tipo_estado, franja_id=franja_id, motivo=motivo,
        sustituir=sustituir,
    )
    flash(_("Turno de %(nombre)s actualizado.", nombre=trabajador.nombre), "success")
    return redirect(
        url_for("planilla_supervision.index", anyo=anyo, mes=mes, unidad_id=unidad.id)
    )


@bp.post("/turno/eliminar")
@login_required
def turno_eliminar():
    unidad = _unidad_supervisada_o_403(request.form.get("unidad_id", type=int))

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

    franja_id = request.form.get("franja_id", type=int)
    if _franja_del_grupo(franja_id, unidad.grupo_intercambio_id) is None:
        abort(400)

    motivo = request.form.get("motivo", "").strip() or None
    eliminar_turno_trabajador(current_user, trabajador, fecha, franja_id, motivo=motivo)
    flash(_("Turno de %(nombre)s eliminado.", nombre=trabajador.nombre), "success")
    return redirect(
        url_for("planilla_supervision.index", anyo=anyo, mes=mes, unidad_id=unidad.id)
    )


@bp.post("/turno/editar")
@login_required
def turno_editar():
    unidad = _unidad_supervisada_o_403(request.form.get("unidad_id", type=int))

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

    franja_actual_id = request.form.get("franja_actual_id", type=int)
    franja_nueva_id = request.form.get("franja_nueva_id", type=int)
    if (
        _franja_del_grupo(franja_actual_id, unidad.grupo_intercambio_id) is None
        or _franja_del_grupo(franja_nueva_id, unidad.grupo_intercambio_id) is None
    ):
        abort(400)

    motivo = request.form.get("motivo", "").strip() or None
    editar_turno_trabajador(
        current_user, trabajador, fecha, franja_actual_id, franja_nueva_id, motivo=motivo
    )
    flash(_("Turno de %(nombre)s modificado.", nombre=trabajador.nombre), "success")
    return redirect(
        url_for("planilla_supervision.index", anyo=anyo, mes=mes, unidad_id=unidad.id)
    )
