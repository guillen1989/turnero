from werkzeug.exceptions import Forbidden

from app.extensions import db
from app.models import BusquedaGuardada, Notificacion, Usuario
from app.models.unidad import Unidad
from app.push.sender import enviar_push_condicional


_MESES = [
    None, "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

_TIPO_LABELS = {
    "cambio": "Cambios",
    "regalo": "Regalos",
    "peticion": "Peticiones",
    "junte": "Juntes",
    "cambio_dia": "Cambios de día",
}


def publicacion_cumple_filtros(pub, filtros):
    """Pure function: True if pub matches all criteria in filtros dict."""
    tipo = filtros.get("tipo", "")
    if tipo and pub.tipo != tipo:
        return False

    mes = filtros.get("mes")
    dia = filtros.get("dia")
    if mes or dia:
        fechas = (
            [tc.fecha for tc in pub.turnos_cedidos]
            + [ta.fecha for ta in pub.turnos_aceptados]
        )

        def _fecha_ok(fecha):
            return (not mes or fecha.month == mes) and (not dia or fecha.day == dia)

        if not any(_fecha_ok(f) for f in fechas):
            return False

    franja_id = filtros.get("franja_id")
    if franja_id:
        franja_ids = {tc.franja_horaria_id for tc in pub.turnos_cedidos} | {
            ta.franja_horaria_id for ta in pub.turnos_aceptados if not ta.cualquier_franja
        }
        if franja_id not in franja_ids:
            return False

    nombre = filtros.get("nombre", "").strip().lower()
    if nombre and nombre not in pub.usuario.nombre.lower():
        return False

    return True


def _nombre_de_filtros(filtros):
    parts = []
    if filtros.get("tipo"):
        parts.append(_TIPO_LABELS.get(filtros["tipo"], filtros["tipo"].capitalize()))
    if filtros.get("mes"):
        parts.append(_MESES[filtros["mes"]])
    if filtros.get("dia"):
        parts.append(f"día {filtros['dia']}")
    if filtros.get("franja_nombre"):
        parts.append(filtros["franja_nombre"])
    elif filtros.get("franja_id"):
        parts.append(f"Franja {filtros['franja_id']}")
    if filtros.get("nombre"):
        parts.append(filtros["nombre"])
    return " · ".join(parts) if parts else "Todos los cambios"


def guardar_busqueda(usuario_id, filtros):
    """Saves a search with auto-generated name from filters."""
    busqueda = BusquedaGuardada(
        usuario_id=usuario_id,
        nombre=_nombre_de_filtros(filtros),
        filtros=filtros,
    )
    db.session.add(busqueda)
    db.session.commit()
    return busqueda


def eliminar_busqueda(busqueda_id, usuario_id):
    """Deletes a saved search. Raises Forbidden if caller is not the owner."""
    busqueda = db.session.get(BusquedaGuardada, busqueda_id)
    if busqueda is None:
        from flask import abort
        abort(404)
    if busqueda.usuario_id != usuario_id:
        raise Forbidden()
    db.session.delete(busqueda)
    db.session.commit()


def notificar_busquedas_guardadas(pub):
    """Creates panel notifications and sends push for saved searches matching a new pub."""
    grupo_id = pub.usuario.unidad.grupo_intercambio_id
    categoria_id = pub.usuario.categoria_id

    candidatas = (
        BusquedaGuardada.query
        .join(Usuario, BusquedaGuardada.usuario_id == Usuario.id)
        .join(Unidad, Usuario.unidad_id == Unidad.id)
        .filter(
            Unidad.grupo_intercambio_id == grupo_id,
            Usuario.categoria_id == categoria_id,
            BusquedaGuardada.usuario_id != pub.usuario_id,
        )
        .all()
    )

    for busqueda in candidatas:
        if publicacion_cumple_filtros(pub, busqueda.filtros):
            db.session.add(Notificacion(
                usuario_id=busqueda.usuario_id,
                publicacion_id=pub.id,
                busqueda_guardada_id=busqueda.id,
                tipo="alerta_busqueda_guardada",
            ))
            usuario = db.session.get(Usuario, busqueda.usuario_id)
            if usuario:
                enviar_push_condicional(usuario, "busqueda_guardada")

    db.session.commit()
