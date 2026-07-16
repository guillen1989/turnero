"""E2E: firma dibujada al confirmar un match directo (1 a 1).

Ejercita el mecanismo real de captura de la firma (canvas + eventos de
puntero → PNG en base64), algo que un test con el cliente de Flask no
puede comprobar porque no ejecuta JS.
"""
from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models import (
    FranjaHoraria,
    MatchCambio,
    MatchParticipacion,
    PublicacionCambio,
    TurnoCedido,
    Usuario,
)
from app.services.registro import registrar_usuario


@pytest.fixture
def escenario_match_directo(e2e_app, usuario):
    with e2e_app.app_context():
        ana = Usuario.query.filter_by(email=usuario["email"]).first()
        pedro = registrar_usuario(
            "Pedro Ruiz", "pedro@test.es", "pass1234", "Hospital E2E", "Urgencias", ana.categoria_id,
        )

        franja = FranjaHoraria.query.filter_by(
            grupo_intercambio_id=ana.unidad.grupo_intercambio_id, nombre="Mañana"
        ).first()
        fecha_ana = date.today() + timedelta(days=30)
        fecha_pedro = date.today() + timedelta(days=31)

        pub_ana = PublicacionCambio(usuario_id=ana.id)
        db.session.add(pub_ana)
        db.session.flush()
        tc_ana = TurnoCedido(publicacion_id=pub_ana.id, fecha=fecha_ana, franja_horaria_id=franja.id)
        db.session.add(tc_ana)

        pub_pedro = PublicacionCambio(usuario_id=pedro.id)
        db.session.add(pub_pedro)
        db.session.flush()
        tc_pedro = TurnoCedido(publicacion_id=pub_pedro.id, fecha=fecha_pedro, franja_horaria_id=franja.id)
        db.session.add(tc_pedro)

        match = MatchCambio(tipo="directo_2", estado="propuesto")
        db.session.add(match)
        db.session.flush()
        db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_ana.id, turno_cedido_id=tc_ana.id))
        db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_pedro.id, turno_cedido_id=tc_pedro.id))
        db.session.commit()
        match_id = match.id

    return match_id


def _dibujar_trazo(page):
    canvas = page.locator("#firma-canvas")
    box = canvas.bounding_box()
    page.mouse.move(box["x"] + 20, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + 15)
    page.mouse.move(box["x"] + box["width"] - 20, box["y"] + box["height"] / 2)
    page.mouse.up()


def test_confirmar_match_directo_dibujando_firma(pagina_autenticada, live_server, escenario_match_directo):
    page = pagina_autenticada
    page.goto(f"{live_server}/")

    page.locator('.match-acciones button:has-text("Confirmar")').click()
    assert page.locator("#modal-firma").is_visible()

    _dibujar_trazo(page)
    page.locator("#btn-firmar-confirmar").click()

    page.wait_for_url(f"{live_server}/")
    assert "Has confirmado tu parte del cambio" in page.content()


def test_confirmar_sin_dibujar_firma_no_confirma(pagina_autenticada, live_server, escenario_match_directo):
    page = pagina_autenticada
    page.goto(f"{live_server}/")

    page.locator('.match-acciones button:has-text("Confirmar")').click()
    page.locator("#btn-firmar-confirmar").click()

    assert page.locator("#firma-aviso").is_visible()
    assert page.locator("#modal-firma").is_visible()
    assert "Has confirmado tu parte del cambio" not in page.content()
