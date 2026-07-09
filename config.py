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
    VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
    VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
    VAPID_CLAIM_EMAIL = os.environ.get("VAPID_CLAIM_EMAIL", "")
    # Flask-Mail
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@turnero.app")
    FEEDBACK_RECIPIENT_EMAIL = os.environ.get("FEEDBACK_RECIPIENT_EMAIL", "")
    # Botón "Entrar con cuenta demo" en el login: solo aparece si están configuradas
    # (p. ej. en staging, con el usuario creado por scripts/seed_staging.py).
    DEMO_LOGIN_EMAIL = os.environ.get("DEMO_LOGIN_EMAIL", "")
    DEMO_LOGIN_PASSWORD = os.environ.get("DEMO_LOGIN_PASSWORD", "")


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql:///turnero"
    )
    MAIL_SUPPRESS_SEND = True


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


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
