"""Tests E2E del flujo de publicación de turnos.

Estos tests habrían atrapado el bug del form anidado (accion=nueva_franja
colándose en el submit principal) que bloqueó a todos los usuarios.

El formulario usa un calendario tap-to-select (elegir franja + tocar días)
en vez de filas manuales de fecha/tipo de turno, así que los helpers de
este fichero simulan exactamente esa interacción: click en el chip de la
franja, click en el día dentro del calendario (navegando de mes si hace
falta).
"""
from datetime import date, timedelta


def _fecha(dias):
    return (date.today() + timedelta(days=dias))


def _tocar_turno(page, widget_id, franja_nombre, fecha):
    """Elige la franja `franja_nombre` y toca el día `fecha` (date) en el
    calendario del widget `widget_id` ('cal-cedidos' o 'cal-aceptados')."""
    widget = page.locator(f"#{widget_id}")
    widget.locator(f'.cal-turnos-chip[data-franja-nombre="{franja_nombre}"]').click()

    hoy = date.today()
    meses_a_avanzar = (fecha.year - hoy.year) * 12 + (fecha.month - hoy.month)
    for _ in range(meses_a_avanzar):
        widget.locator('[data-role="next"]').click()

    widget.locator(f'button.cal-turnos-celda[data-fecha="{fecha.isoformat()}"]').click()


def test_publicar_turno_crea_publicacion(pagina_autenticada, live_server):
    page = pagina_autenticada
    page.goto(f"{live_server}/publicar")

    _tocar_turno(page, "cal-cedidos", "Mañana", _fecha(7))
    _tocar_turno(page, "cal-aceptados", "Mañana", _fecha(14))

    page.locator('#publicar-form button[type="submit"]').click()

    page.wait_for_url(f"{live_server}/")
    assert "Publicación creada" in page.content()


def test_publicar_sin_turno_cedido_muestra_error(pagina_autenticada, live_server):
    page = pagina_autenticada
    page.goto(f"{live_server}/publicar")

    # Solo toca el aceptado, deja el cedido vacío: sin franja activa marcada
    # en "cedidos" no se genera ningún fecha_cedida_N, así que el servidor
    # debe rechazar la publicación (red de seguridad real, sin depender de
    # nada del lado cliente).
    _tocar_turno(page, "cal-aceptados", "Mañana", _fecha(14))

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

    # Ahora publicar usando la franja recién creada (una unidad puede tener
    # más tipos de turno que los de serie, incluidos los que crean sus
    # propios usuarios — deben aparecer como chip igual que cualquier otro).
    _tocar_turno(page, "cal-cedidos", "Guardia 24h", _fecha(7))
    _tocar_turno(page, "cal-aceptados", "Guardia 24h", _fecha(14))

    page.locator('#publicar-form button[type="submit"]').click()
    page.wait_for_url(f"{live_server}/")
    assert "Publicación creada" in page.content()


def test_publicar_varios_turnos_de_una_franja_de_un_tap(e2e_app, pagina_autenticada, live_server):
    """El motivo del rediseño: ceder varios días del mismo turno sin añadir
    una fila por cada uno — se elige la franja una vez y se tocan varios días."""
    page = pagina_autenticada
    page.goto(f"{live_server}/publicar")

    widget = page.locator("#cal-cedidos")
    widget.locator('.cal-turnos-chip[data-franja-nombre="Mañana"]').click()
    for dias in (7, 8, 9):
        fecha = _fecha(dias)
        widget.locator(f'button.cal-turnos-celda[data-fecha="{fecha.isoformat()}"]').click()

    assert widget.locator('input[type="hidden"][name^="fecha_cedida_"]').count() == 3

    _tocar_turno(page, "cal-aceptados", "Mañana", _fecha(20))
    page.locator('#publicar-form button[type="submit"]').click()
    page.wait_for_url(f"{live_server}/")

    with e2e_app.app_context():
        from app.models import PublicacionCambio
        pub = PublicacionCambio.query.order_by(PublicacionCambio.id.desc()).first()
        assert len(pub.turnos_cedidos) == 3
