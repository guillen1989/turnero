from flask import abort, session

from app.extensions import db
from app.models.unidad import Unidad
from app.models.usuario_unidad import UsuarioUnidad


def unidades_de(usuario):
    """Todas las unidades del usuario: la principal más las membresías de
    `usuario_unidad`, ordenadas por nombre y sin repetidos."""
    unidades = {usuario.unidad}
    unidades.update(usuario.unidades)
    return sorted(unidades, key=lambda unidad: unidad.nombre)


def pertenece_a(usuario, unidad):
    return unidad.id == usuario.unidad_id or unidad in usuario.unidades


def categoria_en_unidad(usuario, unidad):
    """Categoría profesional del usuario en esa unidad concreta: la global
    (`usuario.categoria_id`) en la unidad principal, la de su membresía en
    cualquier otra."""
    if unidad.id == usuario.unidad_id:
        return usuario.categoria
    membresia = UsuarioUnidad.query.filter_by(
        usuario_id=usuario.id, unidad_id=unidad.id
    ).first()
    return membresia.categoria if membresia else None


def unidad_activa_o_403(usuario, unidad_id, session_key="unidad_activa_id"):
    """Resuelve qué `Unidad` debe usar un usuario normal en una vista.

    Precedencia: query param `unidad_id` > unidad activa guardada en sesión
    (`session_key`) > unidad principal (`usuario.unidad`). Con `unidad_id`
    informado, exige que el usuario pertenezca a esa unidad o aborta 403.

    Cuando `unidad_id` viene explícitamente informado (query param), lo
    persiste en sesión para que las navegaciones posteriores mantengan el
    contexto sin necesitar el param en cada URL.
    """
    explicitamente_pedida = unidad_id is not None
    if not explicitamente_pedida:
        unidad_id = session.get(session_key)
    if unidad_id is None:
        return usuario.unidad
    unidad = db.session.get(Unidad, unidad_id)
    if unidad is None or not pertenece_a(usuario, unidad):
        abort(403)
    if explicitamente_pedida:
        session[session_key] = unidad_id
    return unidad


def sincronizar_unidades(usuario, membresias):
    """Deja las membresías `usuario_unidad` del usuario exactamente en
    `membresias` ({unidad_id: categoria_id}), creando las que falten y
    actualizando la categoría de las existentes. La unidad principal nunca
    se elimina; su categoría siempre es la de `usuario.categoria_id`."""
    assert usuario.unidad_id in membresias, "la unidad principal no se puede eliminar"

    actuales = {m.unidad_id: m for m in usuario.membresias_unidad}

    if actuales.get(usuario.unidad_id) is None:
        membresia_principal = UsuarioUnidad(
            usuario_id=usuario.id,
            unidad_id=usuario.unidad_id,
            categoria_id=usuario.categoria_id,
        )
        db.session.add(membresia_principal)
        actuales[usuario.unidad_id] = membresia_principal

    usuario.categoria_id = membresias[usuario.unidad_id]

    for unidad_id, categoria_id in membresias.items():
        membresia = actuales.get(unidad_id)
        if membresia is None:
            db.session.add(UsuarioUnidad(
                usuario_id=usuario.id,
                unidad_id=unidad_id,
                categoria_id=categoria_id,
            ))
        elif membresia.categoria_id != categoria_id:
            membresia.categoria_id = categoria_id

    a_quitar = set(actuales) - set(membresias)
    if a_quitar:
        UsuarioUnidad.query.filter(
            UsuarioUnidad.usuario_id == usuario.id,
            UsuarioUnidad.unidad_id.in_(a_quitar),
        ).delete(synchronize_session=False)
