from flask import Blueprint, current_app, jsonify

bp = Blueprint("pwa", __name__)


@bp.get("/manifest.json")
def manifest():
    return jsonify({
        "name": "CambiaTurnos",
        "short_name": "CambiaTurnos",
        "description": "Intercambio de turnos para personal sanitario",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#2563eb",
        "lang": "es",
        "icons": [
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "maskable"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    })


@bp.get("/sw.js")
def service_worker():
    response = current_app.make_response(
        current_app.send_static_file("sw.js")
    )
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Content-Type"] = "application/javascript"
    return response
