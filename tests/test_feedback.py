"""Tests para la ruta /feedback (formulario de contacto)."""
from unittest.mock import patch

from app.extensions import db as _db
from app.models import Categoria, Feedback, Usuario, insertar_categorias_semilla
from app.services.registro import registrar_usuario


def _login(client, email="u@test.es", es_admin=False):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    u = registrar_usuario("Test", email, "pass1234", "H", "U", cat.id)
    if es_admin:
        u.es_admin = True
        _db.session.commit()
    client.post("/auth/login", data={"email": email, "password": "pass1234"})
    return u


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

def test_post_feedback_valido_redirige(client, db):
    resp = client.post("/feedback", data={
        "tipo": "error",
        "descripcion": "La app no carga en Safari.",
        "email_contacto": "usuario@test.es",
    }, follow_redirects=False)
    assert resp.status_code == 302


def test_post_feedback_valido_guarda_en_bd(client, db):
    client.post("/feedback", data={
        "tipo": "sugerencia",
        "descripcion": "Añadir filtro por fecha.",
        "email_contacto": "usuario@test.es",
    })
    fb = Feedback.query.first()
    assert fb is not None
    assert fb.tipo == "sugerencia"
    assert fb.descripcion == "Añadir filtro por fecha."
    assert fb.email_contacto == "usuario@test.es"


def test_post_feedback_autenticado_guarda_usuario_id(client, db):
    u = _login(client)
    client.post("/feedback", data={
        "tipo": "error",
        "descripcion": "Error de prueba.",
        "email_contacto": "",
    })
    fb = Feedback.query.first()
    assert fb.usuario_id == u.id


def test_post_feedback_valido_flash_confirmacion(client, db):
    resp = client.post("/feedback", data={
        "tipo": "sugerencia",
        "descripcion": "Añadir filtro por fecha.",
        "email_contacto": "usuario@test.es",
    }, follow_redirects=True)
    assert "Gracias" in resp.data.decode()


# --- POST inválido ---

def test_post_feedback_sin_descripcion_vuelve_al_form(client, db):
    resp = client.post("/feedback", data={
        "tipo": "error",
        "descripcion": "",
        "email_contacto": "usuario@test.es",
    })
    assert resp.status_code == 200
    assert Feedback.query.count() == 0


def test_post_feedback_sin_tipo_vuelve_al_form(client, db):
    resp = client.post("/feedback", data={
        "tipo": "",
        "descripcion": "Descripción válida.",
        "email_contacto": "usuario@test.es",
    })
    assert resp.status_code == 200
    assert Feedback.query.count() == 0


def test_post_feedback_tipo_invalido_vuelve_al_form(client, db):
    resp = client.post("/feedback", data={
        "tipo": "malicioso",
        "descripcion": "Descripción válida.",
        "email_contacto": "",
    })
    assert resp.status_code == 200
    assert Feedback.query.count() == 0


# --- Campo leido ---

def test_nuevo_feedback_tiene_leido_false(client, db):
    """Los mensajes nuevos se crean con leido=False."""
    client.post("/feedback", data={
        "tipo": "error",
        "descripcion": "La app no carga en Safari.",
        "email_contacto": "",
    })
    fb = Feedback.query.first()
    assert fb.leido is False


# --- Envío de email desactivado ---

def test_post_feedback_no_envia_email(client, db):
    """El formulario ya no dispara envío de email (sistema desactivado)."""
    client.application.config["FEEDBACK_RECIPIENT_EMAIL"] = "admin@test.es"
    with patch("app.services.email._enviar_correo") as mock_correo:
        client.post("/feedback", data={
            "tipo": "error",
            "descripcion": "La app no carga en Safari.",
            "email_contacto": "usuario@test.es",
        })
        mock_correo.assert_not_called()


# --- Panel de feedback del admin ---

def _post_feedback(client, tipo="error", descripcion="Descripción de prueba."):
    client.post("/feedback", data={
        "tipo": tipo,
        "descripcion": descripcion,
        "email_contacto": "",
    })
    return Feedback.query.order_by(Feedback.id.desc()).first()


def test_admin_feedback_sin_leer_contiene_nuevos(client, db):
    """El panel admin muestra los mensajes nuevos en la pestaña sin leer."""
    _login(client, email="admin@test.es", es_admin=True)
    _post_feedback(client)
    resp = client.get("/admin/feedback")
    assert resp.status_code == 200
    assert b"sin_leer" in resp.data or "Descripción de prueba.".encode() in resp.data


def test_admin_marcar_leido(client, db):
    """El admin puede marcar un mensaje como leído."""
    _login(client, email="admin@test.es", es_admin=True)
    fb = _post_feedback(client)
    assert fb.leido is False

    resp = client.post(f"/admin/feedback/{fb.id}/marcar-leido", follow_redirects=False)
    assert resp.status_code == 302

    _db.session.refresh(fb)
    assert fb.leido is True


def test_admin_marcar_leido_mueve_a_pestana_leidos(client, db):
    """Un mensaje marcado como leído aparece en la pestaña de leídos."""
    _login(client, email="admin@test.es", es_admin=True)
    fb = _post_feedback(client)
    client.post(f"/admin/feedback/{fb.id}/marcar-leido")

    resp = client.get("/admin/feedback?tab=leidos")
    assert resp.status_code == 200
    assert "Descripción de prueba.".encode() in resp.data


def test_admin_feedback_requiere_admin(client, db):
    """Un usuario normal no puede acceder al panel de feedback."""
    _login(client, email="normal@test.es", es_admin=False)
    resp = client.get("/admin/feedback")
    assert resp.status_code == 403


def test_admin_marcar_leidos_bulk(client, db):
    """El admin puede marcar varios mensajes como leídos a la vez."""
    _login(client, email="admin@test.es", es_admin=True)
    fb1 = _post_feedback(client, descripcion="Mensaje 1")
    fb2 = _post_feedback(client, descripcion="Mensaje 2")
    fb3 = _post_feedback(client, descripcion="Mensaje 3")

    resp = client.post(
        "/admin/feedback/marcar-leidos",
        data={"ids": [fb1.id, fb2.id]},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    _db.session.refresh(fb1)
    _db.session.refresh(fb2)
    _db.session.refresh(fb3)
    assert fb1.leido is True
    assert fb2.leido is True
    assert fb3.leido is False


def test_admin_marcar_leidos_bulk_sin_ids_no_da_error(client, db):
    """Enviar el bulk form sin seleccionar nada no falla."""
    _login(client, email="admin@test.es", es_admin=True)
    resp = client.post("/admin/feedback/marcar-leidos", data={}, follow_redirects=False)
    assert resp.status_code == 302
