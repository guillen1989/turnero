import hashlib
from pathlib import Path
from urllib.parse import urlsplit

import psycopg2
import psycopg2.errors
import pytest
from sqlalchemy import event, text
from app import create_app
from app.extensions import db as _db


def _uri_aislada_por_checkout(uri):
    """Deriva una URI con un nombre de BD único por checkout (worktree/clon),
    a partir del path absoluto del proyecto. Sin esto, dos agentes trabajando
    en checkouts distintos del mismo repo pero apuntando al mismo Postgres
    local acaban compartiendo la BD de test: sus TRUNCATE/create_all/drop_all
    concurrentes se pisan entre sí (deadlocks, tablas que desaparecen a
    mitad de test)."""
    sufijo = hashlib.sha1(
        str(Path(__file__).resolve().parent.parent).encode()
    ).hexdigest()[:8]
    partes = urlsplit(uri)
    nombre_bd = f"{partes.path.lstrip('/')}_{sufijo}"
    return f"{partes.scheme}://{partes.netloc}/{nombre_bd}", nombre_bd


def _crear_bd_si_falta(uri, nombre_bd):
    partes = urlsplit(uri)
    uri_mantenimiento = f"{partes.scheme}://{partes.netloc}/postgres"
    conn = psycopg2.connect(uri_mantenimiento)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(f'CREATE DATABASE "{nombre_bd}"')
    except psycopg2.errors.DuplicateDatabase:
        pass
    finally:
        conn.close()


@pytest.fixture(scope="session")
def app():
    flask_app = create_app("testing")
    uri, nombre_bd = _uri_aislada_por_checkout(
        flask_app.config["SQLALCHEMY_DATABASE_URI"]
    )
    _crear_bd_si_falta(uri, nombre_bd)
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = uri
    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.drop_all()


@pytest.fixture(autouse=True)
def clean_db(app):
    """
    Empuja un app context fresco por test. Esto garantiza:
    - g vacío: Flask-Login no hereda current_user de tests anteriores
      (en Flask 3.x, g está scoped al app context, no al request context)
    - Session SQLAlchemy aislada por test (scope key = id del app context)
    - Al salir del with, teardown_appcontext llama a db.session.remove()
      cerrando cualquier conexión abierta, sin deadlocks entre tests.
    Trunca todas las tablas ANTES del cuerpo del test.
    """
    with app.app_context():
        tablas = ", ".join(f'"{t.name}"' for t in _db.metadata.sorted_tables)
        _db.session.execute(text(f"TRUNCATE {tablas} RESTART IDENTITY CASCADE"))
        _db.session.commit()
        yield


@pytest.fixture
def db(app):
    return _db


@pytest.fixture
def client(app):
    return app.test_client()


class QueryCounter:
    """Cuenta las sentencias SELECT ejecutadas mientras está activo, para
    detectar N+1 (nº de queries que crece con el nº de filas procesadas)."""

    def __init__(self):
        self.selects = 0

    def _contar(self, conn, cursor, statement, *args):
        if statement.strip().upper().startswith("SELECT"):
            self.selects += 1


@pytest.fixture
def query_counter(app, db):
    counter = QueryCounter()
    event.listen(db.engine, "after_cursor_execute", counter._contar)
    yield counter
    event.remove(db.engine, "after_cursor_execute", counter._contar)
