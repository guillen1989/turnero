"""Tests para la ruta /feedback (formulario de contacto)."""
from unittest.mock import patch

from app.models import Categoria, insertar_categorias_semilla
from app.services.registro import registrar_usuario


def _login(client, email="u@test.es"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    registrar_usuario("Test", email, "pass1234", "H", "U", cat.id)
    client.post("/auth/login", data={"email": email, "password": "pass1234"})


# --- GET ---

def test_get_feedback_anonimo_devuelve_200(client, db):
    resp = client.get("/feedback")
    assert resp.status_code == 200
    assert b"feedback" in resp.data.lower() or b"error" in resp.data.lower() or b"suger" in resp.data.lower()


def test_get_feedback_prerellena_email_si_autenticado(client, db):
    _login(client)
    resp = client.get("/feedback")
    assert b"u@test.es" in resp.data


# --- POST válido ---

def test_post_feedback_valido_redirige_con_flash(client, db):
    with patch("app.routes.feedback.mail") as mock_mail:
        resp = client.post("/feedback", data={
            "tipo": "error",
            "descripcion": "La app no carga en Safari.",
            "email_contacto": "usuario@test.es",
        }, follow_redirects=False)
    assert resp.status_code == 302
    mock_mail.send.assert_called_once()


def test_post_feedback_valido_flash_confirmacion(client, db):
    with patch("app.routes.feedback.mail") as mock_mail:
        resp = client.post("/feedback", data={
            "tipo": "sugerencia",
            "descripcion": "Añadir filtro por fecha.",
            "email_contacto": "usuario@test.es",
        }, follow_redirects=True)
    assert "Gracias" in resp.data.decode()


# --- POST inválido ---

def test_post_feedback_sin_descripcion_vuelve_al_form(client, db):
    with patch("app.routes.feedback.mail"):
        resp = client.post("/feedback", data={
            "tipo": "error",
            "descripcion": "",
            "email_contacto": "usuario@test.es",
        })
    assert resp.status_code == 200
    assert "/feedback" in resp.request.path


def test_post_feedback_sin_tipo_vuelve_al_form(client, db):
    with patch("app.routes.feedback.mail"):
        resp = client.post("/feedback", data={
            "tipo": "",
            "descripcion": "Descripción válida.",
            "email_contacto": "usuario@test.es",
        })
    assert resp.status_code == 200


# --- Fallo de envío ---

def test_post_feedback_fallo_smtp_muestra_error(client, db):
    with patch("app.routes.feedback.mail") as mock_mail:
        mock_mail.send.side_effect = Exception("SMTP error")
        resp = client.post("/feedback", data={
            "tipo": "error",
            "descripcion": "Descripción válida.",
            "email_contacto": "usuario@test.es",
        }, follow_redirects=True)
    assert "pudo enviar" in resp.data.decode().lower()
