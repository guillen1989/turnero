"""Golden-path visual: aviso de interés + cambio sintético a 3 bandas.

Escenario:
  Ana    → cede 10/07 Mañana · acepta 03/08 Tarde
  Pedro  → cede 21/07 Mañana · acepta 10/07 Mañana  ← coincide con lo que Ana cede

Al publicar Pedro se produce solapamiento unilateral:
  · Pedro acepta lo que Ana ofrece  → ✓
  · Ana  no acepta lo que Pedro ofrece → ✗ (fechas distintas)

Resultado esperado en /avisos de Pedro (y de Ana si comprueba):
  · Badge naranja «Interés»       — aviso_interes
  · Badge azul  «Oportunidad a 3» — aviso_sintetica

Ejecución:
  pytest e2e/test_sintetica_golden_path.py --headed --slowmo=800 -s
"""
import pytest

from app.extensions import db
from app.models import Categoria, FranjaHoraria, Usuario, insertar_categorias_semilla
from app.services.registro import registrar_usuario


# ---------------------------------------------------------------------------
# Fixtures locales
# ---------------------------------------------------------------------------

@pytest.fixture
def dos_usuarios(e2e_app, clean_e2e_db):
    """Crea Ana y Pedro en el mismo hospital/grupo y devuelve los IDs de franja."""
    with e2e_app.app_context():
        insertar_categorias_semilla()
        cat = Categoria.query.filter_by(nombre="Enfermería").first()
        ana = registrar_usuario(
            "Ana García", "ana@test.es", "pass1234",
            "Hospital Demo", "Urgencias", cat.id,
        )
        registrar_usuario(
            "Pedro López", "pedro@test.es", "pass1234",
            "Hospital Demo", "Urgencias", cat.id,
        )
        # Marcar onboarding como visto para que el login redirija a / directamente
        Usuario.query.filter(
            Usuario.email.in_(["ana@test.es", "pedro@test.es"])
        ).update({"onboarding_visto": True})
        db.session.commit()
        grupo_id = ana.unidad.grupo_intercambio_id
        franja_m = FranjaHoraria.query.filter_by(
            grupo_intercambio_id=grupo_id, nombre="Mañana"
        ).first()
        franja_t = FranjaHoraria.query.filter_by(
            grupo_intercambio_id=grupo_id, nombre="Tarde"
        ).first()
        return {"manana_id": franja_m.id, "tarde_id": franja_t.id}


# ---------------------------------------------------------------------------
# Golden path
# ---------------------------------------------------------------------------

def test_aviso_interes_y_sintetica(page, live_server, dos_usuarios):
    """
    Demuestra visualmente el ciclo completo:
    1. Ana publica un cambio.
    2. Pedro publica un cambio con solapamiento unilateral.
    3. El sistema genera aviso_interes y aviso_sintetica para ambos.
    4. El test pausa en /avisos de Pedro para que puedas inspeccionar.
    """
    franja_m = str(dos_usuarios["manana_id"])
    franja_t = str(dos_usuarios["tarde_id"])

    # ------------------------------------------------------------------ #
    # 1. Ana se autentica y publica
    # ------------------------------------------------------------------ #
    page.goto(f"{live_server}/auth/login")
    page.locator('input[name="email"]').fill("ana@test.es")
    page.locator('input[name="password"]').fill("pass1234")
    page.locator('[type="submit"]').click()
    page.wait_for_url(f"{live_server}/")

    page.goto(f"{live_server}/publicar")
    page.locator('input[name="fecha_cedida_0"]').fill("2026-07-10")
    page.locator('select[name="franja_cedida_0"]').select_option(franja_m)
    page.locator('input[name="fecha_aceptada_0"]').fill("2026-08-03")
    page.locator('select[name="franja_aceptada_0"]').select_option(franja_t)
    page.locator('#publicar-form button[type="submit"]').click()
    page.wait_for_url(f"{live_server}/")

    # ------------------------------------------------------------------ #
    # 2. Ana cierra sesión
    # ------------------------------------------------------------------ #
    page.goto(f"{live_server}/auth/logout")

    # ------------------------------------------------------------------ #
    # 3. Pedro se autentica y publica (solapamiento unilateral con Ana)
    #    · Pedro acepta  10/07 Mañana  ← lo que Ana cede          ✓
    #    · Pedro cede   21/07 Mañana   ← Ana no lo quiere (acepta 03/08 Tarde) ✗
    # ------------------------------------------------------------------ #
    page.goto(f"{live_server}/auth/login")
    page.locator('input[name="email"]').fill("pedro@test.es")
    page.locator('input[name="password"]').fill("pass1234")
    page.locator('[type="submit"]').click()
    page.wait_for_url(f"{live_server}/")

    page.goto(f"{live_server}/publicar")
    page.locator('input[name="fecha_cedida_0"]').fill("2026-07-21")
    page.locator('select[name="franja_cedida_0"]').select_option(franja_m)
    page.locator('input[name="fecha_aceptada_0"]').fill("2026-07-10")
    page.locator('select[name="franja_aceptada_0"]').select_option(franja_m)
    page.locator('#publicar-form button[type="submit"]').click()
    page.wait_for_url(f"{live_server}/")

    # ------------------------------------------------------------------ #
    # 4. Ir a /avisos de Pedro — aquí verás los dos avisos
    # ------------------------------------------------------------------ #
    page.goto(f"{live_server}/avisos")

    # Verificaciones mínimas (confirman que el motor funcionó)
    assert "Interés" in page.content(), "Falta el aviso_interes en /avisos de Pedro"
    assert "Oportunidad a 3" in page.content(), "Falta el aviso_sintetica en /avisos de Pedro"

    # Pausa — el navegador queda abierto para que puedas inspeccionar.
    # Pulsa «Resume» en el Inspector de Playwright cuando hayas terminado.
    page.pause()
