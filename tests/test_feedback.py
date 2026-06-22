"""Tests para la ruta /feedback (formulario de contacto)."""
from app.models import Categoria, Feedback, insertar_categorias_semilla
from app.services.registro import registrar_usuario


def _login(client, email="u@test.es"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    u = registrar_usuario("Test", email, "pass1234", "H", "U", cat.id)
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
