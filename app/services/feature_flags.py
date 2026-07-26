from functools import wraps

from flask import abort

from app.extensions import db
from app.models import FeatureFlag, FeatureFlagUnidad


def feature_activa(clave, unidad=None):
    """True si el flag está activo globalmente, o si `unidad` está en su
    lista de unidades habilitadas. Si el flag no existe, False (fail
    closed: una funcionalidad sin flag registrado nunca se asume activa)."""
    flag = FeatureFlag.query.filter_by(clave=clave).first()
    if flag is None:
        return False
    if flag.activo_global:
        return True
    return unidad is not None and unidad in flag.unidades_habilitadas


def crear_flag(clave, descripcion=""):
    flag = FeatureFlag(clave=clave, descripcion=descripcion)
    db.session.add(flag)
    db.session.commit()
    return flag


def _obtener_flag(clave):
    return FeatureFlag.query.filter_by(clave=clave).one()


def activar_global(clave):
    _obtener_flag(clave).activo_global = True
    db.session.commit()


def desactivar_global(clave):
    _obtener_flag(clave).activo_global = False
    db.session.commit()


def habilitar_para_unidad(clave, unidad):
    flag = _obtener_flag(clave)
    if unidad not in flag.unidades_habilitadas:
        flag.unidades_habilitadas.append(unidad)
        db.session.commit()


def deshabilitar_para_unidad(clave, unidad):
    flag = _obtener_flag(clave)
    if unidad in flag.unidades_habilitadas:
        flag.unidades_habilitadas.remove(unidad)
        db.session.commit()


def sincronizar_unidades_habilitadas(flag, unidad_ids):
    """Deja las FeatureFlagUnidad del flag exactamente en unidad_ids."""
    deseadas = set(unidad_ids)
    actuales = {unidad.id for unidad in flag.unidades_habilitadas}

    for unidad_id in deseadas - actuales:
        db.session.add(FeatureFlagUnidad(feature_flag_id=flag.id, unidad_id=unidad_id))

    a_quitar = actuales - deseadas
    if a_quitar:
        FeatureFlagUnidad.query.filter(
            FeatureFlagUnidad.feature_flag_id == flag.id,
            FeatureFlagUnidad.unidad_id.in_(a_quitar),
        ).delete(synchronize_session=False)


def _unidad_usuario_actual():
    from flask_login import current_user
    if not current_user.is_authenticated:
        return None
    return getattr(current_user, "unidad", None)


def feature_activa_para_usuario_actual(clave):
    return feature_activa(clave, _unidad_usuario_actual())


def requiere_feature(clave):
    """Oculta una ruta entera con 404 si el flag no está activo (nunca un
    mensaje "próximamente" que confirmaría que la funcionalidad existe)."""

    def decorador(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not feature_activa_para_usuario_actual(clave):
                abort(404)
            return f(*args, **kwargs)
        return decorated
    return decorador
