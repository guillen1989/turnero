"""E2E: modal de "Modificar turno" en /planilla/supervision.

Cada turno existente de un día se lista en una fila propia con dos
iconos: "✎" para modificarlo (cambiarlo por otra franja) y "−" para
eliminarlo. Debajo de las filas hay un botón "+ Añadir" para dar de alta
un turno nuevo (o un estado especial) sin tocar los que ya hubiera —
permite doblajes. El icono de papel para registrar un cambio manual no
lleva texto visible, solo el icono.
"""
from datetime import date, time

import pytest

from app.extensions import db
from app.models import (
    Categoria, FranjaHoraria, GrupoIntercambio, Hospital, Unidad, Usuario, UnidadSupervisada,
)
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
        db.session.add(UnidadSupervisada(usuario_id=supervisora.id, unidad_id=unidad.id))
        db.session.commit()

        hoy = date.today()
        añadir_turno(trabajador, hoy, franja_m.id)

        return {
            "supervisora_email": "sup@e2e-sup.es",
            "trabajador_id": trabajador.id,
            "franja_m_id": franja_m.id,
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


def _celda(page, live_server, escenario):
    page.goto(f"{live_server}/planilla/supervision/")
    return page.locator(
        f'.supervision-celda-btn[data-usuario-id="{escenario["trabajador_id"]}"]'
        f'[data-fecha="{escenario["hoy"].isoformat()}"]'
    )


def _abrir_modal_dia(page, live_server, escenario):
    _celda(page, live_server, escenario).click()
    return page.locator("#sup-ajuste-modal")


def test_fila_de_turno_existente_tiene_iconos_editar_y_eliminar(
    page, live_server, escenario_supervision
):
    _login_supervisora(page, live_server, escenario_supervision["supervisora_email"])
    modal = _abrir_modal_dia(page, live_server, escenario_supervision)

    fila = modal.locator(".sup-ajuste-fila").filter(
        has_text=escenario_supervision["franja_m_nombre"]
    )
    assert fila.locator(".sup-ajuste-fila-btn").count() == 2


def test_eliminar_turno_con_el_icono_lo_quita_del_dia(page, live_server, escenario_supervision):
    _login_supervisora(page, live_server, escenario_supervision["supervisora_email"])
    modal = _abrir_modal_dia(page, live_server, escenario_supervision)

    fila = modal.locator(".sup-ajuste-fila").filter(
        has_text=escenario_supervision["franja_m_nombre"]
    )
    fila.locator(".sup-ajuste-fila-btn").last.click()

    page.wait_for_load_state("networkidle")
    celda = _celda(page, live_server, escenario_supervision)
    assert escenario_supervision["franja_m_nombre"] not in celda.inner_text()


def test_editar_turno_con_el_icono_lo_sustituye_por_otra_franja(
    page, live_server, escenario_supervision
):
    _login_supervisora(page, live_server, escenario_supervision["supervisora_email"])
    modal = _abrir_modal_dia(page, live_server, escenario_supervision)

    fila = modal.locator(".sup-ajuste-fila").filter(
        has_text=escenario_supervision["franja_m_nombre"]
    )
    fila.locator(".sup-ajuste-fila-btn").first.click()

    seleccion = modal.locator("#sup-ajuste-seleccion")
    assert seleccion.get_attribute("name") == "franja_nueva_id"
    seleccion.select_option(str(escenario_supervision["franja_t_id"]))
    modal.locator('button[type="submit"]').click()

    page.wait_for_load_state("networkidle")
    celda = _celda(page, live_server, escenario_supervision)
    texto = celda.inner_text()
    assert escenario_supervision["franja_t_nombre"] in texto
    assert escenario_supervision["franja_m_nombre"] not in texto


def test_anadir_turno_extra_sin_perder_el_existente(page, live_server, escenario_supervision):
    _login_supervisora(page, live_server, escenario_supervision["supervisora_email"])
    modal = _abrir_modal_dia(page, live_server, escenario_supervision)

    modal.locator("#sup-ajuste-anadir-btn").click()
    seleccion = modal.locator("#sup-ajuste-seleccion")
    assert seleccion.get_attribute("name") == "seleccion"
    seleccion.select_option(str(escenario_supervision["franja_t_id"]))
    modal.locator('button[type="submit"]').click()

    page.wait_for_load_state("networkidle")
    celda = _celda(page, live_server, escenario_supervision)
    texto = celda.inner_text()
    assert escenario_supervision["franja_m_nombre"] in texto
    assert escenario_supervision["franja_t_nombre"] in texto


def test_icono_de_papel_no_lleva_texto_visible(page, live_server, escenario_supervision):
    _login_supervisora(page, live_server, escenario_supervision["supervisora_email"])
    modal = _abrir_modal_dia(page, live_server, escenario_supervision)

    enlace = modal.locator("#sup-ajuste-registrar-papel")
    assert enlace.inner_text().strip() == "📄"
