"""E2E: modal de "Modificar turno" en /planilla/supervision.

El modo (modificar vs. añadir turno extra / doblaje) debe elegirse ANTES
de elegir el turno concreto, porque condiciona qué opciones tienen
sentido (con "añadir turno extra" no caben los estados especiales como
Libre o Vacaciones, solo turnos). Un checkbox que solo aparece después de
elegir un turno no es evidente para la supervisora.
"""
from datetime import date, time

import pytest

from app.extensions import db
from app.models import Categoria, FranjaHoraria, GrupoIntercambio, Hospital, Unidad, Usuario
from app.services.planilla import añadir_turno


@pytest.fixture
def escenario_supervision(e2e_app, clean_e2e_db):
    with e2e_app.app_context():
        hospital = Hospital(nombre="H-e2e-sup")
        grupo = GrupoIntercambio()
        db.session.add_all([hospital, grupo])
        db.session.commit()

        unidad = Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo)
        categoria = Categoria(nombre="Cat-e2e-sup")
        franja_m = FranjaHoraria(
            nombre="Mañana", hora_inicio=time(8, 0), hora_fin=time(15, 0), grupo_intercambio=grupo
        )
        franja_t = FranjaHoraria(
            nombre="Tarde", hora_inicio=time(15, 0), hora_fin=time(22, 0), grupo_intercambio=grupo
        )
        db.session.add_all([unidad, categoria, franja_m, franja_t])
        db.session.commit()

        supervisora = Usuario(
            nombre="Supervisora", email="sup@e2e-sup.es", unidad=unidad,
            categoria=categoria, es_supervisora=True, onboarding_visto=True,
        )
        supervisora.set_password("pass1234")
        trabajador = Usuario(
            nombre="Trabajador", email="trab@e2e-sup.es", unidad=unidad, categoria=categoria,
            onboarding_visto=True,
        )
        trabajador.set_password("pass1234")
        db.session.add_all([supervisora, trabajador])
        db.session.commit()

        hoy = date.today()
        añadir_turno(trabajador, hoy, franja_m.id)

        return {
            "supervisora_email": "sup@e2e-sup.es",
            "trabajador_id": trabajador.id,
            "franja_m_nombre": franja_m.nombre,
            "franja_t_id": franja_t.id,
            "franja_t_nombre": franja_t.nombre,
            "hoy": hoy,
        }


def _login_supervisora(page, live_server, email):
    page.goto(f"{live_server}/auth/login")
    page.locator('input[name="email"]').fill(email)
    page.locator('input[name="password"]').fill("pass1234")
    page.locator('[type="submit"]').click()
    page.wait_for_url(f"{live_server}/calendario/")


def _abrir_modal_dia(page, live_server, escenario):
    page.goto(f"{live_server}/planilla/supervision/")
    boton = page.locator(
        f'.supervision-celda-btn[data-usuario-id="{escenario["trabajador_id"]}"]'
        f'[data-fecha="{escenario["hoy"].isoformat()}"]'
    )
    boton.click()
    return page.locator("#sup-ajuste-modal")


def test_modo_se_elige_antes_que_el_turno(page, live_server, escenario_supervision):
    _login_supervisora(page, live_server, escenario_supervision["supervisora_email"])
    modal = _abrir_modal_dia(page, live_server, escenario_supervision)

    modo = modal.locator(".sup-ajuste-modo")
    seleccion = modal.locator("#sup-ajuste-seleccion")
    assert modo.locator('input[name="modo"]').count() == 2
    assert modo.locator('input[value="sustituir"]').is_checked()

    modo_y = modo.bounding_box()["y"]
    seleccion_y = seleccion.bounding_box()["y"]
    assert modo_y < seleccion_y, "el modo debe aparecer antes que el desplegable de turno"


def test_modo_anadir_deshabilita_estados_especiales(page, live_server, escenario_supervision):
    _login_supervisora(page, live_server, escenario_supervision["supervisora_email"])
    modal = _abrir_modal_dia(page, live_server, escenario_supervision)

    modal.locator('input[name="modo"][value="anadir"]').check()

    assert modal.locator('option[value="vaciar"]').is_disabled()
    assert modal.locator('option[value="libre"]').is_disabled()


def test_anadir_turno_extra_sin_perder_el_existente(page, live_server, escenario_supervision):
    _login_supervisora(page, live_server, escenario_supervision["supervisora_email"])
    modal = _abrir_modal_dia(page, live_server, escenario_supervision)

    modal.locator('input[name="modo"][value="anadir"]').check()
    modal.locator("#sup-ajuste-seleccion").select_option(str(escenario_supervision["franja_t_id"]))
    modal.locator('button[type="submit"]').click()

    page.wait_for_load_state("networkidle")
    celda = page.locator(
        f'.supervision-celda-btn[data-usuario-id="{escenario_supervision["trabajador_id"]}"]'
        f'[data-fecha="{escenario_supervision["hoy"].isoformat()}"]'
    )
    texto = celda.inner_text()
    assert escenario_supervision["franja_m_nombre"] in texto
    assert escenario_supervision["franja_t_nombre"] in texto
