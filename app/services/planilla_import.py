"""
Parser puro de planillas exportadas en el formato ILOG (texto separado por
tabuladores, una fila de metadatos + una fila por trabajador con un código de
turno por día). No toca la base de datos ni conoce a `Usuario`: solo traduce
el archivo a estructuras de datos. Casar cada `nombre_planilla` con un
`Usuario` real y traducir cada código de turno a una `FranjaHoraria` son
responsabilidad de otro módulo.
"""
from dataclasses import dataclass, field
from datetime import date


@dataclass
class TrabajadorImportado:
    nombre_planilla: str
    numero_empleado: str
    turnos: dict[date, str] = field(default_factory=dict)


@dataclass
class PlanillaImportada:
    unidad_nombre: str
    anyo: int
    mes: int
    trabajadores: list[TrabajadorImportado]


def _celdas(contenido: str) -> list[list[str]]:
    return [linea.split("\t") for linea in contenido.splitlines()]


def _valor_tras_etiqueta(filas: list[list[str]], etiqueta: str) -> str | None:
    for fila in filas:
        if len(fila) >= 3 and fila[1].strip() == etiqueta:
            return fila[2].strip()
    return None


def _extraer_anyo_mes(filas: list[list[str]]) -> tuple[int, int]:
    fecha_inicial = _valor_tras_etiqueta(filas, "Fecha inicial:")
    if fecha_inicial is None:
        raise ValueError("No se encontró la fila 'Fecha inicial:' en la planilla")
    dia, mes, anyo = fecha_inicial.split("/")
    return int(anyo), int(mes)


def _extraer_unidad(filas: list[list[str]]) -> str:
    unidad = _valor_tras_etiqueta(filas, "Unidad:")
    if unidad is None:
        raise ValueError("No se encontró la fila 'Unidad:' en la planilla")
    return unidad


def _columna_por_dia(filas: list[list[str]]) -> dict[int, int]:
    for fila in filas:
        if len(fila) >= 2 and fila[1].strip() == "Dias":
            return {
                int(celda.strip()): indice
                for indice, celda in enumerate(fila)
                if celda.strip().isdigit()
            }
    raise ValueError("No se encontró la fila 'Dias' en la planilla")


def _nombre_y_numero(fila: list[str]) -> tuple[str, str] | tuple[None, None]:
    if len(fila) < 3:
        return None, None
    nombre = fila[1].strip()
    numero = fila[2].strip()
    if "," in nombre and numero.isdigit():
        return nombre, numero
    return None, None


def parsear_planilla_ilog(contenido: str) -> PlanillaImportada:
    filas = _celdas(contenido)

    anyo, mes = _extraer_anyo_mes(filas)
    unidad_nombre = _extraer_unidad(filas)
    columna_por_dia = _columna_por_dia(filas)

    trabajadores = []
    for fila in filas:
        nombre, numero = _nombre_y_numero(fila)
        if nombre is None:
            continue

        turnos = {}
        for dia, columna in columna_por_dia.items():
            if columna >= len(fila):
                continue
            codigo = fila[columna].strip()
            if codigo:
                turnos[date(anyo, mes, dia)] = codigo

        trabajadores.append(TrabajadorImportado(nombre, numero, turnos))

    return PlanillaImportada(
        unidad_nombre=unidad_nombre, anyo=anyo, mes=mes, trabajadores=trabajadores
    )
