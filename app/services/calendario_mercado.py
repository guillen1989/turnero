"""
Agregación mensual para el calendario visual de ofertas/peticiones.

Módulo puro salvo por las consultas ORM de solo lectura: no crea, modifica
ni borra nada. Agrupa los turnos abiertos de publicaciones activas y
visibles para un usuario (misma categoría + mismo grupo de intercambio),
por fecha y franja, para pintarlos en un grid mensual.
"""
import calendar
from datetime import date

from sqlalchemy.orm import joinedload

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

# Por encima de este número de tipos distintos, las bandas de color serían
# demasiado finas para distinguirse en una celda de ~40px; se usa el
# tratamiento neutro (color plano + nº de tipos) en su lugar.
_MAX_FRANJAS_EN_BANDAS = 4


def _info_clave(clave, franjas_por_id):
    """(color, color_texto, nombre) para una clave de franja o CUALQUIER_FRANJA."""
    if clave == CUALQUIER_FRANJA:
        return _COLOR_CUALQUIERA, _COLOR_TEXTO_CUALQUIERA, "Cualquiera"
    franja = franjas_por_id.get(clave)
    if franja is None:
        return "#3B82F6", "#ffffff", "?"
    return franja.color or "#3B82F6", franja.color_texto, franja.nombre


def _ordenar_claves(claves, franjas):
    """Ordena claves cronológicamente por hora_inicio de la franja
    (CUALQUIER_FRANJA y franjas desconocidas van al final)."""
    orden_ids = [f.id for f in franjas]

    def _posicion(clave):
        if clave == CUALQUIER_FRANJA:
            return len(orden_ids)
        try:
            return orden_ids.index(clave)
        except ValueError:
            return len(orden_ids)

    return sorted(claves, key=_posicion)


def _gradiente_bandas(colores):
    """Linear-gradient con cortes duros: una banda igual de ancha por color,
    en el orden recibido, sin transición entre bandas."""
    n = len(colores)
    ancho = 100 / n
    paradas = []
    for i, color in enumerate(colores):
        inicio = i * ancho
        fin = (i + 1) * ancho
        paradas.append(f"{color} {inicio:.2f}%")
        paradas.append(f"{color} {fin:.2f}%")
    return "linear-gradient(to right, " + ", ".join(paradas) + ")"


def preparar_celdas_mes(dias, calendario_mes, franjas):
    """
    Convierte el resultado de construir_calendario_mes en datos listos para
    pintar cada celda del grid: {fecha: {mod, estilo, etiqueta, tooltip}}.

    - Sin franjas ese día: celda vacía.
    - Una franja: color sólido de esa franja, etiqueta = su inicial.
    - Entre 2 y _MAX_FRANJAS_EN_BANDAS franjas distintas: la celda se divide
      en bandas de igual ancho, una por franja, coloreada con el color de
      esa franja y ordenadas cronológicamente (hora_inicio). Sin etiqueta:
      el propio patrón de color ya es la información.
    - Más de _MAX_FRANJAS_EN_BANDAS: demasiadas bandas serían ilegibles;
      se usa el tratamiento neutro anterior (color plano + nº de tipos),
      con el tooltip listando los nombres separados por coma.
    """
    franjas_por_id = {f.id: f for f in franjas}
    celdas = {}
    for dia in dias:
        claves = _ordenar_claves(list(calendario_mes.get(dia, {}).keys()), franjas)
        if not claves:
            celdas[dia] = {"mod": "cal-celda--vacio", "estilo": "", "etiqueta": "", "tooltip": ""}
            continue

        infos = [_info_clave(c, franjas_por_id) for c in claves]
        nombres = [info[2] for info in infos]

        if len(infos) == 1:
            color, color_texto, nombre = infos[0]
            etiqueta = "?" if claves[0] == CUALQUIER_FRANJA else nombre[:1]
            celdas[dia] = {
                "mod": "cal-celda--turno",
                "estilo": f"background:{color}; color:{color_texto};",
                "etiqueta": etiqueta,
                "tooltip": nombre,
            }
        elif len(infos) <= _MAX_FRANJAS_EN_BANDAS:
            colores = [info[0] for info in infos]
            celdas[dia] = {
                "mod": "cal-celda--multi",
                "estilo": _gradiente_bandas(colores),
                "etiqueta": "",
                "tooltip": ", ".join(nombres),
            }
        else:
            celdas[dia] = {
                "mod": "cal-celda--multi",
                "estilo": f"background:{_COLOR_MULTI}; color:{_COLOR_TEXTO_MULTI};",
                "etiqueta": str(len(infos)),
                "tooltip": ", ".join(nombres),
            }

    return celdas


def resumen_publicaciones(pub_ids):
    """Datos mínimos de cada publicación (autor + tipo) para el drill-down."""
    if not pub_ids:
        return []
    pubs = (
        PublicacionCambio.query
        .filter(PublicacionCambio.id.in_(pub_ids))
        .options(joinedload(PublicacionCambio.usuario))
        .all()
    )
    return [{"id": p.id, "usuario_nombre": p.usuario.nombre, "tipo": p.tipo} for p in pubs]
