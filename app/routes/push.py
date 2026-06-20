import json

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from app.extensions import db

bp = Blueprint("push", __name__)


@bp.get("/push/vapid-public-key")
def vapid_public_key():
    return jsonify({"publicKey": current_app.config.get("VAPID_PUBLIC_KEY", "")})


@bp.post("/push/suscribir")
@login_required
def suscribir():
    datos = request.get_json(force=True, silent=True)
    if not datos:
        return jsonify({"error": "datos inválidos"}), 400
    current_user.push_subscription = json.dumps(datos)
    db.session.commit()
    return jsonify({"ok": True}), 201
