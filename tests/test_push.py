"""Tests del sistema de notificaciones push Web Push (Fase 7, paso 1)."""
import json
from unittest.mock import patch

from app.extensions import db
from app.models import Categoria, insertar_categorias_semilla
from app.services.registro import registrar_usuario
from app.push.sender import enviar_push

SUBSCRIPTION = {
    "endpoint": "https://push.example.com/abc123",
    "keys": {"p256dh": "FAKE_P256DH", "auth": "FAKE_AUTH"},
}


def _usuario(email="test@test.es"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario("Test", email, "password123", "H1", "Urgencias", cat.id)


# --- Endpoint de suscripción ---

def test_suscribir_requiere_login(client, db):
    resp = client.post("/push/suscribir", json=SUBSCRIPTION, follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_suscribir_guarda_subscription_en_usuario(client, db):
    usuario = _usuario()
    client.post("/auth/login", data={"email": "test@test.es", "password": "password123"})

    resp = client.post("/push/suscribir", json=SUBSCRIPTION)

    assert resp.status_code == 201
    db.session.refresh(usuario)
    guardado = json.loads(usuario.push_subscription)
    assert guardado["endpoint"] == SUBSCRIPTION["endpoint"]


def test_suscribir_sin_json_devuelve_400(client, db):
    _usuario()
    client.post("/auth/login", data={"email": "test@test.es", "password": "password123"})
    resp = client.post("/push/suscribir", data="no-json", content_type="text/plain")
    assert resp.status_code == 400


# --- Función enviar_push ---

def test_no_envia_si_usuario_sin_suscripcion(app, db):
    usuario = _usuario()
    with patch("app.push.sender.webpush") as mock_wp:
        enviar_push(usuario, "Título", "Cuerpo")
        mock_wp.assert_not_called()


def test_no_envia_si_vapid_key_no_configurada(app, db):
    usuario = _usuario()
    usuario.push_subscription = json.dumps(SUBSCRIPTION)
    db.session.commit()

    old_key = app.config.get("VAPID_PRIVATE_KEY")
    app.config["VAPID_PRIVATE_KEY"] = ""
    try:
        with patch("app.push.sender.webpush") as mock_wp:
            enviar_push(usuario, "Título", "Cuerpo")
            mock_wp.assert_not_called()
    finally:
        app.config["VAPID_PRIVATE_KEY"] = old_key


def test_envia_cuando_hay_suscripcion_y_vapid(app, db):
    usuario = _usuario()
    usuario.push_subscription = json.dumps(SUBSCRIPTION)
    db.session.commit()

    old_key = app.config.get("VAPID_PRIVATE_KEY")
    old_email = app.config.get("VAPID_CLAIM_EMAIL")
    app.config["VAPID_PRIVATE_KEY"] = "fake-key"
    app.config["VAPID_CLAIM_EMAIL"] = "admin@test.es"
    try:
        with patch("app.push.sender.webpush") as mock_wp:
            enviar_push(usuario, "Nuevo match", "Hay un cambio disponible")
            mock_wp.assert_called_once()
            data_arg = mock_wp.call_args.kwargs.get("data") or mock_wp.call_args.args[1]
            payload = json.loads(data_arg)
            assert payload["title"] == "Nuevo match"
            assert payload["body"] == "Hay un cambio disponible"
    finally:
        app.config["VAPID_PRIVATE_KEY"] = old_key
        app.config["VAPID_CLAIM_EMAIL"] = old_email


def test_ignora_excepcion_webpush(app, db):
    """Si webpush lanza WebPushException, enviar_push no propaga el error."""
    from pywebpush import WebPushException

    usuario = _usuario()
    usuario.push_subscription = json.dumps(SUBSCRIPTION)
    db.session.commit()

    old_key = app.config.get("VAPID_PRIVATE_KEY")
    old_email = app.config.get("VAPID_CLAIM_EMAIL")
    app.config["VAPID_PRIVATE_KEY"] = "fake-key"
    app.config["VAPID_CLAIM_EMAIL"] = "admin@test.es"
    try:
        with patch("app.push.sender.webpush", side_effect=WebPushException("fallo")):
            enviar_push(usuario, "Título", "Cuerpo")  # no debe lanzar
    finally:
        app.config["VAPID_PRIVATE_KEY"] = old_key
        app.config["VAPID_CLAIM_EMAIL"] = old_email


# --- URL de destino según tipo de notificación ---

def _usuario_con_sub(db):
    insertar_categorias_semilla()
    from app.models import Categoria
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    u = registrar_usuario("Test", "push_url@test.es", "pass", "H", "U", cat.id)
    u.push_subscription = json.dumps(SUBSCRIPTION)
    db.session.commit()
    return u


def _payload_enviado(mock_wp):
    data_arg = mock_wp.call_args.kwargs.get("data") or mock_wp.call_args.args[1]
    return json.loads(data_arg)


def _setup_vapid(app):
    app.config["VAPID_PRIVATE_KEY"] = "fake-key"
    app.config["VAPID_CLAIM_EMAIL"] = "admin@test.es"


def _teardown_vapid(app, old_key, old_email):
    app.config["VAPID_PRIVATE_KEY"] = old_key
    app.config["VAPID_CLAIM_EMAIL"] = old_email


def test_push_match_incluye_url_compatibles(app, db):
    from app.push.sender import enviar_push_condicional
    u = _usuario_con_sub(db)
    old_key, old_email = app.config.get("VAPID_PRIVATE_KEY"), app.config.get("VAPID_CLAIM_EMAIL")
    _setup_vapid(app)
    try:
        with patch("app.push.sender.webpush") as mock_wp:
            enviar_push_condicional(u, "match", "Nuevo match", "Tienes un cambio compatible.")
            payload = _payload_enviado(mock_wp)
            assert payload["url"] == "/?estado=compatible"
    finally:
        _teardown_vapid(app, old_key, old_email)


def test_push_confirmacion_parcial_incluye_url_pendiente(app, db):
    from app.push.sender import enviar_push_condicional
    u = _usuario_con_sub(db)
    old_key, old_email = app.config.get("VAPID_PRIVATE_KEY"), app.config.get("VAPID_CLAIM_EMAIL")
    _setup_vapid(app)
    try:
        with patch("app.push.sender.webpush") as mock_wp:
            enviar_push_condicional(u, "confirmacion_parcial", "Pendiente", "La otra parte confirmó.")
            payload = _payload_enviado(mock_wp)
            assert payload["url"] == "/?estado=pendiente"
    finally:
        _teardown_vapid(app, old_key, old_email)


def test_push_confirmado_total_incluye_url_confirmados(app, db):
    from app.push.sender import enviar_push_condicional
    u = _usuario_con_sub(db)
    old_key, old_email = app.config.get("VAPID_PRIVATE_KEY"), app.config.get("VAPID_CLAIM_EMAIL")
    _setup_vapid(app)
    try:
        with patch("app.push.sender.webpush") as mock_wp:
            enviar_push_condicional(u, "confirmado_total", "Confirmado", "Cambio cerrado.")
            payload = _payload_enviado(mock_wp)
            assert payload["url"] == "/?estado=confirmada"
    finally:
        _teardown_vapid(app, old_key, old_email)
