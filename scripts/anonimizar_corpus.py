"""Anonimiza un export de WhatsApp para usarlo como corpus del parser (docs/crear_parser.md).

Sustituye el remitente de cada línea por un pseudónimo consistente ([NOMBRE1],
[NOMBRE2]...) y enmascara teléfonos. NO sustituye nombres mencionados dentro del
cuerpo del mensaje: eso requiere revisión manual (ver Fase 0.1 del plan).

Uso: python scripts/anonimizar_corpus.py <export.txt> <destino.txt>
"""
import argparse
import re

# Línea de export de WhatsApp: "dd/mm/aa, hh:mm - Remitente: mensaje"
PATRON_LINEA = re.compile(
    r"^(?P<cabecera>\d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?\s*[-–]\s*)"
    r"(?P<remitente>[^:]+):\s*(?P<mensaje>.*)$"
)
PATRON_TELEFONO = re.compile(r"(\+?\d[\d\s()-]{6,}\d)")


def anonimizar_lineas(lineas: list[str]) -> list[str]:
    pseudonimos: dict[str, str] = {}
    salida = []
    for linea in lineas:
        m = PATRON_LINEA.match(linea.rstrip("\n"))
        if not m:
            salida.append(PATRON_TELEFONO.sub("[TELEFONO]", linea))
            continue
        remitente = m.group("remitente").strip()
        if remitente not in pseudonimos:
            pseudonimos[remitente] = f"[NOMBRE{len(pseudonimos) + 1}]"
        mensaje = PATRON_TELEFONO.sub("[TELEFONO]", m.group("mensaje"))
        salida.append(f"{m.group('cabecera')}{pseudonimos[remitente]}: {mensaje}\n")
    return salida


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origen", help="Export de WhatsApp en texto plano")
    parser.add_argument("destino", help="Ruta de salida anonimizada")
    args = parser.parse_args()

    with open(args.origen, encoding="utf-8") as f:
        lineas = f.readlines()

    salida = anonimizar_lineas(lineas)

    with open(args.destino, "w", encoding="utf-8") as f:
        f.writelines(salida)

    print(f"{len(salida)} líneas procesadas -> {args.destino}")
    print("Revisa a mano el resultado: nombres mencionados dentro de un mensaje no se sustituyen.")


if __name__ == "__main__":
    main()
