import os
from flask import Flask, request
from config import config
from app.extensions import db, migrate, babel, login_manager, csrf


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "default")

    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config[config_name])

    db.init_app(app)
    migrate.init_app(app, db)
    babel.init_app(app, locale_selector=_get_locale)
    csrf.init_app(app)

    # Flask-Babel 4.x no inyecta get_locale en Jinja2 automáticamente
    from flask_babel import get_locale
    app.jinja_env.globals["get_locale"] = get_locale

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"

    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix="/auth")

    from app.routes.publicaciones import bp as publicaciones_bp
    app.register_blueprint(publicaciones_bp)

    from app.routes.matches import bp as matches_bp
    app.register_blueprint(matches_bp)

    # Importar modelos para que SQLAlchemy los registre en los metadatos
    from . import models  # noqa: F401

    return app


def _get_locale():
    from flask_login import current_user
    try:
        if current_user.is_authenticated and hasattr(current_user, "locale"):
            return current_user.locale
    except Exception:
        pass
    return request.accept_languages.best_match(["es", "en"]) or "es"
