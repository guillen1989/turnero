"""
Agregación mensual para el calendario visual de ofertas/peticiones.

Módulo puro salvo por las consultas ORM de solo lectura: no crea, modifica
ni borra nada. Agrupa los turnos abiertos de publicaciones activas y
visibles para un usuario (misma categoría + mismo grupo de intercambio),
por fecha y franja, para pintarlos en un grid mensual.
"""
import calendar
from datetime import date

from app.models import PublicacionCambio, TurnoAceptado, TurnoCedido, Unidad, Usuario

CUALQUIER_FRANJA = "cualquiera"

_TIPOS_POR_MODO = {
    "ofertas": ("cambio", "regalo", "cambio_dia"),
    "peticiones": ("cambio", "peticion", "cambio_dia"),
}


def _candidatas(usuario, tipos):
    grupo_id = usuario.unidad.grupo_intercambio_id
    return (
        PublicacionCambio.query
        .join(Usuario, PublicacionCambio.usuario_id == Usuario.id)
        .join(Unidad, Usuario.unidad_id == Unidad.id)
        .filter(
            PublicacionCambio.usuario_id != usuario.id,
            PublicacionCambio.tipo.in_(tipos),
            PublicacionCambio.estado.in_(("abierta", "parcialmente_resuelta")),
            PublicacionCambio.es_sintetica.is_(False),
            Usuario.categoria_id == usuario.categoria_id,
            Unidad.grupo_intercambio_id == grupo_id,
        )
        .all()
    )


def construir_calendario_mes(usuario, anio, mes, modo):
    """
    Devuelve {fecha: {clave_franja: [publicacion_id, ...]}} para el mes dado.

    modo: 'ofertas' (turnos que otros trabajarían) o 'peticiones' (turnos que
    otros quieren librar). clave_franja es el id de FranjaHoraria, o la
    constante CUALQUIER_FRANJA si el turno aceptado admite cualquier franja
    ese día.
    """
    if modo not in _TIPOS_POR_MODO:
        raise ValueError(f"modo debe ser uno de {tuple(_TIPOS_POR_MODO)}, recibido: {modo!r}")

    primer_dia = date(anio, mes, 1)
    ultimo_dia = date(anio, mes, calendar.monthrange(anio, mes)[1])

    candidatas = _candidatas(usuario, _TIPOS_POR_MODO[modo])
    pub_ids = [p.id for p in candidatas]
    if not pub_ids:
        return {}

    if modo == "ofertas":
        turnos = (
            TurnoAceptado.query
            .filter(
                TurnoAceptado.publicacion_id.in_(pub_ids),
                TurnoAceptado.estado == "abierto",
                TurnoAceptado.fecha.between(primer_dia, ultimo_dia),
            )
            .all()
        )
    else:
        turnos = (
            TurnoCedido.query
            .filter(
                TurnoCedido.publicacion_id.in_(pub_ids),
                TurnoCedido.estado == "abierto",
                TurnoCedido.fecha.between(primer_dia, ultimo_dia),
            )
            .all()
        )

    resultado = {}
    for turno in turnos:
        cualquier = getattr(turno, "cualquier_franja", False)
        clave = CUALQUIER_FRANJA if cualquier else turno.franja_horaria_id
        resultado.setdefault(turno.fecha, {}).setdefault(clave, []).append(turno.publicacion_id)

    return resultado
