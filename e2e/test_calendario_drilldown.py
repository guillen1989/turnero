"""E2E: drill-down del calendario de ofertas (Paso 5).

Escenario: Pedro publica un 'regalo' (turno que se ofrece a trabajar) para
un día conocido del mes actual. Ana entra a /calendario, toca ese día,
toca la franja y sigue el enlace resultante — debe aterrizar en Buscar
cambios (/cambios) viendo la publicación de Pedro con el botón "Me interesa"
ya funcional (reutilizado, no reimplementado en el calendario).
"""
from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models import Categoria, FranjaHoraria, insertar_categorias_semilla
from app.services.publicaciones import publicar_cambio
from app.services.registro import registrar_usuario


@pytest.fixture
def escenario_oferta(e2e_app, clean_e2e_db):
    with e2e_app.app_context():
        insertar_categorias_semilla()
        cat = Categoria.query.filter_by(nombre="Enfermería").first()
        ana = registrar_usuario("Ana García", "ana@test.es", "pass1234", "Hospital E2E", "Urgencias", cat.id)
        pedro = registrar_usuario("Pedro Ruiz", "pedro@test.es", "pass1234", "Hospital E2E", "Urgencias", cat.id)

        gid = ana.unidad.grupo_intercambio_id
        manana = FranjaHoraria.query.filter_by(grupo_intercambio_id=gid, nombre="Mañana").first()

        fecha = date.today().replace(day=1) + timedelta(days=14)
        publicar_cambio(pedro.id, [], [(fecha, manana.id)], tipo="regalo")
        db.session.commit()

    return {
        "email": "ana@test.es",
        "password": "pass1234",
        "fecha": fecha,
        "pedro_nombre": "Pedro Ruiz",
    }


def test_drilldown_dia_franja_navega_a_publicacion(page, live_server, escenario_oferta):
    page.goto(f"{live_server}/auth/login")
    page.locator('input[name="email"]').fill(escenario_oferta["email"])
    page.locator('input[name="password"]').fill(escenario_oferta["password"])
    page.locator('[type="submit"]').click()
    page.wait_for_load_state("networkidle")

    # Un usuario recién registrado aterriza primero en /como-funciona (onboarding);
    # navegamos directamente al calendario en vez de depender de ese redirect.
    page.goto(f"{live_server}/calendario/")

    fecha_iso = escenario_oferta["fecha"].isoformat()
    page.locator(f'[data-fecha="{fecha_iso}"]').click()

    panel = page.locator("#calendario-panel")
    assert panel.is_visible()
    # El día solo tiene un tipo de turno, así que el panel salta directo a
    # la lista de publicaciones (sin el paso intermedio de elegir franja).
    page.locator("a.calendario-lista-item").first.click()

    page.wait_for_url(lambda url: "/cambios" in url)
    assert escenario_oferta["pedro_nombre"] in page.content()
    assert page.locator('button:has-text("Me interesa")').first.is_visible()


def test_dia_con_una_sola_franja_salta_directo_a_publicaciones(page, live_server, escenario_oferta):
    """Cuando un día solo tiene un tipo de turno, el panel debe saltarse el
    paso intermedio de elegir franja y mostrar directo la lista de
    publicaciones de esa franja (sin el botón "Mañana (1)")."""
    page.goto(f"{live_server}/auth/login")
    page.locator('input[name="email"]').fill(escenario_oferta["email"])
    page.locator('input[name="password"]').fill(escenario_oferta["password"])
    page.locator('[type="submit"]').click()
    page.wait_for_load_state("networkidle")

    page.goto(f"{live_server}/calendario/")

    fecha_iso = escenario_oferta["fecha"].isoformat()
    page.locator(f'[data-fecha="{fecha_iso}"]').click()

    panel = page.locator("#calendario-panel")
    assert panel.is_visible()

    # No debe verse el botón intermedio de franja ("Mañana (1)")...
    assert page.locator("button.calendario-lista-item").count() == 0
    # ...sino directamente el enlace a la publicación de Pedro.
    enlace = page.locator("a.calendario-lista-item").first
    assert enlace.is_visible()
    assert escenario_oferta["pedro_nombre"] in page.locator("#calendario-panel").inner_text()

    # Al ser la vista "raíz" de ese día, no debe ofrecerse "Volver".
    assert page.locator("#calendario-panel-volver").is_hidden()


def test_dia_vacio_ofrece_publicar_cambio(page, live_server, escenario_oferta):
    """Ronda 2, Paso 3: tocar un día SIN ofertas también abre el panel,
    con un enlace para publicar un cambio precargado con esa fecha/modo."""
    page.goto(f"{live_server}/auth/login")
    page.locator('input[name="email"]').fill(escenario_oferta["email"])
    page.locator('input[name="password"]').fill(escenario_oferta["password"])
    page.locator('[type="submit"]').click()
    page.wait_for_load_state("networkidle")

    page.goto(f"{live_server}/calendario/?modo=ofertas")

    fecha_vacia = escenario_oferta["fecha"] + timedelta(days=1)
    fecha_iso = fecha_vacia.isoformat()
    page.locator(f'[data-fecha="{fecha_iso}"]').click()

    panel = page.locator("#calendario-panel")
    assert panel.is_visible()

    enlace_publicar = page.locator("#calendario-panel a.calendario-btn-publicar")
    assert enlace_publicar.is_visible()

    href = enlace_publicar.get_attribute("href")
    assert f"fecha={fecha_iso}" in href
    assert "modo=ofertas" in href

    enlace_publicar.click()
    page.wait_for_url(lambda url: "/publicar" in url)
    assert page.locator(f'input[name="fecha_aceptada_0"][value="{fecha_iso}"]').count() == 1
