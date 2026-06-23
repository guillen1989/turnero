import os
from flask import Flask, request
from config import config
from app.extensions import db, migrate, babel, login_manager, csrf, mail


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "default")

    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config[config_name])

    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
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

    from app.routes.push import bp as push_bp
    app.register_blueprint(push_bp)

    from app.routes.pwa import bp as pwa_bp
    app.register_blueprint(pwa_bp)

    from app.routes.admin import bp as admin_bp
    app.register_blueprint(admin_bp)

    from app.routes.feedback import bp as feedback_bp
    app.register_blueprint(feedback_bp)

    from app.routes.notificaciones import bp as notificaciones_bp
    app.register_blueprint(notificaciones_bp)

    from app.routes.unidad import bp as unidad_bp
    app.register_blueprint(unidad_bp)

    # Importar modelos para que SQLAlchemy los registre en los metadatos
    from . import models  # noqa: F401

    @app.context_processor
    def _inject_avisos_no_leidos():
        from flask_login import current_user
        try:
            if current_user.is_authenticated:
                from app.models import Notificacion
                count = Notificacion.query.filter_by(
                    usuario_id=current_user.id,
                    tipo="nueva_publicacion_seguido",
                    leida=False,
                ).count()
                return {"avisos_no_leidos": count}
        except Exception:
            pass
        return {"avisos_no_leidos": 0}

    _registrar_comandos(app)

    return app


def _registrar_comandos(app):
    import click

    @app.cli.command("seed-franjas")
    def seed_franjas():
        """Siembra Mañana/Tarde/Noche en grupos que todavía no tienen franjas."""
        from app.models import GrupoIntercambio
        from app.services.registro import crear_franjas_default

        grupos = GrupoIntercambio.query.all()
        seeded = 0
        for grupo in grupos:
            if grupo.franjas_horarias.count() == 0:
                crear_franjas_default(grupo)
                seeded += 1
        db.session.commit()
        click.echo(f"Franjas sembradas en {seeded} grupo(s).")

    @app.cli.command("init-admin")
    @click.option("--yes", is_flag=True, required=True, help="Confirmación explícita obligatoria.")
    def init_admin(yes):
        """Borra TODOS los datos y crea el usuario administrador inicial."""
        from sqlalchemy import text
        from app.models import insertar_categorias_semilla, Categoria, Usuario
        from app.services.registro import encontrar_o_crear_hospital, encontrar_o_crear_unidad

        # Borrar todo respetando las FK con CASCADE
        db.session.execute(text(
            "TRUNCATE notificacion, match_participacion, match_cambio, "
            "turno_cedido, turno_aceptado, publicacion_cambio, usuario, "
            "franja_horaria, unidad, grupo_intercambio, hospital, categoria "
            "RESTART IDENTITY CASCADE"
        ))
        db.session.commit()
        click.echo("Datos borrados.")

        # Insertar categorías semilla
        insertar_categorias_semilla()

        # Infraestructura mínima para el usuario admin
        hospital = encontrar_o_crear_hospital("Sistema")
        unidad, _ = encontrar_o_crear_unidad("Administración", hospital)
        cat = Categoria(nombre="Administrador")
        db.session.add(cat)
        db.session.flush()

        admin = Usuario(
            nombre="admin",
            email="guillen@delbarrioblanco.net",
            unidad=unidad,
            categoria=cat,
            es_admin=True,
        )
        admin.set_password("relajate")
        db.session.add(admin)
        db.session.commit()
        click.echo("Usuario administrador creado: guillen@delbarrioblanco.net")


def _get_locale():
    from flask_login import current_user
    try:
        if current_user.is_authenticated and hasattr(current_user, "locale"):
            return current_user.locale
    except Exception:
        pass
    return request.accept_languages.best_match(["es", "en"]) or "es"
