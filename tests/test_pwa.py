"""Tests de las rutas PWA: manifest, service worker y clave VAPID pública (Fase 8, paso 1)."""
import json


def test_manifest_json_disponible(client, db):
    resp = client.get("/manifest.json")
    assert resp.status_code == 200
    assert "manifest+json" in resp.content_type


def test_manifest_contiene_campos_requeridos(client, db):
    data = json.loads(client.get("/manifest.json").data)
    assert data["name"] == "Turnero"
    assert data["short_name"] == "Turnero"
    assert data["start_url"] == "/"
    assert data["display"] == "standalone"


def test_manifest_scope_y_prefer_related(client, db):
    """scope y prefer_related_applications son necesarios para compatibilidad con Android antiguo."""
    data = json.loads(client.get("/manifest.json").data)
    assert data.get("scope") == "/"
    assert data.get("prefer_related_applications") is False


def test_manifest_iconos_sin_duplicados(client, db):
    """Iconos duplicados (mismo src+size, purpose distinto) rompen Chrome < 79 en Android 5/6/7."""
    data = json.loads(client.get("/manifest.json").data)
    vistos = set()
    for icono in data["icons"]:
        clave = (icono["src"], icono["sizes"])
        assert clave not in vistos, f"Icono duplicado en el manifest: {clave}"
        vistos.add(clave)


def test_manifest_iconos_purpose_valido(client, db):
    """Cada icono debe declarar purpose; los valores válidos son 'any', 'maskable' o 'any maskable'."""
    valores_validos = {"any", "maskable", "any maskable"}
    data = json.loads(client.get("/manifest.json").data)
    for icono in data["icons"]:
        purpose = icono.get("purpose", "")
        assert purpose in valores_validos, f"purpose inválido en icono {icono['src']}: '{purpose}'"


def test_manifest_iconos_minimos(client, db):
    """Chrome en Android requiere al menos un icono de 192 px y uno de 512 px con purpose 'any'."""
    data = json.loads(client.get("/manifest.json").data)
    purposes_any = {
        icono["sizes"]
        for icono in data["icons"]
        if "any" in icono.get("purpose", "")
    }
    assert "192x192" in purposes_any, "Falta icono 192x192 con purpose 'any'"
    assert "512x512" in purposes_any, "Falta icono 512x512 con purpose 'any'"


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
