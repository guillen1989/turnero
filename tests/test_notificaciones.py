"""Tests del panel de notificaciones y suscripciones a publicaciones."""
import json
from datetime import date
from unittest.mock import patch

from app.extensions import db
from app.models import Categoria, Notificacion, SuscripcionPublicaciones, insertar_categorias_semilla
from app.push.sender import enviar_push_condicional
from app.services.publicaciones import publicar_cambio
from app.services.registro import registrar_usuario


def _usuario(email="user@test.es", nombre="User"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario(nombre, email, "password123", "H1", "Urgencias", cat.id)


def _usuario2(email="user2@test.es", nombre="User2"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario(nombre, email, "pass456", "H1", "Urgencias", cat.id)


def _login(client, email, password="password123"):
    client.post("/auth/login", data={"email": email, "password": password})


# --- Panel de notificaciones ---

def test_panel_requiere_login(client, db):
    resp = client.get("/notificaciones", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_panel_accesible_para_usuario_autenticado(client, db):
    _usuario()
    _login(client, "user@test.es")
    resp = client.get("/notificaciones")
    assert resp.status_code == 200
    assert "Notificaciones" in resp.data.decode()


def test_panel_muestra_preferencias_actuales(client, db):
    usuario = _usuario()
    usuario.push_activo = True
    usuario.notif_match = False
    db.session.commit()
    _login(client, "user@test.es")
    resp = client.get("/notificaciones")
    html = resp.data.decode()
    assert 'name="push_activo"' in html
    assert 'name="notif_match"' in html


# --- Guardar preferencias ---

def test_guardar_desactiva_push_global(client, db):
    usuario = _usuario()
    usuario.push_activo = True
    db.session.commit()
    _login(client, "user@test.es")
    client.post("/notificaciones/guardar", data={})  # sin push_activo → False
    db.session.refresh(usuario)
    assert usuario.push_activo is False


def test_guardar_activa_preferencias_individuales(client, db):
    usuario = _usuario()
    usuario.push_activo = False
    usuario.notif_match = False
    db.session.commit()
    _login(client, "user@test.es")
    client.post("/notificaciones/guardar", data={
        "push_activo": "on",
        "notif_match": "on",
    })
    db.session.refresh(usuario)
    assert usuario.push_activo is True
    assert usuario.notif_match is True
    assert usuario.notif_confirmacion_parcial is False


# --- Suscripciones ---

def test_suscribir_a_colega(client, db):
    u1 = _usuario()
    u2 = _usuario2()
    _login(client, "user@test.es")
    resp = client.post(f"/notificaciones/suscribir/{u2.id}", follow_redirects=False)
    assert resp.status_code == 302
    suscripcion = SuscripcionPublicaciones.query.filter_by(
        suscriptor_id=u1.id, publicador_id=u2.id
    ).first()
    assert suscripcion is not None


def test_suscribir_duplicado_no_da_error(client, db):
    u1 = _usuario()
    u2 = _usuario2()
    _login(client, "user@test.es")
    client.post(f"/notificaciones/suscribir/{u2.id}")
    resp = client.post(f"/notificaciones/suscribir/{u2.id}")
    assert resp.status_code == 302


def test_cancelar_suscripcion(client, db):
    u1 = _usuario()
    u2 = _usuario2()
    db.session.add(SuscripcionPublicaciones(suscriptor_id=u1.id, publicador_id=u2.id))
    db.session.commit()
    _login(client, "user@test.es")
    client.post(f"/notificaciones/cancelar/{u2.id}")
    suscripcion = SuscripcionPublicaciones.query.filter_by(
        suscriptor_id=u1.id, publicador_id=u2.id
    ).first()
    assert suscripcion is None


def test_no_puede_suscribirse_a_si_mismo(client, db):
    usuario = _usuario()
    _login(client, "user@test.es")
    resp = client.post(f"/notificaciones/suscribir/{usuario.id}", follow_redirects=True)
    assert resp.status_code == 200
    suscripcion = SuscripcionPublicaciones.query.filter_by(
        suscriptor_id=usuario.id, publicador_id=usuario.id
    ).first()
    assert suscripcion is None


# --- enviar_push_condicional ---

SUBSCRIPTION = {
    "endpoint": "https://push.example.com/abc",
    "keys": {"p256dh": "FAKE_P256DH", "auth": "FAKE_AUTH"},
}


def test_push_condicional_no_envia_si_push_inactivo(app, db):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    usuario = registrar_usuario("Test", "t@test.es", "pass", "H1", "UCI", cat.id)
    usuario.push_subscription = json.dumps(SUBSCRIPTION)
    usuario.push_activo = False
    db.session.commit()
    app.config["VAPID_PRIVATE_KEY"] = "fake-key"
    app.config["VAPID_CLAIM_EMAIL"] = "admin@test.es"
    with patch("app.push.sender.webpush") as mock_wp:
        enviar_push_condicional(usuario, "match", "Título", "Cuerpo")
        mock_wp.assert_not_called()


def test_push_condicional_no_envia_si_tipo_desactivado(app, db):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    usuario = registrar_usuario("Test2", "t2@test.es", "pass", "H1", "UCI", cat.id)
    usuario.push_subscription = json.dumps(SUBSCRIPTION)
    usuario.push_activo = True
    usuario.notif_match = False
    db.session.commit()
    app.config["VAPID_PRIVATE_KEY"] = "fake-key"
    app.config["VAPID_CLAIM_EMAIL"] = "admin@test.es"
    with patch("app.push.sender.webpush") as mock_wp:
        enviar_push_condicional(usuario, "match", "Título", "Cuerpo")
        mock_wp.assert_not_called()


# --- Avisos in-app por publicaciones de seguidos ---

def _franja_id(usuario):
    return usuario.unidad.grupo_intercambio.franjas_horarias.first().id


def test_publicar_crea_notificacion_inapp_para_suscriptor(app, db):
    u1 = _usuario()
    u2 = _usuario2()
    db.session.add(SuscripcionPublicaciones(suscriptor_id=u1.id, publicador_id=u2.id))
    db.session.commit()
    franja = _franja_id(u2)
    with patch("app.push.sender.webpush"):
        publicar_cambio(u2.id, [(date(2025, 1, 10), franja)], [(date(2025, 1, 11), franja)])
    notif = Notificacion.query.filter_by(usuario_id=u1.id, tipo="nueva_publicacion_seguido").first()
    assert notif is not None
    assert notif.publicacion_id is not None
    assert notif.leida is False


def test_publicar_no_crea_notificacion_si_sin_suscriptores(app, db):
    u2 = _usuario2()
    franja = _franja_id(u2)
    with patch("app.push.sender.webpush"):
        publicar_cambio(u2.id, [(date(2025, 1, 10), franja)], [(date(2025, 1, 11), franja)])
    notifs = Notificacion.query.filter_by(tipo="nueva_publicacion_seguido").all()
    assert len(notifs) == 0


def test_avisos_no_leidos_aparece_en_nav(client, db):
    u1 = _usuario()
    u2 = _usuario2()
    db.session.add(Notificacion(
        usuario_id=u1.id, publicacion_id=None, tipo="nueva_publicacion_seguido", leida=False
    ))
    db.session.commit()
    _login(client, "user@test.es")
    resp = client.get("/")
    html = resp.data.decode()
    assert "nav-bell--activa" in html
    assert "nav-bell-badge" in html


def test_avisos_panel_marca_notificaciones_leidas(client, db):
    u1 = _usuario()
    u2 = _usuario2()
    db.session.add(Notificacion(
        usuario_id=u1.id, publicacion_id=None, tipo="nueva_publicacion_seguido", leida=False
    ))
    db.session.commit()
    _login(client, "user@test.es")
    client.get("/avisos")
    notif = Notificacion.query.filter_by(usuario_id=u1.id, tipo="nueva_publicacion_seguido").first()
    assert notif.leida is True


def test_avisos_panel_muestra_empty_state_sin_avisos(client, db):
    _usuario()
    _login(client, "user@test.es")
    resp = client.get("/avisos")
    assert resp.status_code == 200
    assert "Avisos" in resp.data.decode()


def test_push_condicional_envia_cuando_activo(app, db):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    usuario = registrar_usuario("Test3", "t3@test.es", "pass", "H1", "UCI", cat.id)
    usuario.push_subscription = json.dumps(SUBSCRIPTION)
    usuario.push_activo = True
    usuario.notif_match = True
    db.session.commit()
    old_key = app.config.get("VAPID_PRIVATE_KEY")
    old_email = app.config.get("VAPID_CLAIM_EMAIL")
    app.config["VAPID_PRIVATE_KEY"] = "fake-key"
    app.config["VAPID_CLAIM_EMAIL"] = "admin@test.es"
    try:
        with patch("app.push.sender.webpush") as mock_wp:
            enviar_push_condicional(usuario, "match", "Título", "Cuerpo")
            mock_wp.assert_called_once()
    finally:
        app.config["VAPID_PRIVATE_KEY"] = old_key
        app.config["VAPID_CLAIM_EMAIL"] = old_email
