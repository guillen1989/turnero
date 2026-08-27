"""Test E2E: rellenar el mensaje del asistente desde el portapapeles.

Sustituye al Web Share Target (WhatsApp Android no permite compartir
mensajes de texto al share sheet del sistema, solo Copiar/Reenviar dentro
de la propia app), así que la vía real para traer el mensaje es que el
usuario lo copie en WhatsApp y la app lo lea del portapapeles.
"""

MENSAJE = "cambio mi mañana del 28 por tu tarde del 29"


def test_boton_pegar_rellena_el_textarea_desde_el_portapapeles(pagina_autenticada, live_server):
    page = pagina_autenticada
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.goto(f"{live_server}/publicar")

    page.evaluate("text => navigator.clipboard.writeText(text)", MENSAJE)

    page.locator("#btn-abrir-asistente").click()
    page.locator("#btn-pegar-portapapeles").click()

    assert page.locator("#asistente-texto").input_value() == MENSAJE
