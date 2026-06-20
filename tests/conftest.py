import pytest
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
    """Limpia todas las tablas tras cada test para garantizar aislamiento."""
    yield
    _db.session.remove()
    for table in reversed(_db.metadata.sorted_tables):
        _db.session.execute(table.delete())
    _db.session.commit()


@pytest.fixture
def db(app):
    return _db


@pytest.fixture
def client(app):
    return app.test_client()
