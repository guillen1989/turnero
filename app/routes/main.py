from flask import Blueprint, jsonify, render_template
from flask_login import login_required

bp = Blueprint("main", __name__)


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@bp.get("/")
def index():
    return render_template("main/index.html")
