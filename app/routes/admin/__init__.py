from functools import wraps

from flask import Blueprint, abort
from flask_login import current_user, login_required

bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.es_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


# Los submódulos registran sus rutas sobre `bp` al importarse; el orden no
# importa entre ellos, pero deben importarse después de definir `bp` y
# `admin_required` arriba, de los que dependen.
from app.routes.admin import (  # noqa: E402,F401
    analytics,
    demo,
    feature_flags,
    feedback,
    franjas,
    geografia,
    publicaciones,
    usuarios,
    vista_general,
)
