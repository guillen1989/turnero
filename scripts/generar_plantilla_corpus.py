"""Genera la plantilla JSONL de anotación a partir del corpus anonimizado (Fase 0.1,
docs/crear_parser.md).

Agrupa cada mensaje (cabecera + líneas de continuación) del export anonimizado en una
entrada `{"id", "texto", "esperado": null}` lista para que un humano rellene el campo
"esperado" a mano y reparta las entradas entre dev.jsonl y test.jsonl. NO decide qué
publicación representa cada mensaje: esa anotación es manual (ver Fase 0.1 del plan).

Uso: python scripts/generar_plantilla_corpus.py <anonimizado.txt> <plantilla.jsonl>
"""
import argparse
import importlib.util
import json
import pathlib
import re

_RUTA_ANONIMIZADOR = pathlib.Path(__file__).resolve().parent / "anonimizar_corpus.py"
_spec = importlib.util.spec_from_file_location("anonimizar_corpus", _RUTA_ANONIMIZADOR)
anonimizar_corpus = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(anonimizar_corpus)

PATRON_LINEA = anonimizar_corpus.PATRON_LINEA

_PATRON_FECHA_CABECERA = re.compile(r"^(?P<dia>\d{1,2})/(?P<mes>\d{1,2})(?:/(?P<anio>\d{2,4}))?")


def _fecha_iso(fecha_cruda: str, anio_por_defecto: int) -> str:
    """Convierte la fecha cruda de una cabecera de WhatsApp ("dd/mm[/aa]") a ISO.

    La mayoría de cabeceras del corpus no llevan año (export de pocos meses);
    se usa `anio_por_defecto` en ese caso. Si la cabecera trae año de 2 dígitos,
    se asume 2000 + aa.
    """
    m = _PATRON_FECHA_CABECERA.match(fecha_cruda)
    dia = int(m.group("dia"))
    mes = int(m.group("mes"))
    anio_cruda = m.group("anio")
    if anio_cruda is None:
        anio = anio_por_defecto
    elif len(anio_cruda) == 2:
        anio = 2000 + int(anio_cruda)
    else:
        anio = int(anio_cruda)
    return f"{anio:04d}-{mes:02d}-{dia:02d}"


def extraer_mensajes(lineas: list[str], anio_por_defecto: int = 2026) -> list[dict]:
    """Agrupa cabecera + continuaciones en mensajes y les asigna id correlativo w001, w002...

    Cada mensaje incluye `fecha_mensaje` (ISO) tomada de la cabecera que lo abre,
    necesaria para que el asistente resuelva fechas relativas ("la semana que viene")
    contra el "hoy" real de cuando se escribió el mensaje, no contra la fecha de la
    sesión de evaluación.
    """
    textos: list[str] = []
    fechas: list[str] = []
    actual: list[str] | None = None
    for linea in lineas:
        sin_salto = linea.rstrip("\n")
        m = PATRON_LINEA.match(sin_salto)
        if m:
            if actual is not None:
                textos.append("\n".join(actual))
            actual = [m.group("resto")]
            fechas.append(_fecha_iso(m.group("fecha"), anio_por_defecto))
        elif actual is not None:
            actual.append(sin_salto)
    if actual is not None:
        textos.append("\n".join(actual))

    mensajes = []
    for texto, fecha in zip(textos, fechas):
        if not texto.strip():
            continue
        mensajes.append(
            {"id": f"w{len(mensajes) + 1:03d}", "texto": texto, "fecha_mensaje": fecha}
        )
    return mensajes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origen", help="Corpus anonimizado (mensajes_anonimizados.txt)")
    parser.add_argument("destino", help="Ruta de salida de la plantilla JSONL")
    args = parser.parse_args()

    with open(args.origen, encoding="utf-8") as f:
        lineas = f.readlines()

    mensajes = extraer_mensajes(lineas)

    with open(args.destino, "w", encoding="utf-8") as f:
        for mensaje in mensajes:
            f.write(json.dumps({**mensaje, "esperado": None}, ensure_ascii=False) + "\n")

    print(f"{len(mensajes)} mensajes -> {args.destino}")
    print('Rellena "esperado" a mano y reparte las entradas entre dev.jsonl (~60) y test.jsonl.')


if __name__ == "__main__":
    main()
