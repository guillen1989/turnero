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


_COLOR_CUALQUIERA = "#9333ea"
_COLOR_TEXTO_CUALQUIERA = "#ffffff"
_COLOR_MULTI = "#dbeafe"
_COLOR_TEXTO_MULTI = "#1e40af"


def _info_clave(clave, franjas_por_id):
    """(color, color_texto, nombre) para una clave de franja o CUALQUIER_FRANJA."""
    if clave == CUALQUIER_FRANJA:
        return _COLOR_CUALQUIERA, _COLOR_TEXTO_CUALQUIERA, "Cualquiera"
    franja = franjas_por_id.get(clave)
    if franja is None:
        return "#3B82F6", "#ffffff", "?"
    return franja.color or "#3B82F6", franja.color_texto, franja.nombre


def preparar_celdas_mes(dias, calendario_mes, franjas):
    """
    Convierte el resultado de construir_calendario_mes en datos listos para
    pintar cada celda del grid: {fecha: {mod, estilo, etiqueta, tooltip}}.

    - Sin franjas ese día: celda vacía.
    - Una franja: color sólido de esa franja, etiqueta = su inicial.
    - Varias franjas: estilo neutro "multi", etiqueta = nº de franjas,
      tooltip con los nombres separados por coma (no se puede codificar más
      de un color de forma legible en una celda pequeña).
    """
    franjas_por_id = {f.id: f for f in franjas}
    celdas = {}
    for dia in dias:
        claves = list(calendario_mes.get(dia, {}).keys())
        if not claves:
            celdas[dia] = {"mod": "cal-celda--vacio", "estilo": "", "etiqueta": "", "tooltip": ""}
            continue

        infos = [_info_clave(c, franjas_por_id) for c in claves]
        if len(infos) == 1:
            color, color_texto, nombre = infos[0]
            etiqueta = "?" if claves[0] == CUALQUIER_FRANJA else nombre[:1]
            celdas[dia] = {
                "mod": "cal-celda--turno",
                "estilo": f"background:{color}; color:{color_texto};",
                "etiqueta": etiqueta,
                "tooltip": nombre,
            }
        else:
            nombres = [info[2] for info in infos]
            celdas[dia] = {
                "mod": "cal-celda--multi",
                "estilo": f"background:{_COLOR_MULTI}; color:{_COLOR_TEXTO_MULTI};",
                "etiqueta": str(len(infos)),
                "tooltip": ", ".join(nombres),
            }

    return celdas
