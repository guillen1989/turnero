"""Tests para app/services/email.py (envío vía Resend HTTPS API)."""
from unittest.mock import patch, Mock

from app.services.email import enviar_email


def _mock_response(status_code=200):
    resp = Mock()
    resp.status_code = status_code
    resp.text = "{}"
    return resp


def test_enviar_email_llama_a_resend_con_los_datos_correctos(app):
    with app.app_context():
        app.config["RESEND_API_KEY"] = "re_test_key"
        app.config["RESEND_FROM_EMAIL"] = "noreply@turnero.app"

        with patch("app.services.email.requests.post", return_value=_mock_response(200)) as mock_post:
            resultado = enviar_email("destino@test.es", "Asunto de prueba", "<p>Cuerpo</p>")

        assert resultado is True
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.resend.com/emails"
        assert kwargs["headers"]["Authorization"] == "Bearer re_test_key"
        assert kwargs["json"]["from"] == "noreply@turnero.app"
        assert kwargs["json"]["to"] == ["destino@test.es"]
        assert kwargs["json"]["subject"] == "Asunto de prueba"
        assert kwargs["json"]["html"] == "<p>Cuerpo</p>"
        assert kwargs["timeout"] <= 10


def test_enviar_email_sin_api_key_no_intenta_conectar(app):
    with app.app_context():
        app.config["RESEND_API_KEY"] = ""

        with patch("app.services.email.requests.post") as mock_post:
            resultado = enviar_email("destino@test.es", "Asunto", "<p>Cuerpo</p>")

        assert resultado is False
        mock_post.assert_not_called()


def test_enviar_email_error_http_devuelve_false_sin_lanzar(app):
    with app.app_context():
        app.config["RESEND_API_KEY"] = "re_test_key"
        app.config["RESEND_FROM_EMAIL"] = "noreply@turnero.app"

        with patch("app.services.email.requests.post", return_value=_mock_response(422)):
            resultado = enviar_email("destino@test.es", "Asunto", "<p>Cuerpo</p>")

        assert resultado is False


def test_enviar_email_excepcion_de_red_devuelve_false_sin_lanzar(app):
    import requests

    with app.app_context():
        app.config["RESEND_API_KEY"] = "re_test_key"
        app.config["RESEND_FROM_EMAIL"] = "noreply@turnero.app"

        with patch("app.services.email.requests.post", side_effect=requests.exceptions.Timeout):
            resultado = enviar_email("destino@test.es", "Asunto", "<p>Cuerpo</p>")

        assert resultado is False
