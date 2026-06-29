"""Golden-path visual contra la app de staging en Railway.

Escenario idéntico al test local pero sin fixtures de BD:
los tres usuarios se registran via UI y los datos se crean en staging.

  Ana    → cede 10/07 Mañana · acepta 03/08 Tarde
  Pedro  → cede 21/07 Mañana · acepta 10/07 Mañana  ← solapamiento unilateral
  Carlos → hace «Me interesa» en la Oportunidad a 3  → cierra el triángulo

Prereqs:
  - App de staging desplegada y accesible
  - Seed ejecutado: Hospital Universitario La Paz / UCO / Enfermería ya existen
  - STAGING_URL definida en .env (o como variable de entorno)

Ejecución:
  pytest e2e/test_sintetica_staging.py --headed --slowmo=600 -s
"""
import os
import time

import pytest
from dotenv import load_dotenv

load_dotenv()

_BASE = os.getenv("STAGING_URL", "").rstrip("/")
pytestmark = pytest.mark.skipif(not _BASE, reason="STAGING_URL no configurada en .env")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(page, email, password="TestPass2026!"):
    page.goto(f"{_BASE}/auth/login")
    page.locator('input[name="email"]').fill(email)
    page.locator('input[name="password"]').fill(password)
    page.locator('[type="submit"]').click()
    # login puede redirigir a /como-funciona la primera vez
    page.wait_for_load_state("networkidle")
    if "como-funciona" in page.url:
        page.goto(f"{_BASE}/")
        page.wait_for_load_state("networkidle")


def _publicar(page, fecha_cede, franja_cede_nombre, fecha_acepta, franja_acepta_nombre):
    """Publica un cambio (tipo por defecto) eligiendo franjas por nombre parcial."""
    page.goto(f"{_BASE}/publicar")
    page.wait_for_selector('input[name="fecha_cedida_0"]')

    # Los options de franja incluyen el horario: «Mañana (07:00–15:00)»
    # Usamos evaluate para buscar por texto parcial en lugar de por value/label exacto.
    def _sel_franja(select_name, nombre_franja):
        valor = page.locator(f'select[name="{select_name}"]').evaluate(
            "(sel, n) => { const o = [...sel.options].find(x => x.text.includes(n)); return o ? o.value : ''; }",
            nombre_franja,
        )
        page.locator(f'select[name="{select_name}"]').select_option(value=valor)

    page.locator('input[name="fecha_cedida_0"]').fill(fecha_cede)
    _sel_franja("franja_cedida_0", franja_cede_nombre)
    page.locator('input[name="fecha_aceptada_0"]').fill(fecha_acepta)
    _sel_franja("franja_aceptada_0", franja_acepta_nombre)
    page.locator('#publicar-form button[type="submit"]').click()
    page.wait_for_load_state("networkidle")


def _registrar(page, nombre, email, password="TestPass2026!"):
    """Registra un usuario nuevo via UI usando Hospital La Paz / UCO / Enfermería."""
    page.goto(f"{_BASE}/auth/registro")
    page.locator('input[name="nombre"]').fill(nombre)
    page.locator('input[name="email"]').fill(email)
    page.locator('input[name="password"]').fill(password)
    page.locator('input[name="password2"]').fill(password)

    # País: opciones pre-cargadas en el HTML (sin AJAX)
    page.locator('#pais-select').select_option(label="España")

    # Cada selección dispara AJAX; esperamos a que aparezca la opción concreta
    # antes de interactuar con el siguiente select.
    page.wait_for_function(
        "[...document.querySelector('#provincia-select').options].some(o => o.text.includes('Madrid'))"
    )
    page.locator('#provincia-select').select_option(label="Madrid")

    page.wait_for_function(
        "[...document.querySelector('#ciudad-select').options].some(o => o.text.includes('Madrid'))"
    )
    page.locator('#ciudad-select').select_option(label="Madrid")

    page.wait_for_function(
        "[...document.querySelector('#hospital-select').options].some(o => o.text.includes('La Paz'))"
    )
    page.locator('#hospital-select').select_option(label="Hospital Universitario La Paz")

    # Categoría: select estático (no AJAX), pero cambia qué unidades se muestran
    page.locator('#categoria-select').select_option(label="Enfermería")

    # Esperar a que aparezca la unidad UCO en el select
    page.wait_for_function(
        "[...document.querySelector('#unidad-select').options].some(o => o.text.includes('UCO'))"
    )
    page.locator('#unidad-select').select_option(label="UCO")

    page.locator('[type="submit"]').click()
    # Registro redirige a /como-funciona; visitarlo marca onboarding_visto = True
    page.wait_for_load_state("networkidle")
    if "como-funciona" in page.url:
        page.wait_for_timeout(400)
        page.goto(f"{_BASE}/")
        page.wait_for_load_state("networkidle")


# ---------------------------------------------------------------------------
# Golden path
# ---------------------------------------------------------------------------

def test_golden_path_staging(page):
    """
    1. Registra Ana, Pedro y Carlos en La Paz/UCO/Enfermería (mismos grupo).
    2. Ana publica cambio (cede 10/07 M · acepta 03/08 T).
    3. Pedro publica cambio (cede 21/07 M · acepta 10/07 M) → solapamiento.
       Sistema genera aviso_oportunidad_3 + publicación sintética.
    4. Pedro · /avisos (5 s): «Oportunidad a 3» (aviso combinado).
    5. Pedro · dashboard (5 s): tarjeta oportunidad a 3 y botón Compartir.
    6. Pedro logout.
    7. Carlos · Buscar cambios (3 s): ve la sintética con botón WhatsApp.
    8. Carlos · «Me interesa» → modal (2 s) → acepta → cadena_3.
    9. Dashboard Carlos (5 s): «¡Cambio a 3 bandas!».
    """
    ts = str(int(time.time()))
    ana_email    = f"ana.gp.{ts}@test.es"
    pedro_email  = f"pedro.gp.{ts}@test.es"
    carlos_email = f"carlos.gp.{ts}@test.es"

    # ── Registrar los tres usuarios ────────────────────────────────────────
    _registrar(page, "Ana Golden", ana_email)
    page.goto(f"{_BASE}/auth/logout")

    _registrar(page, "Pedro Golden", pedro_email)
    page.goto(f"{_BASE}/auth/logout")

    _registrar(page, "Carlos Golden", carlos_email)
    page.goto(f"{_BASE}/auth/logout")

    # ── 1. Ana publica ─────────────────────────────────────────────────────
    _login(page, ana_email)
    _publicar(page, "2026-07-10", "Mañana", "2026-08-03", "Tarde")
    page.goto(f"{_BASE}/auth/logout")

    # ── 2. Pedro publica (solapamiento unilateral) ─────────────────────────
    _login(page, pedro_email)
    _publicar(page, "2026-07-21", "Mañana", "2026-07-10", "Mañana")

    # ── 3. Pedro · /avisos (5 s) ───────────────────────────────────────────
    page.goto(f"{_BASE}/avisos")
    assert "Oportunidad a 3" in page.content(), "Falta aviso_oportunidad_3 en /avisos de Pedro"
    page.wait_for_timeout(5000)

    # ── 4. Pedro · dashboard Activos (5 s) ────────────────────────────────
    page.goto(f"{_BASE}/")
    assert "Oportunidad a 3 bandas" in page.content(), "Falta tarjeta oportunidad_3 en dashboard de Pedro"
    assert "Oportunidad a 3"        in page.content(), "Falta aviso oportunidad_3 en dashboard de Pedro"
    assert "Compartir"              in page.content(), "Falta botón de compartir por WhatsApp"
    page.wait_for_timeout(5000)

    # ── 5. Pedro logout ────────────────────────────────────────────────────
    page.goto(f"{_BASE}/auth/logout")

    # ── 6. Carlos · Buscar cambios (3 s) ──────────────────────────────────
    _login(page, carlos_email)
    page.goto(f"{_BASE}/cambios")
    assert "Oportunidad a 3" in page.content(), "Carlos no ve la Oportunidad a 3 en /cambios"
    page.wait_for_timeout(3000)

    # ── 7. Carlos · «Me interesa» → modal (2 s) → acepta ──────────────────
    # En staging hay otras pubs del seed en el mismo grupo. Usamos el selector
    # específico de la tarjeta sintética para no confundirnos con otra pub.
    page.locator('.publicacion-card:has(.tipo-badge--sintetica) button:has-text("Me interesa")').first.click()
    page.wait_for_selector('#modal-me-interesa:not(.modal-hidden)')
    page.wait_for_timeout(2000)
    # El form post redirige a / en caso de éxito o a /cambios si falla.
    # Usamos expect_navigation para asegurar que Playwright espera la redirección completa.
    with page.expect_navigation(timeout=20000):
        page.locator('#mmi-form button[type="submit"]').click()

    # ── 8. Dashboard Carlos: cadena_3 (5 s) ───────────────────────────────
    content = page.content()
    assert "3 bandas" in content, (
        f"No aparece el match cadena_3 en el dashboard de Carlos. "
        f"URL actual: {page.url}. "
        f"¿Flash de éxito?: {'Cambio a 3 bandas iniciado' in content}. "
        f"¿Sección matches?: {'matches-section' in content}. "
        f"¿Flash de error?: {'No fue posible' in content or 'ya no está' in content}. "
        f"Fragmento (2000-3000): {content[2000:3000]!r}"
    )
    page.wait_for_timeout(5000)
