import json
import os

from flask import Blueprint, Response, current_app

bp = Blueprint("pwa", __name__)


@bp.get("/manifest.json")
def manifest():
    is_staging = os.environ.get("RAILWAY_ENVIRONMENT_NAME") == "staging"
    name       = "Turnero (staging)" if is_staging else "Turnero"
    short_name = "Turnero ST"        if is_staging else "Turnero"
    data = {
        "name": name,
        "short_name": short_name,
        "description": "Intercambio de turnos para personal sanitario",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#2563eb",
        "lang": "es",
        "prefer_related_applications": False,
        "icons": [
            # "any maskable" en una sola entrada evita duplicados que rompen Chrome antiguo en Android 5/6/7
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ],
    }
    resp = Response(json.dumps(data), content_type="application/manifest+json")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@bp.get("/sw.js")
def service_worker():
    response = current_app.make_response(
        current_app.send_static_file("sw.js")
    )
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Content-Type"] = "application/javascript"
    return response
