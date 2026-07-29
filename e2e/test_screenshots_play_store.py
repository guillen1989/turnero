"""Genera capturas de pantalla para la ficha de Play Store.

No es un test de comportamiento (no hace assert de negocio); reutiliza los
fixtures y helpers del golden path local para dejar la app en estados
visualmente representativos y capturar cada uno con Playwright.

Ejecución:
  anaconda3/bin/python3 -m pytest e2e/test_screenshots_play_store.py --headed -s
"""
from datetime import date
from pathlib import Path

import pytest

from app.extensions import db
from app.models import Categoria, FranjaHoraria, Usuario, insertar_categorias_semilla
from app.services.registro import registrar_usuario

OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "store-assets" / "screenshots"
VIEWPORT = {"width": 1080, "height": 2160}


def _login(page, base, email, password="pass1234"):
    page.goto(f"{base}/auth/login")
    page.locator('input[name="email"]').fill(email)
    page.locator('input[name="password"]').fill(password)
    page.locator('[type="submit"]').click()
    page.wait_for_url(f"{base}/calendario/")


def _tocar_turno(page, widget_id, franja_id, fecha_iso):
    widget = page.locator(f"#{widget_id}")
    widget.locator(f'.cal-turnos-chip[data-franja-id="{franja_id}"]').click()
    objetivo = date.fromisoformat(fecha_iso)
    hoy = date.today()
    for _ in range((objetivo.year - hoy.year) * 12 + (objetivo.month - hoy.month)):
        widget.locator('[data-role="next"]').click()
    widget.locator(f'button.cal-turnos-celda[data-fecha="{fecha_iso}"]').click()


def _publicar(page, base, fecha_cede, franja_cede, fecha_acepta, franja_acepta):
    page.goto(f"{base}/publicar")
    _tocar_turno(page, "cal-cedidos", franja_cede, fecha_cede)
    _tocar_turno(page, "cal-aceptados", franja_acepta, fecha_acepta)
    page.locator('#publicar-form button[type="submit"]').click()
    page.wait_for_url(f"{base}/")


@pytest.fixture
def tres_usuarios(e2e_app, clean_e2e_db):
    with e2e_app.app_context():
        insertar_categorias_semilla()
        cat = Categoria.query.filter_by(nombre="Enfermería").first()
        ana = registrar_usuario(
            "Ana García", "ana@test.es", "pass1234",
            "Hospital Universitario Central", "Urgencias", cat.id,
        )
        registrar_usuario(
            "Pedro López", "pedro@test.es", "pass1234",
            "Hospital Universitario Central", "Urgencias", cat.id,
        )
        registrar_usuario(
            "Carlos Ruiz", "carlos@test.es", "pass1234",
            "Hospital Universitario Central", "Urgencias", cat.id,
        )
        Usuario.query.filter(
            Usuario.email.in_(["ana@test.es", "pedro@test.es", "carlos@test.es"])
        ).update({"onboarding_visto": True})
        db.session.commit()

        grupo_id = ana.unidad.grupo_intercambio_id
        franja_m = FranjaHoraria.query.filter_by(
            grupo_intercambio_id=grupo_id, nombre="Mañana"
        ).first()
        franja_t = FranjaHoraria.query.filter_by(
            grupo_intercambio_id=grupo_id, nombre="Tarde"
        ).first()
        return {"manana_id": str(franja_m.id), "tarde_id": str(franja_t.id)}


def test_generar_capturas(page, live_server, tres_usuarios):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    page.set_viewport_size(VIEWPORT)
    m = tres_usuarios["manana_id"]
    t = tres_usuarios["tarde_id"]

    from datetime import timedelta
    hoy = date.today()
    f_ana_cede = (hoy + timedelta(days=10)).isoformat()
    f_ana_acepta = (hoy + timedelta(days=40)).isoformat()
    f_pedro_cede = (hoy + timedelta(days=25)).isoformat()

    # 1. Ana publica un cambio
    _login(page, live_server, "ana@test.es")
    _publicar(page, live_server, f_ana_cede, m, f_ana_acepta, t)
    page.goto(f"{live_server}/")
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT_DIR / "01_dashboard.png"))

    page.goto(f"{live_server}/calendario/")
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT_DIR / "02_calendario.png"))
    page.goto(f"{live_server}/auth/logout")

    # 2. Pedro publica -> solapamiento -> oportunidad a 3
    _login(page, live_server, "pedro@test.es")
    _publicar(page, live_server, f_pedro_cede, m, f_ana_cede, m)
    page.goto(f"{live_server}/avisos")
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT_DIR / "03_avisos.png"))

    page.goto(f"{live_server}/")
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT_DIR / "04_dashboard_oportunidad_3.png"))
    page.goto(f"{live_server}/auth/logout")

    # 3. Carlos busca cambios y ve la oportunidad
    _login(page, live_server, "carlos@test.es")
    page.goto(f"{live_server}/cambios")
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT_DIR / "05_buscar_cambios.png"))

    page.locator('button:has-text("Me interesa")').first.click()
    page.wait_for_selector('#modal-me-interesa:not(.modal-hidden)')
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT_DIR / "06_modal_me_interesa.png"))
    page.locator('#mmi-form button[type="submit"]').click()

    page.wait_for_url(f"{live_server}/")
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT_DIR / "07_dashboard_match_3_bandas.png"))
