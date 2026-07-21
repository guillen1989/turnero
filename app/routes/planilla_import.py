from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user, login_required

from app.models import FranjaHoraria, Usuario
from app.models.planilla_import import MapeoTrabajadorPlanilla
from app.services.importar_planilla import importar_planilla
from app.services.planilla_matching import (
    establecer_mapeo_codigo,
    trabajadores_sin_vincular,
    usuarios_disponibles_para_vincular,
    vincular_usuario,
)

bp = Blueprint("planilla_import", __name__, url_prefix="/planilla/importar")


def _exigir_supervisora():
    if not current_user.es_supervisora:
        abort(403)

def _usuario_de_la_unidad(usuario_id, unidad_id):
    if not usuario_id:
        return None
    usuario = Usuario.query.get(usuario_id)
    if usuario is None or usuario.unidad_id != unidad_id:
        return None
    return usuario


@bp.get("/")
@login_required
def index():
    _exigir_supervisora()
    unidad = current_user.unidad
    return render_template(
        "planilla_import/index.html",
        pendientes=trabajadores_sin_vincular(unidad),
        usuarios=usuarios_disponibles_para_vincular(unidad),
    )


@bp.post("/")
@login_required
def subir():
    _exigir_supervisora()
    unidad = current_user.unidad

    archivo = request.files.get("archivo")
    if archivo is None or archivo.filename == "":
        flash(_("Selecciona un archivo de planilla."), "danger")
        return redirect(url_for("planilla_import.index"))

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
        return redirect(url_for("planilla_import.codigos"))

    flash(
        _(
            "%(actualizados)d trabajadores actualizados. "
            "%(pendientes)d sin vincular a una cuenta todavía.",
            actualizados=len(resultado.trabajadores_actualizados),
            pendientes=len(resultado.trabajadores_pendientes),
        ),
        "success",
    )
    return redirect(url_for("planilla_import.index"))


@bp.route("/codigos", methods=["GET", "POST"])
@login_required
def codigos():
    _exigir_supervisora()
    grupo = current_user.unidad.grupo_intercambio
    franjas = FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo.id).all()

    if request.method == "POST":
        for franja in franjas:
            codigos_raw = request.form.get(f"codigos_{franja.id}", "")
            for codigo in [c.strip().upper() for c in codigos_raw.split(",") if c.strip()]:
                establecer_mapeo_codigo(grupo, codigo, franja)
        flash(_("Códigos de turno configurados."), "success")
        return redirect(url_for("planilla_import.index"))

    return render_template("planilla_import/codigos.html", franjas=franjas)


@bp.post("/<int:mapeo_id>/vincular")
@login_required
def vincular(mapeo_id):
    _exigir_supervisora()
    mapeo = MapeoTrabajadorPlanilla.query.get_or_404(mapeo_id)
    if mapeo.unidad_id != current_user.unidad_id:
        abort(403)

    usuario_id = request.form.get("usuario_id", type=int)
    usuario = _usuario_de_la_unidad(usuario_id, current_user.unidad_id)
    if usuario is None:
        flash(_("Selecciona una cuenta válida."), "danger")
        return redirect(url_for("planilla_import.index"))

    vincular_usuario(mapeo, usuario)
    flash(_("Trabajador vinculado a %(nombre)s.", nombre=usuario.nombre), "success")
    return redirect(url_for("planilla_import.index"))
