"""Tests de integración: base.html incluye las piezas PWA (Fase 8, paso 2)."""
from app.models import Categoria, insertar_categorias_semilla
from app.services.registro import registrar_usuario


def _login(client, db):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    registrar_usuario("Ana", "ana@test.es", "password123", "H1", "Urgencias", cat.id)
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})


def test_base_incluye_link_manifest(client, db):
    resp = client.get("/")
    assert b'rel="manifest"' in resp.data
    assert b"/manifest.json" in resp.data


def test_base_incluye_meta_theme_color(client, db):
    resp = client.get("/")
    assert b'name="theme-color"' in resp.data


def test_base_registra_service_worker(client, db):
    _login(client, db)
    resp = client.get("/")
    assert b"serviceWorker" in resp.data
    assert b"/sw.js" in resp.data


def test_base_incluye_script_suscripcion_push(client, db):
    """El dashboard de usuario autenticado contiene el código de suscripción push."""
    _login(client, db)
    resp = client.get("/")
    assert b"pushManager" in resp.data
    assert b"/push/vapid-public-key" in resp.data
