"""Tests de las rutas PWA: manifest, service worker y clave VAPID pública (Fase 8, paso 1)."""


def test_manifest_json_disponible(client, db):
    resp = client.get("/manifest.json")
    assert resp.status_code == 200
    assert "manifest+json" in resp.content_type


def test_manifest_contiene_campos_requeridos(client, db):
    import json
    data = json.loads(client.get("/manifest.json").data)
    assert data["name"] == "CambiaTurnos"
    assert data["short_name"] == "CambiaTurnos"
    assert data["start_url"] == "/"
    assert data["display"] == "standalone"


def test_service_worker_disponible(client, db):
    resp = client.get("/sw.js")
    assert resp.status_code == 200
    assert "javascript" in resp.content_type


def test_service_worker_maneja_push_events(client, db):
    """El archivo sw.js debe registrar un listener para el evento 'push'."""
    resp = client.get("/sw.js")
    assert b"push" in resp.data


def test_vapid_public_key_endpoint(client, app, db):
    old = app.config.get("VAPID_PUBLIC_KEY")
    app.config["VAPID_PUBLIC_KEY"] = "clave-publica-vapid-test"
    try:
        resp = client.get("/push/vapid-public-key")
        assert resp.status_code == 200
        assert resp.get_json()["publicKey"] == "clave-publica-vapid-test"
    finally:
        app.config["VAPID_PUBLIC_KEY"] = old
