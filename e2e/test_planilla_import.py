"""E2E: selector de unidad en /planilla/importar/ para supervisoras multiunidad."""
import pytest

from app.extensions import db
from app.models import Categoria, GrupoIntercambio, Hospital, Unidad, Usuario, UnidadSupervisada
from app.services.planilla_matching import resolver_o_crear_trabajador


def _login_supervisora(page, live_server, email):
    page.goto(f"{live_server}/auth/login")
    page.locator('input[name="email"]').fill(email)
    page.locator('input[name="password"]').fill("pass1234")
    page.locator('[type="submit"]').click()
    page.wait_for_url(f"{live_server}/calendario/")


@pytest.fixture
def escenario_multiunidad(e2e_app, clean_e2e_db):
    with e2e_app.app_context():
        hospital = Hospital(nombre="H-e2e-import")
        grupo = GrupoIntercambio()
        db.session.add_all([hospital, grupo])
        db.session.commit()

        unidad = Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo)
        otra_unidad = Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo)
        categoria = Categoria(nombre="Cat-e2e-import")
        db.session.add_all([unidad, otra_unidad, categoria])
        db.session.commit()

        supervisora = Usuario(
            nombre="Supervisora", email="sup@e2e-import.es", unidad=unidad,
            categoria=categoria, es_supervisora=True, onboarding_visto=True,
        )
        supervisora.set_password("pass1234")
        db.session.add(supervisora)
        db.session.commit()
        db.session.add_all([
            UnidadSupervisada(usuario_id=supervisora.id, unidad_id=unidad.id),
            UnidadSupervisada(usuario_id=supervisora.id, unidad_id=otra_unidad.id),
        ])
        db.session.commit()

        resolver_o_crear_trabajador(unidad, "11111", "GARCIA, ANA")
        resolver_o_crear_trabajador(otra_unidad, "22222", "LOPEZ, CRIS")

        return {
            "supervisora_email": "sup@e2e-import.es",
            "unidad_nombre": unidad.nombre,
            "otra_unidad_nombre": otra_unidad.nombre,
        }


def test_selector_de_unidad_cambia_los_trabajadores_pendientes_mostrados(
    page, live_server, escenario_multiunidad
):
    _login_supervisora(page, live_server, escenario_multiunidad["supervisora_email"])
    page.goto(f"{live_server}/planilla/importar/")

    selector = page.locator('select[aria-label="Unidad"]')
    assert selector.count() == 1
    assert "GARCIA, ANA" in page.locator("body").inner_text()
    assert "LOPEZ, CRIS" not in page.locator("body").inner_text()

    selector.select_option(label=escenario_multiunidad["otra_unidad_nombre"])
    page.wait_for_load_state("networkidle")

    assert "LOPEZ, CRIS" in page.locator("body").inner_text()
    assert "GARCIA, ANA" not in page.locator("body").inner_text()
