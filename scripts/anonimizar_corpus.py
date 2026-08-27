"""Anonimiza un export de WhatsApp para usarlo como corpus del parser (docs/crear_parser.md).

Sustituye el remitente de cada línea por un pseudónimo consistente ([NOMBRE1],
[NOMBRE2]...) y enmascara teléfonos. Soporta tanto el formato de export con
guion ("dd/mm/aa, hh:mm - Remitente: mensaje") como el de corchetes
("[dd/mm(/aa), hh:mm] Remitente: mensaje"), y mensajes reenviados que
envuelven otra línea con cabecera propia dentro del cuerpo. NO sustituye
nombres mencionados dentro del cuerpo del mensaje: eso requiere revisión
manual (ver Fase 0.1 del plan).

Uso: python scripts/anonimizar_corpus.py <export.txt> <destino.txt>
"""
import argparse
import re

# Cabecera de export de WhatsApp, con o sin corchetes:
# "dd/mm/aa, hh:mm - Remitente: mensaje" o "[dd/mm(/aa), hh:mm] Remitente: mensaje"
PATRON_LINEA = re.compile(
    r"^(?P<apertura>\[?)"
    r"(?P<fecha>\d{1,2}/\d{1,2}(?:/\d{2,4})?,?\s+\d{1,2}:\d{2}(?::\d{2})?)"
    r"(?(apertura)\]|\s*[-–])"
    r"\s*(?P<remitente>[^:]+):\s?(?P<resto>.*)$"
)
PATRON_TELEFONO = re.compile(r"(\+?\d[\d\s()-]{6,}\d)")


def _pseudonimo_de(remitente: str, pseudonimos: dict[str, str]) -> str:
    remitente = remitente.strip()
    if PATRON_TELEFONO.fullmatch(remitente):
        return "[TELEFONO]"
    if remitente not in pseudonimos:
        pseudonimos[remitente] = f"[NOMBRE{len(pseudonimos) + 1}]"
    return pseudonimos[remitente]


def _anonimizar_texto(texto: str, pseudonimos: dict[str, str]) -> str:
    """Anonimiza una línea o cabecera, incluyendo envolturas anidadas de reenvíos."""
    m = PATRON_LINEA.match(texto)
    if not m:
        return PATRON_TELEFONO.sub("[TELEFONO]", texto)
    pseudonimo = _pseudonimo_de(m.group("remitente"), pseudonimos)
    resto = _anonimizar_texto(m.group("resto"), pseudonimos)
    cierre = "]" if m.group("apertura") else ""
    return f"{m.group('apertura')}{m.group('fecha')}{cierre} {pseudonimo}: {resto}"


def anonimizar_lineas(lineas: list[str]) -> list[str]:
    pseudonimos: dict[str, str] = {}
    salida = []
    for linea in lineas:
        sin_salto = linea.rstrip("\n")
        tiene_salto = linea.endswith("\n")
        procesada = _anonimizar_texto(sin_salto, pseudonimos)
        salida.append(procesada + "\n" if tiene_salto else procesada)
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
