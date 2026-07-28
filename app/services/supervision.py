from flask import abort

from app.extensions import db
from app.models.unidad import Unidad
from app.models.unidad_supervisada import UnidadSupervisada


def unidades_supervisadas_de(usuario):
    return sorted(usuario.unidades_supervisadas, key=lambda unidad: unidad.nombre)


def puede_supervisar(usuario, unidad):
    return unidad in usuario.unidades_supervisadas


def unidad_supervisada_o_403(usuario, unidad_id):
    """Resuelve qué `Unidad` debe usarse en una vista de supervisión.

    Sin `unidad_id`, usa la unidad propia del usuario si está entre las
    supervisadas (compatibilidad con supervisoras de una sola unidad) o si
    no la primera de `unidades_supervisadas_de`. Con `unidad_id`, exige que
    esté entre las supervisadas.
    """
    unidades = unidades_supervisadas_de(usuario)
    if not unidades:
        abort(403)
    if unidad_id is None:
        return usuario.unidad if usuario.unidad in unidades else unidades[0]
    unidad = db.session.get(Unidad, unidad_id)
    if unidad is None or not puede_supervisar(usuario, unidad):
        abort(403)
    return unidad


def sincronizar_unidades_supervisadas(usuario, unidad_ids):
    """Deja las UnidadSupervisada del usuario exactamente en unidad_ids."""
    deseadas = set(unidad_ids)
    actuales = {unidad.id for unidad in usuario.unidades_supervisadas}

    for unidad_id in deseadas - actuales:
        db.session.add(UnidadSupervisada(usuario_id=usuario.id, unidad_id=unidad_id))

    a_quitar = actuales - deseadas
    if a_quitar:
        UnidadSupervisada.query.filter(
            UnidadSupervisada.usuario_id == usuario.id,
            UnidadSupervisada.unidad_id.in_(a_quitar),
        ).delete(synchronize_session=False)
