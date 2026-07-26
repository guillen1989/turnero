from app.extensions import db
from app.models.unidad_supervisada import UnidadSupervisada


def unidades_supervisadas_de(usuario):
    return sorted(usuario.unidades_supervisadas, key=lambda unidad: unidad.nombre)


def puede_supervisar(usuario, unidad):
    return unidad in usuario.unidades_supervisadas


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
