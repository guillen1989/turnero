"""Tests de la recuperación de contraseña self-service (auth blueprint)."""
from unittest.mock import patch

from app.extensions import db as _db
from app.models import Categoria, PasswordResetToken, insertar_categorias_semilla
from app.services.registro import registrar_usuario
from app.services.password_reset import generar_token_reset


def _usuario(email="victima@test.es"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario("Víctima", email, "pass_original", "H", "U", cat.id)


# --- GET /auth/recuperar-contrasena ---

def test_get_recuperar_contrasena_devuelve_200(client, db):
    resp = client.get("/auth/recuperar-contrasena")
    assert resp.status_code == 200


# --- POST /auth/recuperar-contrasena ---

def test_post_recuperar_contrasena_email_existente_envia_email(client, db):
    _usuario()

    with patch("app.routes.auth.enviar_email", return_value=True) as mock_enviar:
        resp = client.post("/auth/recuperar-contrasena", data={"email": "victima@test.es"},
                            follow_redirects=False)

    assert resp.status_code == 302
    mock_enviar.assert_called_once()
    destinatario = mock_enviar.call_args[0][0]
    assert destinatario == "victima@test.es"
    assert PasswordResetToken.query.count() == 1


def test_post_recuperar_contrasena_email_incluye_enlace_con_token(client, db):
    _usuario()

    with patch("app.routes.auth.enviar_email", return_value=True) as mock_enviar:
        client.post("/auth/recuperar-contrasena", data={"email": "victima@test.es"})

    cuerpo_html = mock_enviar.call_args[0][2]
    assert "/auth/restablecer-contrasena/" in cuerpo_html


def test_post_recuperar_contrasena_email_inexistente_no_envia_ni_filtra(client, db):
    with patch("app.routes.auth.enviar_email") as mock_enviar:
        resp = client.post("/auth/recuperar-contrasena", data={"email": "noexiste@test.es"},
                            follow_redirects=True)

    mock_enviar.assert_not_called()
    # mismo mensaje genérico que si el email sí existiera (anti-enumeración)
    assert "Si ese email está registrado".encode() in resp.data or "enlace".encode() in resp.data


def test_post_recuperar_contrasena_redirige_al_login(client, db):
    _usuario()
    with patch("app.routes.auth.enviar_email", return_value=True):
        resp = client.post("/auth/recuperar-contrasena", data={"email": "victima@test.es"},
                            follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


# --- GET /auth/restablecer-contrasena/<token> ---

def test_get_restablecer_con_token_valido_devuelve_200(client, db):
    usuario = _usuario()
    token = generar_token_reset(usuario)

    resp = client.get(f"/auth/restablecer-contrasena/{token}")
    assert resp.status_code == 200


def test_get_restablecer_con_token_invalido_redirige(client, db):
    resp = client.get("/auth/restablecer-contrasena/token-invalido", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/recuperar-contrasena" in resp.headers["Location"]


# --- POST /auth/restablecer-contrasena/<token> ---

def test_post_restablecer_con_token_valido_cambia_password(client, db):
    usuario = _usuario()
    token = generar_token_reset(usuario)

    resp = client.post(f"/auth/restablecer-contrasena/{token}", data={
        "password": "nueva_password_123",
        "password2": "nueva_password_123",
    }, follow_redirects=False)

    assert resp.status_code == 302
    _db.session.refresh(usuario)
    assert usuario.check_password("nueva_password_123")
    assert not usuario.check_password("pass_original")


def test_post_restablecer_invalida_el_token_tras_usarlo(client, db):
    usuario = _usuario()
    token = generar_token_reset(usuario)
    client.post(f"/auth/restablecer-contrasena/{token}", data={
        "password": "nueva_password_123",
        "password2": "nueva_password_123",
    })

    resp = client.get(f"/auth/restablecer-contrasena/{token}", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/recuperar-contrasena" in resp.headers["Location"]


def test_post_restablecer_con_contrasenas_distintas_no_cambia_password(client, db):
    usuario = _usuario()
    token = generar_token_reset(usuario)

    client.post(f"/auth/restablecer-contrasena/{token}", data={
        "password": "nueva_password_123",
        "password2": "otra_distinta_456",
    })

    _db.session.refresh(usuario)
    assert usuario.check_password("pass_original")


def test_post_restablecer_con_contrasena_corta_no_cambia_password(client, db):
    usuario = _usuario()
    token = generar_token_reset(usuario)

    client.post(f"/auth/restablecer-contrasena/{token}", data={
        "password": "corta",
        "password2": "corta",
    })

    _db.session.refresh(usuario)
    assert usuario.check_password("pass_original")


def test_login_enlaza_a_recuperar_contrasena_de_auth(client, db):
    resp = client.get("/auth/login")
    assert b'href="/auth/recuperar-contrasena"' in resp.data
