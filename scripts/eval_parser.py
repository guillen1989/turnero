"""Evalúa el asistente de parseo contra un corpus anotado (Fase 5, docs/crear_parser.md).

Compara la `PropuestaPublicacion` que devuelve el modelo contra el `esperado`
anotado a mano en dev.jsonl/test.jsonl, y calcula dos métricas:

- **exact match**: el conjunto normalizado de turnos coincide exactamente.
- **error silencioso**: la propuesta no se abstuvo (`campos_faltantes` vacío)
  pero es incorrecta. Es el fallo caro: el usuario confirma sin sospechar.

Uso: python scripts/eval_parser.py <dev.jsonl|test.jsonl>
"""
import argparse
import json
from datetime import date

from app.services.asistente.cliente import extraer_propuesta

_FRANJAS_CORPUS = [
    {"nombre": "Mañana", "hora_inicio": "08:00", "hora_fin": "15:00"},
    {"nombre": "Tarde", "hora_inicio": "15:00", "hora_fin": "22:00"},
    {"nombre": "Noche", "hora_inicio": "22:00", "hora_fin": "08:00"},
]
_TIPOS_VALIDOS = ["cambio", "regalo", "peticion", "junte", "cambio_dia"]


def cargar_corpus(ruta) -> list[dict]:
    """Lee un jsonl del corpus y descarta las entradas sin anotar (`esperado: null`)."""
    entradas = []
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            if not linea.strip():
                continue
            entrada = json.loads(linea)
            if entrada["esperado"] is not None:
                entradas.append(entrada)
    return entradas


def _turnos_a_tuplas(turnos) -> list[tuple]:
    """Normaliza cedidos/aceptados (de TurnoPropuesto o de pares [fecha, franja]) a tuplas."""
    resultado = []
    for turno in turnos:
        if isinstance(turno, (list, tuple)):
            fecha, franja = turno
        else:
            fecha, franja = turno.fecha, turno.franja
        resultado.append((fecha, franja))
    return sorted(resultado)


def comparar_exacto(propuesta, esperado: dict) -> bool:
    if propuesta.tipo != esperado["tipo"]:
        return False
    if _turnos_a_tuplas(propuesta.cedidos) != _turnos_a_tuplas(esperado["cedidos"]):
        return False
    if _turnos_a_tuplas(propuesta.aceptados) != _turnos_a_tuplas(esperado["aceptados"]):
        return False
    return True


def diagnosticar(propuesta, esperado: dict) -> list[str]:
    """Desglosa por qué falla una propuesta. Lista vacía si es exact match."""
    fallos = []
    if propuesta.tipo != esperado["tipo"]:
        fallos.append("tipo")

    for campo, prefijo in (("cedidos", "cedido"), ("aceptados", "aceptado")):
        obtenidos = set(_turnos_a_tuplas(getattr(propuesta, campo)))
        esperados = set(_turnos_a_tuplas(esperado[campo]))
        if obtenidos - esperados:
            fallos.append(f"{prefijo}_de_mas")
        if esperados - obtenidos:
            fallos.append(f"{prefijo}_de_menos")

    return fallos


def es_error_silencioso(propuesta, esperado: dict) -> bool:
    """Propuesta completa (sin campos_faltantes) pero incorrecta: el fallo caro de verdad."""
    if propuesta.campos_faltantes:
        return False
    return not comparar_exacto(propuesta, esperado)


def evaluar_corpus(entradas: list[dict], contexto_base: dict, extraer) -> dict:
    """Corre `extraer(texto, contexto, id_entrada) -> PropuestaPublicacion` sobre `entradas`
    y agrega las métricas. `extraer` es inyectable para poder testear sin red y para
    poder cambiar entre llamada síncrona y resultados ya recogidos de la Batch API.
    """
    total = len(entradas)
    exact_match = 0
    error_silencioso = 0
    histograma_fallos: dict[str, int] = {}

    for entrada in entradas:
        contexto = {**contexto_base, "hoy": date.fromisoformat(entrada["fecha_mensaje"])}
        propuesta = extraer(entrada["texto"], contexto, entrada["id"])
        esperado = entrada["esperado"]

        if comparar_exacto(propuesta, esperado):
            exact_match += 1
        else:
            for fallo in diagnosticar(propuesta, esperado):
                histograma_fallos[fallo] = histograma_fallos.get(fallo, 0) + 1

        if es_error_silencioso(propuesta, esperado):
            error_silencioso += 1

    return {
        "total": total,
        "exact_match": exact_match,
        "exact_match_rate": exact_match / total if total else 0.0,
        "error_silencioso": error_silencioso,
        "error_silencioso_rate": error_silencioso / total if total else 0.0,
        "histograma_fallos": histograma_fallos,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", help="dev.jsonl o test.jsonl")
    args = parser.parse_args()

    entradas = cargar_corpus(args.corpus)
    contexto_base = {"franjas": _FRANJAS_CORPUS, "tipos_validos": _TIPOS_VALIDOS}

    resultado = evaluar_corpus(
        entradas,
        contexto_base,
        extraer=lambda texto, contexto, id_entrada: extraer_propuesta(texto, contexto),
    )

    print(f"Total anotadas: {resultado['total']}")
    print(f"Exact match: {resultado['exact_match']} ({resultado['exact_match_rate']:.1%})")
    print(
        f"Error silencioso: {resultado['error_silencioso']} "
        f"({resultado['error_silencioso_rate']:.1%})"
    )
    print("Histograma de fallos:", resultado["histograma_fallos"])


if __name__ == "__main__":
    main()
