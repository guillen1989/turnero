"""Tests E2E del flujo de publicación de turnos.

Estos tests habrían atrapado el bug del form anidado (accion=nueva_franja
colándose en el submit principal) que bloqueó a todos los usuarios.
"""
from datetime import date, timedelta


def _fecha(dias):
    return (date.today() + timedelta(days=dias)).strftime("%Y-%m-%d")


def test_publicar_turno_crea_publicacion(pagina_autenticada, live_server):
    page = pagina_autenticada
    page.goto(f"{live_server}/publicar")

    page.locator('input[name="fecha_cedida_0"]').fill(_fecha(7))
    page.locator('select[name="franja_cedida_0"]').select_option(index=1)

    page.locator('input[name="fecha_aceptada_0"]').fill(_fecha(14))
    page.locator('select[name="franja_aceptada_0"]').select_option(index=1)

    page.locator('#publicar-form button[type="submit"]').click()

    page.wait_for_url(f"{live_server}/")
    assert "Publicación creada" in page.content()


def test_publicar_sin_turno_cedido_muestra_error(pagina_autenticada, live_server):
    page = pagina_autenticada
    page.goto(f"{live_server}/publicar")

    # Solo rellena el aceptado, deja el cedido vacío.
    # El HTML tiene 'required', así que lo quitamos para que llegue al servidor
    # y probemos la validación server-side (la red de seguridad real).
    page.locator('input[name="fecha_aceptada_0"]').fill(_fecha(14))
    page.locator('select[name="franja_aceptada_0"]').select_option(index=1)
    page.evaluate("document.querySelectorAll('[required]').forEach(el => el.removeAttribute('required'))")

    page.locator('#publicar-form button[type="submit"]').click()

    assert "/publicar" in page.url
    assert "al menos un turno" in page.content()


def test_nueva_franja_no_interfiere_con_publicar(pagina_autenticada, live_server):
    """Regresión: el form de nueva franja era un form anidado dentro del principal.
    El navegador lo fusionaba, haciendo que el submit principal incluyera
    accion=nueva_franja y nunca creara la publicación.
    """
    page = pagina_autenticada
    page.goto(f"{live_server}/publicar")

    # Crear una nueva franja desde el form secundario
    page.locator('.nueva-franja-form input[name="franja_nombre"]').fill("Guardia 24h")
    page.locator('.nueva-franja-form input[name="franja_inicio"]').fill("08:00")
    page.locator('.nueva-franja-form input[name="franja_fin"]').fill("08:00")
    page.locator('.nueva-franja-form button[type="submit"]').click()

    # Vuelve a /publicar (no al inicio)
    page.wait_for_url(f"{live_server}/publicar")
    assert "Guardia 24h" in page.content()

    # Ahora publicar usando la franja recién creada
    page.locator('input[name="fecha_cedida_0"]').fill(_fecha(7))
    page.locator('select[name="franja_cedida_0"]').select_option(label="Guardia 24h (08:00–08:00)")

    page.locator('input[name="fecha_aceptada_0"]').fill(_fecha(14))
    page.locator('select[name="franja_aceptada_0"]').select_option(label="Guardia 24h (08:00–08:00)")

    page.locator('#publicar-form button[type="submit"]').click()
    page.wait_for_url(f"{live_server}/")
    assert "Publicación creada" in page.content()
