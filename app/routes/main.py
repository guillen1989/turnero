from flask import Blueprint, jsonify, render_template
from flask_login import current_user

from app.extensions import db
from app.models import MatchCambio, MatchParticipacion, PublicacionCambio
from app.services.caducidad import caducar_publicaciones_expiradas

bp = Blueprint("main", __name__)


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


def _matches_activos(usuario_id):
    """Devuelve lista de (match, mi_participacion, otra_participacion) pendientes del usuario."""
    raw = (
        MatchCambio.query
        .join(MatchParticipacion, MatchCambio.id == MatchParticipacion.match_id)
        .join(PublicacionCambio, MatchParticipacion.publicacion_id == PublicacionCambio.id)
        .filter(
            PublicacionCambio.usuario_id == usuario_id,
            MatchCambio.estado.in_(["propuesto", "confirmado_parcial"]),
        )
        .distinct()
        .all()
    )
    resultado = []
    for match in raw:
        mi = next((p for p in match.participaciones if p.publicacion.usuario_id == usuario_id), None)
        otra = next((p for p in match.participaciones if p.publicacion.usuario_id != usuario_id), None)
        if mi and otra:
            resultado.append((match, mi, otra))
    return resultado


@bp.get("/")
def index():
    if current_user.is_authenticated:
        caducar_publicaciones_expiradas()
        publicaciones = (
            PublicacionCambio.query
            .filter_by(usuario_id=current_user.id)
            .order_by(PublicacionCambio.fecha_creacion.desc())
            .all()
        )
        matches = _matches_activos(current_user.id)
        return render_template("main/dashboard.html", publicaciones=publicaciones, matches=matches)
    return render_template("main/index.html")
