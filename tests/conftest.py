import hashlib
import os
from pathlib import Path
from urllib.parse import urlsplit

import psycopg2
import psycopg2.errors
import pytest


def _parche_md5():
    def _md5(data=b"", *, usedforsecurity=True):
        return hashlib.md5(data)

    from reportlab.lib import utils
    utils.md5 = _md5

    from reportlab.pdfbase import pdfdoc
    pdfdoc.md5 = _md5


_parche_md5()
from sqlalchemy import event, text
from app import create_app
from app.extensions import db as _db


def _uri_aislada_por_ejecucion(uri):
    """Deriva una URI con un nombre de BD único por proceso de pytest (no solo
    por checkout), a partir del path absoluto del proyecto + el PID.

    Con aislamiento solo por checkout, dos ejecuciones de pytest concurrentes
    sobre el MISMO checkout (p. ej. una en segundo plano y otra en primer
    plano, algo habitual al iterar con un agente) seguían compartiendo la
    misma BD: el TRUNCATE de `clean_db` de una sesión borraba en mitad de
    un test las filas que la otra sesión tenía cargadas, produciendo
    `ObjectDeletedError` y fallos espurios sin relación con el cambio en
    curso. Cada proceso de pytest obtiene ahora su propia BD.
    """
    sufijo_checkout = hashlib.sha1(
        str(Path(__file__).resolve().parent.parent).encode()
    ).hexdigest()[:8]
    partes = urlsplit(uri)
    prefijo_bd = f"{partes.path.lstrip('/')}_{sufijo_checkout}"
    nombre_bd = f"{prefijo_bd}_{os.getpid()}"
    uri_mantenimiento = f"{partes.scheme}://{partes.netloc}/postgres"
    return f"{partes.scheme}://{partes.netloc}/{nombre_bd}", nombre_bd, prefijo_bd, uri_mantenimiento


def _crear_bd_si_falta(uri_mantenimiento, nombre_bd):
    conn = psycopg2.connect(uri_mantenimiento)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(f'CREATE DATABASE "{nombre_bd}"')
    except psycopg2.errors.DuplicateDatabase:
        pass
    finally:
        conn.close()


def _borrar_bd(uri_mantenimiento, nombre_bd):
    conn = psycopg2.connect(uri_mantenimiento)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(f'DROP DATABASE IF EXISTS "{nombre_bd}"')
    except psycopg2.Error:
        pass
    finally:
        conn.close()


def _limpiar_bds_huerfanas(uri_mantenimiento, prefijo_bd, nombre_bd_actual):
    """Borra BDs de test de ejecuciones anteriores de este checkout que
    quedaron huérfanas (proceso de pytest interrumpido antes del teardown,
    p. ej. por timeout o Ctrl+C) y que ya no tienen ninguna conexión activa.
    Evita acumular una BD nueva por cada ejecución, dado que el aislamiento
    ahora es por PID (ver `_uri_aislada_por_ejecucion`)."""
    conn = psycopg2.connect(uri_mantenimiento)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT datname FROM pg_database WHERE datname LIKE %s AND datname != %s",
                (f"{prefijo_bd}\\_%", nombre_bd_actual),
            )
            candidatas = [row[0] for row in cur.fetchall()]
            for nombre in candidatas:
                cur.execute(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = %s",
                    (nombre,),
                )
                if cur.fetchone()[0] == 0:
                    try:
                        cur.execute(f'DROP DATABASE "{nombre}"')
                    except psycopg2.Error:
                        pass
    finally:
        conn.close()


@pytest.fixture(scope="session")
def app():
    from config import TestingConfig

    # Flask-SQLAlchemy lee SQLALCHEMY_DATABASE_URI dentro de db.init_app(),
    # que create_app() ya ha invocado cuando esta función recibe el app
    # devuelto -- reasignar app.config después no tiene ningún efecto sobre
    # el engine ya vinculado. Hay que parchear la URI aislada ANTES de crear
    # la app, sobre la clase de config que create_app() va a leer.
    uri, nombre_bd, prefijo_bd, uri_mantenimiento = _uri_aislada_por_ejecucion(
        TestingConfig.SQLALCHEMY_DATABASE_URI
    )
    _limpiar_bds_huerfanas(uri_mantenimiento, prefijo_bd, nombre_bd)
    _crear_bd_si_falta(uri_mantenimiento, nombre_bd)
    TestingConfig.SQLALCHEMY_DATABASE_URI = uri

    flask_app = create_app("testing")
    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.session.remove()
        _db.engine.dispose()
    _borrar_bd(uri_mantenimiento, nombre_bd)


def _activar_feature_flags_de_test():
    from app.services.feature_flags import crear_flag, activar_global
    for clave in (
        "planilla_supervision_multiunidad",
        "importacion_planilla",
        "hoja_cambio_digital",
        "cambios_encadenados",
        "cambios_a_3",
        "cambios_a_4",
        "multi_unidad",
        "asistente_parser",
        "novedades",
    ):
        try:
            crear_flag(clave)
        except Exception:
            _db.session.rollback()
        try:
            activar_global(clave)
        except Exception:
            _db.session.rollback()


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
        _db.session.remove()
        tablas = ", ".join(f'"{t.name}"' for t in _db.metadata.sorted_tables)
        _db.session.execute(text(f"TRUNCATE {tablas} RESTART IDENTITY CASCADE"))
        _db.session.commit()
        _activar_feature_flags_de_test()
        yield
        _db.session.remove()


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
