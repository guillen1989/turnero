from flask import Blueprint, jsonify, render_template
from flask_login import current_user

from app.models import PublicacionCambio

bp = Blueprint("main", __name__)


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@bp.get("/")
def index():
    if current_user.is_authenticated:
        publicaciones = (
            PublicacionCambio.query
            .filter_by(usuario_id=current_user.id)
            .order_by(PublicacionCambio.fecha_creacion.desc())
            .all()
        )
        return render_template("main/dashboard.html", publicaciones=publicaciones)
    return render_template("main/index.html")
