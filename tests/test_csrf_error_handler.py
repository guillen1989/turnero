"""Manejo global de errores CSRF (token caducado o inválido).

El asistente y el resto de formularios de la app pueden quedar abiertos
mucho tiempo (composición de mensajes, PWA en segundo plano en móvil), lo
que supera de sobra el límite por defecto de Flask-WTF (1 hora) y provoca
un 400 "Bad Request" crudo. La app nunca debe romper con un error así:
debe devolver al usuario a un formulario utilizable con un aviso.
"""
import pytest


@pytest.fixture
def csrf_activo(app):
    original = app.config["WTF_CSRF_ENABLED"]
    app.config["WTF_CSRF_ENABLED"] = True
    yield
    app.config["WTF_CSRF_ENABLED"] = original


def test_token_csrf_invalido_no_devuelve_400(client, db, csrf_activo):
    resp = client.post(
        "/auth/login",
        data={"email": "x@test.es", "password": "x", "csrf_token": "token-invalido"},
    )
    assert resp.status_code != 400


def test_token_csrf_invalido_redirige_con_aviso(client, db, csrf_activo):
    resp = client.post(
        "/auth/login",
        data={"email": "x@test.es", "password": "x", "csrf_token": "token-invalido"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"demasiado tiempo" in resp.data.lower()
