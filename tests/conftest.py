import pytest
from sqlalchemy import event, text
from app import create_app
from app.extensions import db as _db


@pytest.fixture(scope="session")
def app():
    flask_app = create_app("testing")
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
