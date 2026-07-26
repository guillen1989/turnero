from app.extensions import db
from app.models import FeatureFlag


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
