"""
Agregación mensual para el calendario visual de ofertas/peticiones.

Módulo puro salvo por las consultas ORM de solo lectura: no crea, modifica
ni borra nada. Agrupa los turnos abiertos de publicaciones activas y
visibles para un usuario (misma categoría + mismo grupo de intercambio),
por fecha y franja, para pintarlos en un grid mensual.
"""
import calendar
from datetime import date, timedelta

from sqlalchemy.orm import joinedload

from app.models import PublicacionCambio, TurnoAceptado, TurnoCedido, Unidad, Usuario
from app.services.junte_semanal import DIAS_CORTOS, calcular_distribucion, resumen_textual

CUALQUIER_FRANJA = "cualquiera"

_TIPOS_POR_MODO = {
    "ofertas": ("cambio", "regalo", "cambio_dia"),
    "peticiones": ("cambio", "peticion", "cambio_dia"),
}

_TIPOS_JUNTE = ("junte",)


def _candidatas(usuario, tipos):
    """Publicaciones candidatas, visibles y activas para el usuario.

    Incluye las sintéticas (oportunidades a 3 bandas): tienen tipo 'cambio' y
    son justo el tipo de match más difícil de descubrir, así que también se
    muestran en el calendario (etiquetadas aparte, ver resumen_publicaciones).
    """
    grupo_id = usuario.unidad.grupo_intercambio_id
    return (
        PublicacionCambio.query
        .join(Usuario, PublicacionCambio.usuario_id == Usuario.id)
        .join(Unidad, Usuario.unidad_id == Unidad.id)
        .filter(
            PublicacionCambio.usuario_id != usuario.id,
            PublicacionCambio.tipo.in_(tipos),
            PublicacionCambio.estado.in_(("abierta", "parcialmente_resuelta")),
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

    Los juntes de noches no encajan en este modelo día a día (cedido/aceptado
    no son direccionales: son las dos caras de la misma permuta semanal), así
    que tienen su propio agregado por semana — ver construir_semanas_juntes.
    """
    if modo not in _TIPOS_POR_MODO:
        raise ValueError(f"modo debe ser uno de {tuple(_TIPOS_POR_MODO)}, recibido: {modo!r}")

    primer_dia = date(anio, mes, 1)
    ultimo_dia = date(anio, mes, calendar.monthrange(anio, mes)[1])

    candidatas = _candidatas(usuario, _TIPOS_POR_MODO[modo])
    if not candidatas:
        return {}

    normales_ids = [p.id for p in candidatas if not p.es_sintetica]
    sinteticas_ids = [p.id for p in candidatas if p.es_sintetica]

    # Para publicaciones normales, 'ofertas' = turno_aceptado (días que otros
    # trabajarían) y 'peticiones' = turno_cedido (días que otros quieren
    # librar). Para las sintéticas (oportunidades a 3) el sentido está
    # invertido: crear_pub_sintetica() copia como turno_cedido el ACEPTADO de
    # pub_a (una oferta real) y como turno_aceptado el CEDIDO de pub_b (una
    # petición real) — así lo necesita el matching de la cadena a 3. El
    # calendario debe deshacer esa inversión para mostrarlas en el modo que
    # corresponde a su significado real.
    if modo == "ofertas":
        pares = ((TurnoAceptado, normales_ids), (TurnoCedido, sinteticas_ids))
    else:
        pares = ((TurnoCedido, normales_ids), (TurnoAceptado, sinteticas_ids))

    turnos = []
    for modelo, pub_ids in pares:
        if not pub_ids:
            continue
        turnos += (
            modelo.query
            .filter(
                modelo.publicacion_id.in_(pub_ids),
                modelo.estado == "abierto",
                modelo.fecha.between(primer_dia, ultimo_dia),
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


def _bandas(claves, infos):
    """Una banda por franja: color sólido + su color de texto legible (según
    el brillo de ese color, igual que en el caso de una sola franja) + su
    inicial (o '?' para CUALQUIER_FRANJA), en el mismo orden que claves/infos."""
    bandas = []
    for clave, (color, color_texto, nombre) in zip(claves, infos):
        letra = "?" if clave == CUALQUIER_FRANJA else nombre[:1]
        bandas.append({"color": color, "color_texto": color_texto, "letra": letra})
    return bandas


def preparar_celdas_mes(dias, calendario_mes, franjas):
    """
    Convierte el resultado de construir_calendario_mes en datos listos para
    pintar cada celda del grid: {fecha: {mod, estilo, etiqueta, tooltip, bandas}}.

    - Sin franjas ese día: celda vacía.
    - Una franja: color sólido de esa franja, etiqueta = su inicial.
    - Entre 2 y _MAX_FRANJAS_EN_BANDAS franjas distintas: `bandas` trae una
      banda por franja (color + inicial), ordenadas cronológicamente
      (hora_inicio), para que la plantilla las pinte como sub-elementos
      independientes dentro de la celda (más fiable que superponer texto
      sobre un gradiente CSS). `estilo`/`etiqueta` van vacíos en este caso.
    - Más de _MAX_FRANJAS_EN_BANDAS: demasiadas bandas serían ilegibles;
      se usa el tratamiento neutro anterior (color plano + nº de tipos),
      con el tooltip listando los nombres separados por coma. `bandas` vacío.
    """
    franjas_por_id = {f.id: f for f in franjas}
    celdas = {}
    for dia in dias:
        claves = _ordenar_claves(list(calendario_mes.get(dia, {}).keys()), franjas)
        if not claves:
            celdas[dia] = {"mod": "cal-celda--vacio", "estilo": "", "etiqueta": "", "tooltip": "", "bandas": []}
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
                "bandas": [],
            }
        elif len(infos) <= _MAX_FRANJAS_EN_BANDAS:
            celdas[dia] = {
                "mod": "cal-celda--multi",
                "estilo": "",
                "etiqueta": "",
                "tooltip": ", ".join(nombres),
                "bandas": _bandas(claves, infos),
            }
        else:
            celdas[dia] = {
                "mod": "cal-celda--multi",
                "estilo": f"background:{_COLOR_MULTI}; color:{_COLOR_TEXTO_MULTI};",
                "etiqueta": str(len(infos)),
                "tooltip": ", ".join(nombres),
                "bandas": [],
            }

    return celdas


def resumen_publicaciones(pub_ids):
    """Datos mínimos de cada publicación (autor + tipo + si es sintética) para
    el drill-down. es_sintetica permite etiquetarla como "Oportunidad a 3"
    en vez de con la etiqueta genérica de su tipo."""
    if not pub_ids:
        return []
    pubs = (
        PublicacionCambio.query
        .filter(PublicacionCambio.id.in_(pub_ids))
        .options(joinedload(PublicacionCambio.usuario))
        .all()
    )
    return [
        {"id": p.id, "usuario_nombre": p.usuario.nombre, "tipo": p.tipo, "es_sintetica": p.es_sintetica}
        for p in pubs
    ]


def construir_semanas_juntes(usuario, anio, mes):
    """
    Devuelve la lista de semanas naturales (lunes a domingo) que solapan el
    mes dado, en orden cronológico: [{lunes, domingo, ofertas}, ...].

    Un junte de noches es un patrón semanal completo (qué noches se
    trabajarían/librarían), no una noche suelta, así que aquí se agrupa por
    semana en vez de por día como en construir_calendario_mes. `ofertas` es
    la lista de publicaciones junte visibles para el usuario cuya semana
    natural es esa: [{pub_id, usuario_nombre, trabaja, libra}], con
    trabaja/libra como frozenset de weekday (ver junte_semanal.calcular_distribucion).
    """
    primer_dia = date(anio, mes, 1)
    ultimo_dia = date(anio, mes, calendar.monthrange(anio, mes)[1])
    primer_lunes = primer_dia - timedelta(days=primer_dia.weekday())

    ofertas_por_lunes = {}
    for pub in _candidatas(usuario, _TIPOS_JUNTE):
        lunes, trabaja, libra, _num_noches = calcular_distribucion(pub)
        if lunes is None:
            continue
        ofertas_por_lunes.setdefault(lunes, []).append({
            "pub_id": pub.id,
            "usuario_nombre": pub.usuario.nombre,
            "trabaja": trabaja,
            "libra": libra,
        })
    for ofertas in ofertas_por_lunes.values():
        ofertas.sort(key=lambda o: o["pub_id"])

    semanas = []
    lunes = primer_lunes
    while lunes <= ultimo_dia:
        semanas.append({
            "lunes": lunes,
            "domingo": lunes + timedelta(days=6),
            "ofertas": ofertas_por_lunes.get(lunes, []),
        })
        lunes += timedelta(days=7)
    return semanas


def preparar_semanas_juntes(semanas, mes):
    """
    Da forma a construir_semanas_juntes() para la plantilla: marca las
    semanas parciales (con algún día fuera del mes mostrado) y, por cada
    oferta, genera la tira de 7 días (trabaja/libra, lunes a domingo) y el
    resumen en texto.
    """
    resultado = []
    for semana in semanas:
        lunes, domingo = semana["lunes"], semana["domingo"]
        ofertas = []
        for oferta in semana["ofertas"]:
            trabaja_str, libra_str = resumen_textual(oferta["trabaja"], oferta["libra"])
            dias = [
                {"letra": DIAS_CORTOS[wd], "estado": "trabaja" if wd in oferta["trabaja"] else "libra"}
                for wd in range(7)
            ]
            ofertas.append({
                "pub_id": oferta["pub_id"],
                "usuario_nombre": oferta["usuario_nombre"],
                "trabaja_str": trabaja_str,
                "libra_str": libra_str,
                "dias": dias,
            })
        resultado.append({
            "lunes": lunes,
            "domingo": domingo,
            "es_parcial": lunes.month != mes or domingo.month != mes,
            "ofertas": ofertas,
        })
    return resultado
