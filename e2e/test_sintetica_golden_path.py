"""Golden-path visual: aviso de oportunidad a 3 + cambio sintético a 3 bandas.

Escenario:
  Ana    → cede 10/07 Mañana · acepta 03/08 Tarde
  Pedro  → cede 21/07 Mañana · acepta 10/07 Mañana  ← coincide con lo que Ana cede
  Carlos → hace «Me interesa» en la Oportunidad a 3  → cierra el triángulo

Al publicar Pedro se produce solapamiento unilateral:
  · Pedro acepta lo que Ana ofrece  → ✓
  · Ana  no acepta lo que Pedro ofrece → ✗ (fechas distintas)
  → aviso_oportunidad_3 (combinado) + publicación sintética para ambos

Carlos ve la sintética en Buscar cambios, hace «Me interesa» y acepta
los turnos en el modal → se crea el match cadena_3 sin que Carlos
necesite publicar su propio cambio.

Ejecución (headed, con pausa visual):
  pytest e2e/test_sintetica_golden_path.py --headed --slowmo=600 -s
"""
import pytest

from app.extensions import db
from app.models import Categoria, FranjaHoraria, Usuario, insertar_categorias_semilla
from app.services.registro import registrar_usuario


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(page, base, email, password="pass1234"):
    page.goto(f"{base}/auth/login")
    page.locator('input[name="email"]').fill(email)
    page.locator('input[name="password"]').fill(password)
    page.locator('[type="submit"]').click()
    page.wait_for_url(f"{base}/calendario/")


def _publicar(page, base, fecha_cede, franja_cede, fecha_acepta, franja_acepta):
    page.goto(f"{base}/publicar")
    page.locator('input[name="fecha_cedida_0"]').fill(fecha_cede)
    page.locator('select[name="franja_cedida_0"]').select_option(franja_cede)
    page.locator('input[name="fecha_aceptada_0"]').fill(fecha_acepta)
    page.locator('select[name="franja_aceptada_0"]').select_option(franja_acepta)
    page.locator('#publicar-form button[type="submit"]').click()
    page.wait_for_url(f"{base}/")


# ---------------------------------------------------------------------------
# Fixture: tres usuarios en el mismo hospital/grupo
# ---------------------------------------------------------------------------

@pytest.fixture
def tres_usuarios(e2e_app, clean_e2e_db):
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
        registrar_usuario(
            "Carlos Ruiz", "carlos@test.es", "pass1234",
            "Hospital Demo", "Urgencias", cat.id,
        )
        # Saltar onboarding para que el login redirija a / directamente
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


# ---------------------------------------------------------------------------
# Golden path
# ---------------------------------------------------------------------------

def test_golden_path_cambio_a_3(page, live_server, tres_usuarios):
    """
    Golden path completo:

    1. Ana publica (cede 10/07 M · acepta 03/08 T).
    2. Pedro publica (cede 21/07 M · acepta 10/07 M) → solapamiento unilateral.
       → sistema genera aviso_oportunidad_3 (combinado) + publicación sintética.
    3. Pedro ve /avisos (pausa 5 s): muestra «Oportunidad a 3».
    4. Pedro ve Mis cambios > Activos (pausa 5 s): tarjeta de oportunidad a 3 bandas.
    5. Pedro hace logout.
    6. Carlos entra en Buscar cambios (pausa 3 s): ve la «Oportunidad a 3».
    7. Carlos hace clic en «Me interesa» → se abre el modal.
    8. Carlos acepta (pausa 2 s en modal) → sistema crea match cadena_3.
    9. Carlos ve su dashboard (pausa 5 s): aparece «¡Cambio a 3 bandas!».
    """
    m = tres_usuarios["manana_id"]
    t = tres_usuarios["tarde_id"]

    # ── 1. Ana publica ────────────────────────────────────────────────────
    _login(page, live_server, "ana@test.es")
    _publicar(page, live_server, "2026-07-10", m, "2026-08-03", t)
    page.goto(f"{live_server}/auth/logout")

    # ── 2. Pedro publica (solapamiento unilateral) ────────────────────────
    _login(page, live_server, "pedro@test.es")
    _publicar(page, live_server, "2026-07-21", m, "2026-07-10", m)

    # ── 3. Pedro · /avisos (5 s) ──────────────────────────────────────────
    page.goto(f"{live_server}/avisos")
    assert "Oportunidad a 3" in page.content(), "Falta aviso_oportunidad_3 en /avisos de Pedro"
    page.wait_for_timeout(5000)

    # ── 4. Pedro · Mis cambios > Activos (5 s) ────────────────────────────
    page.goto(f"{live_server}/")
    assert "Oportunidad a 3 bandas" in page.content(), "Falta tarjeta oportunidad_3 en dashboard"
    page.wait_for_timeout(5000)

    # ── 5. Pedro · logout ─────────────────────────────────────────────────
    page.goto(f"{live_server}/auth/logout")

    # ── 6. Carlos · Buscar cambios (pausa 3 s) ────────────────────────────
    _login(page, live_server, "carlos@test.es")
    page.goto(f"{live_server}/cambios")
    assert "Oportunidad a 3" in page.content(), "Carlos no ve la Oportunidad a 3 en /cambios"
    page.wait_for_timeout(3000)

    # ── 7. Carlos · clic en «Me interesa» ────────────────────────────────
    page.locator('button:has-text("Me interesa")').first.click()
    page.wait_for_selector('#modal-me-interesa:not(.modal-hidden)')

    # ── 8. Modal: turnos pre-seleccionados, Carlos acepta (pausa 2 s) ─────
    # El JS pre-rellena mmi-tc y mmi-ta con el primer cedido y aceptado de
    # la pub sintética, así que Carlos solo tiene que confirmar.
    page.wait_for_timeout(2000)
    page.locator('#mmi-form button[type="submit"]').click()

    # ── 9. Dashboard de Carlos: cadena_3 propuesto (pausa 5 s) ───────────
    page.wait_for_url(f"{live_server}/")
    assert "3 bandas" in page.content(), "No aparece el match cadena_3 en el dashboard de Carlos"
    page.wait_for_timeout(5000)
