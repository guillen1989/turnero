"""Convierte una PropuestaPublicacion en los argumentos de publicar_cambio().

Todo determinista y testeable sin red: la propuesta ya viene parseada por el
cliente de la API (Fase 4); aquí solo se resuelve contra la base de datos.
"""
import re
import unicodedata
from datetime import date

from app.models import FranjaHoraria
from app.routes.publicaciones import _validar_turnos
from app.services.asistente.sinonimos_franja import SINONIMOS_FRANJA


def _normalizar(texto: str) -> str:
    texto = texto.strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto)


_SINONIMOS_NORMALIZADOS = {
    _normalizar(mote): canonico for mote, canonico in SINONIMOS_FRANJA.items()
}


def _resolver_franja_id(nombre_franja, grupo_intercambio_id):
    """Busca `nombre_franja` (o su sinónimo) entre las franjas del grupo dado.

    Devuelve el id si la encuentra, o None si no existe: nunca inventa un id.
    La búsqueda se limita siempre a `grupo_intercambio_id` del usuario autenticado.
    """
    clave = _normalizar(nombre_franja)
    nombre_canonico = _SINONIMOS_NORMALIZADOS.get(clave, nombre_franja)
    clave_canonica = _normalizar(nombre_canonico)

    franjas = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=grupo_intercambio_id
    ).all()
    for franja in franjas:
        if _normalizar(franja.nombre) == clave_canonica:
            return franja.id
    return None


def _resolver_turnos(turnos, grupo_intercambio_id, hoy, permitir_cualquier_franja, problemas):
    resueltos = []
    for turno in turnos:
        fecha = date.fromisoformat(turno.fecha)
        if fecha < hoy:
            problemas.append(f"Fecha en el pasado: {turno.fecha}")
            continue

        if turno.franja is None and permitir_cualquier_franja:
            franja_id = None
        else:
            franja_id = _resolver_franja_id(turno.franja, grupo_intercambio_id)
            if franja_id is None:
                problemas.append(f"Turno desconocido: '{turno.franja}' el {turno.fecha}")
                continue

        if (fecha, franja_id) in resueltos:
            problemas.append(f"Turno duplicado: {turno.fecha} {turno.franja}")
            continue
        resueltos.append((fecha, franja_id))
    return resueltos


def resolver_propuesta(propuesta, usuario, hoy):
    """Resuelve una PropuestaPublicacion contra la BD.

    Devuelve (cedidos, aceptados, problemas). Si `problemas` no está vacío,
    `cedidos`/`aceptados` vienen vacíos: el llamador debe mandar al usuario al
    formulario normal, nunca publicar con datos parcialmente resueltos.
    """
    if propuesta.campos_faltantes:
        return [], [], list(propuesta.campos_faltantes)

    grupo_id = usuario.grupo_intercambio.id
    problemas = []

    cedidos = _resolver_turnos(
        propuesta.cedidos, grupo_id, hoy, permitir_cualquier_franja=False, problemas=problemas
    )
    aceptados = _resolver_turnos(
        propuesta.aceptados, grupo_id, hoy, permitir_cualquier_franja=True, problemas=problemas
    )

    if problemas:
        return [], [], problemas

    error = _validar_turnos(propuesta.tipo, cedidos, aceptados, hoy)
    if error:
        return [], [], [error]

    return cedidos, aceptados, []
