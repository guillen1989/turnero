import os
from flask import Flask, request
from config import config
from app.extensions import db, migrate, babel, login_manager, csrf


def _init_sentry():
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
    sentry_sdk.init(
        dsn=dsn,
        integrations=[FlaskIntegration()],
        traces_sample_rate=0.1,
        environment=os.environ.get("FLASK_ENV", "production"),
    )


def create_app(config_name=None):
    _init_sentry()

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

    from app.routes.busquedas import bp as busquedas_bp
    app.register_blueprint(busquedas_bp)

    from app.routes.planilla import bp as planilla_bp
    app.register_blueprint(planilla_bp)

    from app.routes.calendario import bp as calendario_bp
    app.register_blueprint(calendario_bp)

    from app.routes.documento_cambio import bp as documento_cambio_bp
    app.register_blueprint(documento_cambio_bp)

    # Importar modelos para que SQLAlchemy los registre en los metadatos
    from . import models  # noqa: F401

    @app.context_processor
    def _inject_avisos_no_leidos():
        from flask_login import current_user
        try:
            if current_user.is_authenticated:
                from app.models import Notificacion
                count = Notificacion.query.filter(
                    Notificacion.usuario_id == current_user.id,
                    Notificacion.tipo.in_([
                        "nueva_publicacion_seguido",
                        "alerta_busqueda_guardada",
                        "aviso_oportunidad_3",
                        "aviso_oportunidad_4",
                        "contrasena_restablecida",
                        "documento_cambio_pendiente_firma",
                        "documento_cambio_completo",
                    ]),
                    Notificacion.leida.is_(False),
                ).count()
                return {"avisos_no_leidos": count}
        except Exception:
            pass
        return {"avisos_no_leidos": 0}

    _registrar_comandos(app)

    return app


def _registrar_comandos(app):
    import click

    @app.cli.command("rematch")
    @click.option("--dry-run", is_flag=True, help="Muestra qué matches crearía sin guardar nada.")
    def rematch(dry_run):
        """Relanza el motor de matching sobre todas las publicaciones abiertas.

        Útil para recuperar matches perdidos en publicaciones creadas via script
        o anteriores a algún cambio en la lógica de matching.
        """
        from sqlalchemy import select as sa_select
        from app.models import (
            MatchCambio, MatchParticipacion, PublicacionCambio, Unidad, Usuario
        )
        from app.matching.service import (
            buscar_avisos_interes_para,
            buscar_matches_para,
            buscar_sinteticas_que_coinciden_con,
            crear_cadena_3_desde_sintetica,
            crear_match_directo,
            procesar_aviso_y_sintetica,
        )

        def _ya_tienen_match_activo(id_a, id_b):
            match_ids = db.session.execute(
                sa_select(MatchParticipacion.match_id)
                .join(MatchCambio)
                .where(
                    MatchParticipacion.publicacion_id == id_a,
                    MatchCambio.estado.in_(["propuesto", "confirmado_parcial"]),
                )
            ).scalars().all()
            if not match_ids:
                return False
            return db.session.execute(
                sa_select(MatchParticipacion.match_id).where(
                    MatchParticipacion.match_id.in_(match_ids),
                    MatchParticipacion.publicacion_id == id_b,
                )
            ).scalar() is not None

        pubs = (
            PublicacionCambio.query
            .join(Usuario, PublicacionCambio.usuario_id == Usuario.id)
            .join(Unidad, Usuario.unidad_id == Unidad.id)
            .filter(
                PublicacionCambio.estado.in_(("abierta", "parcialmente_resuelta")),
                PublicacionCambio.es_sintetica.is_(False),
            )
            .all()
        )

        n_matches = 0
        n_cadenas = 0
        n_sinteticas = 0
        pares_vistos = set()

        for pub in pubs:
            for candidata in buscar_matches_para(pub):
                par = frozenset({pub.id, candidata.id})
                if par in pares_vistos:
                    continue
                pares_vistos.add(par)
                if not _ya_tienen_match_activo(pub.id, candidata.id):
                    if not dry_run:
                        crear_match_directo(pub, candidata)
                    n_matches += 1

            for sint in buscar_sinteticas_que_coinciden_con(pub):
                if not dry_run:
                    crear_cadena_3_desde_sintetica(pub, sint)
                n_cadenas += 1

            for candidata in buscar_avisos_interes_para(pub):
                par = frozenset({pub.id, candidata.id})
                if par in pares_vistos:
                    continue
                pares_vistos.add(par)
                if not dry_run:
                    procesar_aviso_y_sintetica(pub, candidata)
                n_sinteticas += 1

        prefijo = "[dry-run] " if dry_run else ""
        click.echo(f"{prefijo}Matches directos nuevos:   {n_matches}")
        click.echo(f"{prefijo}Cadenas a 3 cerradas:      {n_cadenas}")
        click.echo(f"{prefijo}Avisos/sintéticas nuevas:  {n_sinteticas}")
        click.echo(f"{prefijo}Publicaciones analizadas:  {len(pubs)}")

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

    @app.cli.command("seed-demo")
    def seed_demo():
        """Siembra la unidad demo si DEMO_ENABLED=true y no está ya completa."""
        import os
        if os.environ.get("DEMO_ENABLED", "").lower() != "true":
            click.echo("DEMO_ENABLED no está activo — omitiendo seed demo.")
            return
        from app.services.demo import reset_demo, DEMO_ACCOUNTS
        from app.models import Usuario, PlanillaMes
        demo_user = Usuario.query.filter_by(email=DEMO_ACCOUNTS[0][1]).first()
        if demo_user:
            tiene_planillas = PlanillaMes.query.filter_by(
                usuario_id=demo_user.id
            ).first() is not None
            if tiene_planillas:
                click.echo("La unidad demo ya existe y tiene planillas — nada que hacer.")
                return
            click.echo("Demo incompleta (sin planillas) — regenerando desde cero…")
        else:
            click.echo("Sembrando unidad demo…")
        reset_demo()
        click.echo("Unidad demo creada/regenerada correctamente.")


def _get_locale():
    from flask_login import current_user
    try:
        if current_user.is_authenticated and hasattr(current_user, "locale"):
            return current_user.locale
    except Exception:
        pass
    return request.accept_languages.best_match(["es", "en"]) or "es"
