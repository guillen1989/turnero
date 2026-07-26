from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user, login_required

from app.models import FranjaHoraria, Usuario
from app.models.planilla_import import MapeoTrabajadorPlanilla
from app.services.importar_planilla import importar_planilla
from app.services.planilla_matching import (
    descartar_trabajadores,
    establecer_mapeo_codigo,
    trabajadores_sin_vincular,
    usuarios_disponibles_para_vincular,
    vincular_usuario,
)
from app.services.supervision import puede_supervisar, unidad_supervisada_o_403, unidades_supervisadas_de
from app.services.feature_flags import requiere_feature

bp = Blueprint("planilla_import", __name__, url_prefix="/planilla/importar")


def _usuario_de_la_unidad(usuario_id, unidad_id):
    if not usuario_id:
        return None
    usuario = Usuario.query.get(usuario_id)
    if usuario is None or usuario.unidad_id != unidad_id:
        return None
    return usuario


@bp.get("/")
@login_required
@requiere_feature("importacion_planilla")
def index():
    unidad = unidad_supervisada_o_403(current_user, request.args.get("unidad_id", type=int))
    return render_template(
        "planilla_import/index.html",
        unidad=unidad,
        unidades_supervisadas=unidades_supervisadas_de(current_user),
        pendientes=trabajadores_sin_vincular(unidad),
        usuarios=usuarios_disponibles_para_vincular(unidad),
    )


@bp.post("/")
@login_required
@requiere_feature("importacion_planilla")
def subir():
    unidad = unidad_supervisada_o_403(current_user, request.form.get("unidad_id", type=int))

    archivo = request.files.get("archivo")
    if archivo is None or archivo.filename == "":
        flash(_("Selecciona un archivo de planilla."), "danger")
        return redirect(url_for("planilla_import.index", unidad_id=unidad.id))

    contenido = archivo.stream.read().decode("latin-1")
    resultado = importar_planilla(contenido, unidad)

    if resultado.codigos_sin_mapear:
        codigos = ", ".join(sorted(resultado.codigos_sin_mapear))
        flash(
            _(
                "Faltan por configurar estos códigos de turno: %(codigos)s. "
                "Configúralos y vuelve a subir el archivo.",
                codigos=codigos,
            ),
            "danger",
        )
        return redirect(url_for("planilla_import.codigos", unidad_id=unidad.id))

    flash(
        _(
            "%(actualizados)d trabajadores actualizados. "
            "%(pendientes)d sin vincular a una cuenta todavía.",
            actualizados=len(resultado.trabajadores_actualizados),
            pendientes=len(resultado.trabajadores_pendientes),
        ),
        "success",
    )
    return redirect(url_for("planilla_import.index", unidad_id=unidad.id))


@bp.route("/codigos", methods=["GET", "POST"])
@login_required
@requiere_feature("importacion_planilla")
def codigos():
    if request.method == "POST":
        unidad_id = request.form.get("unidad_id", type=int)
    else:
        unidad_id = request.args.get("unidad_id", type=int)
    unidad = unidad_supervisada_o_403(current_user, unidad_id)
    grupo = unidad.grupo_intercambio
    franjas = FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo.id).all()

    if request.method == "POST":
        for franja in franjas:
            codigos_raw = request.form.get(f"codigos_{franja.id}", "")
            for codigo in [c.strip().upper() for c in codigos_raw.split(",") if c.strip()]:
                establecer_mapeo_codigo(grupo, codigo, franja)
        flash(_("Códigos de turno configurados."), "success")
        return redirect(url_for("planilla_import.index", unidad_id=unidad.id))

    return render_template(
        "planilla_import/codigos.html",
        franjas=franjas,
        unidad=unidad,
        unidades_supervisadas=unidades_supervisadas_de(current_user),
    )


@bp.post("/descartar")
@login_required
@requiere_feature("importacion_planilla")
def descartar():
    unidad = unidad_supervisada_o_403(current_user, request.form.get("unidad_id", type=int))
    mapeo_ids = request.form.getlist("mapeo_ids", type=int)

    if not mapeo_ids:
        flash(_("Selecciona al menos un trabajador."), "danger")
    else:
        n = descartar_trabajadores(unidad, mapeo_ids)
        flash(_("%(n)d trabajadores dejados sin asignar.", n=n), "success")

    return redirect(url_for("planilla_import.index", unidad_id=unidad.id))


@bp.post("/<int:mapeo_id>/vincular")
@login_required
@requiere_feature("importacion_planilla")
def vincular(mapeo_id):
    mapeo = MapeoTrabajadorPlanilla.query.get_or_404(mapeo_id)
    if not puede_supervisar(current_user, mapeo.unidad):
        abort(403)

    usuario_id = request.form.get("usuario_id", type=int)
    usuario = _usuario_de_la_unidad(usuario_id, mapeo.unidad_id)
    if usuario is None:
        flash(_("Selecciona una cuenta válida."), "danger")
        return redirect(url_for("planilla_import.index", unidad_id=mapeo.unidad_id))

    vincular_usuario(mapeo, usuario)
    flash(_("Trabajador vinculado a %(nombre)s.", nombre=usuario.nombre), "success")
    return redirect(url_for("planilla_import.index", unidad_id=mapeo.unidad_id))
