"""Añade `fecha_mensaje` a las entradas ya anotadas de dev.jsonl/test.jsonl (Fase 5,
docs/crear_parser.md).

`generar_plantilla_corpus.py` descartaba la fecha de cabecera al construir `texto`,
pero el cliente del asistente necesita el "hoy" real de cada mensaje para resolver
fechas relativas ("la semana que viene"). Este script es un backfill aditivo: NO
toca `id`, `texto` ni `esperado` de las entradas ya anotadas a mano, solo añade
`fecha_mensaje` buscándola por `id` en el corpus anonimizado original.

Uso: python scripts/anadir_fecha_mensaje.py <anonimizado.txt> <destino.jsonl> [destino.jsonl ...]
"""
import argparse
import importlib.util
import json
import pathlib

_RUTA_PLANTILLA = pathlib.Path(__file__).resolve().parent / "generar_plantilla_corpus.py"
_spec = importlib.util.spec_from_file_location("generar_plantilla_corpus", _RUTA_PLANTILLA)
generar_plantilla_corpus = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generar_plantilla_corpus)

extraer_mensajes = generar_plantilla_corpus.extraer_mensajes


def fusionar_fecha_mensaje(mensajes: list[dict], entradas: list[dict]) -> list[dict]:
    """Añade `fecha_mensaje` a cada entrada buscando su `id` en `mensajes`.

    Preserva el resto de campos (y su orden) tal cual; inserta `fecha_mensaje`
    justo después de `texto` por legibilidad.
    """
    fecha_por_id = {m["id"]: m["fecha_mensaje"] for m in mensajes}
    resultado = []
    for entrada in entradas:
        if entrada["id"] not in fecha_por_id:
            raise ValueError(f"No se encontró fecha_mensaje para el id '{entrada['id']}'")
        nueva = {}
        for clave, valor in entrada.items():
            nueva[clave] = valor
            if clave == "texto":
                nueva["fecha_mensaje"] = fecha_por_id[entrada["id"]]
        resultado.append(nueva)
    return resultado


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("anonimizado", help="Corpus anonimizado (mensajes_anonimizados.txt)")
    parser.add_argument("jsonl", nargs="+", help="Archivos jsonl a actualizar (dev.jsonl, test.jsonl)")
    args = parser.parse_args()

    with open(args.anonimizado, encoding="utf-8") as f:
        mensajes = extraer_mensajes(f.readlines())

    for ruta in args.jsonl:
        with open(ruta, encoding="utf-8") as f:
            entradas = [json.loads(linea) for linea in f if linea.strip()]

        actualizadas = fusionar_fecha_mensaje(mensajes, entradas)

        with open(ruta, "w", encoding="utf-8") as f:
            for entrada in actualizadas:
                f.write(json.dumps(entrada, ensure_ascii=False) + "\n")

        print(f"{len(actualizadas)} entradas actualizadas -> {ruta}")


if __name__ == "__main__":
    main()
