from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user, login_required

from app.extensions import db
from app.models import FranjaHoraria, GrupoIntercambio, PublicacionCambio
from app.services.publicaciones import cancelar_publicacion, publicar_cambio
from app.services.registro import crear_franjas_default
from app.matching.service import buscar_matches_para, crear_match_directo

bp = Blueprint("publicaciones", __name__)


def _extraer_turnos(prefix):
    """Extrae pares (fecha, franja_id) del form con claves fecha_{prefix}_N / franja_{prefix}_N."""
    turnos = []
    idx = 0
    while True:
        fecha_str = request.form.get(f"fecha_{prefix}_{idx}", "").strip()
        franja_str = request.form.get(f"franja_{prefix}_{idx}", "").strip()
        if not fecha_str or not franja_str:
            break
        try:
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            franja_id = int(franja_str)
            turnos.append((fecha, franja_id))
        except (ValueError, TypeError):
            pass
        idx += 1
    return turnos


def _asegurar_franjas(grupo_intercambio_id):
    """Si el grupo no tiene franjas (usuarios anteriores al seeding), las crea ahora."""
    if FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_intercambio_id).count() == 0:
        grupo = db.session.get(GrupoIntercambio, grupo_intercambio_id)
        crear_franjas_default(grupo)
        db.session.commit()


@bp.route("/publicar", methods=["GET", "POST"])
@login_required
def nueva():
    grupo_id = current_user.unidad.grupo_intercambio_id
    _asegurar_franjas(grupo_id)
    franjas = (
        FranjaHoraria.query
        .filter_by(grupo_intercambio_id=grupo_id)
        .order_by(FranjaHoraria.hora_inicio)
        .all()
    )

    if request.method == "POST":
        cedidos = _extraer_turnos("cedida")
        aceptados = _extraer_turnos("aceptada")

        if not cedidos:
            flash(_("Debes indicar al menos un turno que cedes."), "danger")
            return render_template("publicaciones/publicar.html", franjas=franjas)

        if not aceptados:
            flash(_("Debes indicar al menos un turno que aceptarías."), "danger")
            return render_template("publicaciones/publicar.html", franjas=franjas)

        pub = publicar_cambio(current_user.id, cedidos, aceptados)
        for candidata in buscar_matches_para(pub):
            crear_match_directo(pub, candidata)
        flash(_("Publicación creada correctamente."), "success")
        return redirect(url_for("main.index"))

    return render_template("publicaciones/publicar.html", franjas=franjas)


@bp.post("/publicaciones/<int:pub_id>/cancelar")
@login_required
def cancelar(pub_id):
    pub = db.get_or_404(PublicacionCambio, pub_id)
    if pub.usuario_id != current_user.id:
        abort(403)
    if not pub.esta_activa():
        abort(409)
    cancelar_publicacion(pub)
    flash(_("Publicación cancelada."), "info")
    return redirect(url_for("main.index"))
