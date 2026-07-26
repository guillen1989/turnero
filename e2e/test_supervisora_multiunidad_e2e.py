"""E2E: flujo completo — crear supervisora con 2 unidades, invitacion, login,
selector de unidad en /planilla/supervision/ y /planilla/importar/."""
import secrets

import pytest

from app.extensions import db
from app.models import (
    Categoria, Ciudad, GrupoIntercambio, Hospital, Pais, Provincia,
    Unidad, UnidadSupervisada, Usuario,
)
from app.services.password_reset import generar_token_reset
from app.services.planilla_matching import resolver_o_crear_trabajador


@pytest.fixture
def escenario_completo(e2e_app, clean_e2e_db):
    """Crea pais, provincia, ciudad, hospital, 3 unidades, categoria,
    admin y una supervisora con 2 unidades supervisadas con contraseña
    aleatoria (sin token de invitacion generado aun)."""
    with e2e_app.app_context():
        pais = Pais(nombre="España")
        db.session.add(pais)
        db.session.commit()

        provincia = Provincia(nombre="Madrid", pais=pais)
        ciudad = Ciudad(nombre="Madrid", provincia=provincia)
        hospital = Hospital(nombre="H-E2E-Flow", ciudad=ciudad)
        grupo = GrupoIntercambio()
        db.session.add_all([provincia, ciudad, hospital, grupo])
        db.session.commit()

        uci = Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo)
        urgencias = Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo)
        otra = Unidad(nombre="Traumatología", hospital=hospital, grupo_intercambio=grupo)
        categoria = Categoria(nombre="Enfermería")
        db.session.add_all([uci, urgencias, otra, categoria])
        db.session.commit()

        admin = Usuario(
            nombre="Admin", email="admin@e2e-flow.es", unidad=uci,
            categoria=categoria, es_admin=True, onboarding_visto=True,
        )
        admin.set_password("admin1234")
        db.session.add(admin)
        db.session.commit()

        supervisora = Usuario(
            nombre="Supervisora Flow", email="sup@e2e-flow.es", unidad=uci,
            categoria=categoria, es_supervisora=True, onboarding_visto=True,
        )
        supervisora.set_password(secrets.token_urlsafe(32))
        db.session.add(supervisora)
        db.session.commit()

        db.session.add_all([
            UnidadSupervisada(usuario_id=supervisora.id, unidad_id=uci.id),
            UnidadSupervisada(usuario_id=supervisora.id, unidad_id=urgencias.id),
        ])
        db.session.commit()

        resolver_o_crear_trabajador(uci, "11111", "GARCIA, ANA")
        resolver_o_crear_trabajador(urgencias, "22222", "LOPEZ, CRIS")
        resolver_o_crear_trabajador(otra, "33333", "MARTIN, CARLOS")

        return {
            "admin_email": "admin@e2e-flow.es",
            "admin_password": "admin1234",
            "supervisora_email": "sup@e2e-flow.es",
            "uci_id": uci.id,
            "uci_nombre": uci.nombre,
            "urgencias_id": urgencias.id,
            "urgencias_nombre": urgencias.nombre,
            "otra_nombre": otra.nombre,
        }


def _login(page, live_server, email, password):
    page.goto(f"{live_server}/auth/login")
    page.locator('input[name="email"]').fill(email)
    page.locator('input[name="password"]').fill(password)
    page.locator('[type="submit"]').click()
    page.wait_for_url(f"{live_server}/calendario/")


def test_flujo_completo_supervisora_multiunidad(
    page, live_server, e2e_app, escenario_completo
):
    """Prueba manual end-to-end descrita en Paso 7 del plan:
    1. Como admin, crear una supervisora con 2 unidades
    2. La invitacion por email genera un token de reset valido
    3. La supervisora establece su contraseña via el enlace
    4. Inicia sesion y puede alternar entre sus 2 unidades en
       /planilla/supervision/ y /planilla/importar/
    """
    sup_email = escenario_completo["supervisora_email"]
    uci = escenario_completo["uci_nombre"]
    urgencias = escenario_completo["urgencias_nombre"]

    # 1 + 2 — El admin crea la supervisora (simulado en fixture DB).
    # La cuenta existe con contraseña aleatoria desconocida.
    # Login con contraseña trivial debe fallar.
    page.goto(f"{live_server}/auth/login")
    page.locator('input[name="email"]').fill(sup_email)
    page.locator('input[name="password"]').fill("pass1234")
    page.locator('[type="submit"]').click()
    page.wait_for_url(f"{live_server}/auth/login")
    body_text = page.locator("body").inner_text().lower()
    assert any(
        palabra in body_text
        for palabra in ("incorrecto", "incorrecta", "inválido", "error")
    ), f"No se encontro mensaje de error de login, body: {body_text[:200]}"

    # 3 — Generar token de invitacion/reset y establecer contraseña
    with e2e_app.app_context():
        sup = Usuario.query.filter_by(email=sup_email).first()
        assert sup is not None
        raw_token = generar_token_reset(sup)
        db.session.commit()

    page.goto(f"{live_server}/auth/restablecer-password/{raw_token}")
    page.wait_for_load_state("networkidle")
    page.locator('input[name="password"]').fill("sup1234")
    page.locator('input[name="confirmar"]').fill("sup1234")
    page.locator('[type="submit"]').click()
    page.wait_for_url(f"{live_server}/auth/login")

    # 4a — Login como supervisora y selector de unidad en supervision
    _login(page, live_server, sup_email, password="sup1234")

    page.goto(f"{live_server}/planilla/supervision/")
    page.wait_for_load_state("networkidle")

    selector = page.locator('select[aria-label="Unidad"]')
    assert selector.count() == 1, "Falta el selector de unidad en supervision"
    body_1 = page.locator("body").inner_text()
    assert "GARCIA, ANA" in body_1, f"No se ve GARCIA en UCI: {body_1[:300]}"
    assert "LOPEZ, CRIS" not in body_1

    selector.select_option(label=urgencias)
    page.wait_for_load_state("networkidle")
    body_2 = page.locator("body").inner_text()
    assert "LOPEZ, CRIS" in body_2, f"No se ve LOPEZ en Urgencias: {body_2[:300]}"
    assert "GARCIA, ANA" not in body_2

    # 4b — Selector de unidad en /planilla/importar/
    page.goto(f"{live_server}/planilla/importar/")
    page.wait_for_load_state("networkidle")

    selector_imp = page.locator('select[aria-label="Unidad"]')
    assert selector_imp.count() == 1, "Falta el selector de unidad en importar"
    body_3 = page.locator("body").inner_text()
    assert "GARCIA, ANA" in body_3
    assert "LOPEZ, CRIS" not in body_3

    selector_imp.select_option(label=urgencias)
    page.wait_for_load_state("networkidle")
    body_4 = page.locator("body").inner_text()
    assert "LOPEZ, CRIS" in body_4
    assert "GARCIA, ANA" not in body_4
