import os
from dotenv import load_dotenv
from sqlalchemy.pool import NullPool

load_dotenv()


def _fix_db_url(url):
    # Railway devuelve postgres:// pero SQLAlchemy 2.x requiere postgresql://
    if url and url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-inseguro")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    BABEL_DEFAULT_LOCALE = "es"
    BABEL_DEFAULT_TIMEZONE = "Europe/Madrid"
    # Login persistente ("recuérdame" siempre activo, como una app): la cookie
    # de sesión sobrevive al cierre del navegador/PWA gracias a la cookie
    # "remember me" de Flask-Login (dura 365 días por defecto). La única forma
    # de cerrar sesión es la acción explícita del usuario (auth.logout).
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SAMESITE = "Lax"
    VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
    VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
    VAPID_CLAIM_EMAIL = os.environ.get("VAPID_CLAIM_EMAIL", "")
    # Envío de email transaccional vía Resend (HTTPS API, no SMTP: Railway
    # bloquea los puertos SMTP salientes en el plan Hobby).
    RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
    RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "noreply@turnero.xyz")
    # Dominio propio para los enlaces incluidos en emails (p. ej. https://app.turnero.xyz).
    # Si no está configurada, se usa el host de la petición entrante (comportamiento
    # anterior). Necesaria porque algunos filtros de correo corporativos bloquean o
    # rebotan enlaces al dominio compartido *.up.railway.app.
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "")
    # Botón "Entrar con cuenta demo" en el login: solo aparece si están configuradas
    # (p. ej. en staging, con el usuario creado por scripts/seed_staging.py).
    DEMO_LOGIN_EMAIL = os.environ.get("DEMO_LOGIN_EMAIL", "")
    DEMO_LOGIN_PASSWORD = os.environ.get("DEMO_LOGIN_PASSWORD", "")


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql:///turnero"
    )


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL", "postgresql:///turnero_test"
    )
    WTF_CSRF_ENABLED = False
    # NullPool evita que las conexiones se reutilicen entre tests,
    # previniendo bloqueos por transacciones implícitas abiertas en el pool.
    SQLALCHEMY_ENGINE_OPTIONS = {"poolclass": NullPool}


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = _fix_db_url(os.environ.get("DATABASE_URL"))
    # Railway sirve siempre sobre HTTPS: las cookies de sesión y de
    # "recuérdame" solo deben viajar cifradas.
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    # Railway cierra las conexiones ociosas a Postgres pasado un rato; sin esto
    # el pool reutiliza conexiones muertas y salta "SSL SYSCALL error: EOF detected".
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
