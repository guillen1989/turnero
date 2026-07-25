from flask import abort, flash, redirect, render_template, request, url_for
from flask_babel import _

from app.extensions import db
from app.models import MatchCambio, MatchParticipacion, PublicacionCambio, Usuario
from app.routes.admin import admin_required, bp
from app.services.publicaciones import eliminar_publicacion


def _matches_info_por_pub(publicaciones):
    """Devuelve un dict {pub_id: {partners, fecha_match, fecha_confirmacion}}."""
    pub_ids = [p.id for p in publicaciones]
    if not pub_ids:
        return {}

    participaciones = (
        MatchParticipacion.query
        .filter(MatchParticipacion.publicacion_id.in_(pub_ids))
        .all()
    )
    match_ids = {p.match_id for p in participaciones}
    if not match_ids:
        return {}

    matches = {m.id: m for m in MatchCambio.query.filter(MatchCambio.id.in_(match_ids)).all()}
    todas_parts = (
        MatchParticipacion.query
        .filter(MatchParticipacion.match_id.in_(match_ids))
        .all()
    )

    result = {}
    for part in participaciones:
        match = matches[part.match_id]
        if match.estado in ("rechazado",):
            continue
        partners = [
            p.publicacion.usuario.nombre
            for p in todas_parts
            if p.match_id == match.id and p.publicacion_id != part.publicacion_id
        ]
        existing = result.get(part.publicacion_id)
        if existing is None or (match.fecha_creacion and (
            existing["fecha_match"] is None or match.fecha_creacion < existing["fecha_match"]
        )):
            result[part.publicacion_id] = {
                "partners": partners,
                "fecha_match": match.fecha_creacion,
                "fecha_confirmacion": match.fecha_confirmacion_total,
            }
    return result


_SORT_COLUMNS = {
    "usuario": Usuario.nombre,
    "estado": PublicacionCambio.estado,
    "fecha": PublicacionCambio.fecha_creacion,
}


@bp.route("/publicaciones")
@admin_required
def publicaciones():
    sort = request.args.get("sort", "fecha")
    order = request.args.get("order", "desc")

    col = _SORT_COLUMNS.get(sort, PublicacionCambio.fecha_creacion)
    col_sorted = col.asc() if order == "asc" else col.desc()

    todas = (
        PublicacionCambio.query
        .join(Usuario)
        .order_by(col_sorted)
        .all()
    )
    matches_info = _matches_info_por_pub(todas)
    return render_template(
        "admin/publicaciones.html",
        publicaciones=todas,
        matches_info=matches_info,
        sort=sort,
        order=order,
    )


@bp.route("/publicaciones/<int:id>/cancelar", methods=["POST"])
@admin_required
def publicacion_cancelar(id):
    p = db.session.get(PublicacionCambio, id) or abort(404)
    p.estado = "cancelada"
    db.session.commit()
    flash(_("Publicación cancelada."), "success")
    return redirect(url_for("admin.publicaciones"))


@bp.route("/publicaciones/<int:id>/eliminar", methods=["POST"])
@admin_required
def publicacion_eliminar(id):
    p = db.session.get(PublicacionCambio, id) or abort(404)
    eliminar_publicacion(p)
    flash(_("Publicación eliminada."), "success")
    return redirect(url_for("admin.publicaciones"))
