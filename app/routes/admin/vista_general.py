from flask import render_template

from app.models import Categoria, Hospital, Pais, PublicacionCambio, Unidad, Usuario
from app.routes.admin import admin_required, bp


@bp.route("/")
@admin_required
def index():
    stats = {
        "usuarios": Usuario.query.count(),
        "paises": Pais.query.count(),
        "hospitales": Hospital.query.count(),
        "unidades": Unidad.query.count(),
        "categorias": Categoria.query.count(),
        "publicaciones": PublicacionCambio.query.count(),
    }
    return render_template("admin/index.html", stats=stats)
