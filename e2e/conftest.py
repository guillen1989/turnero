import threading

import pytest
from sqlalchemy import text
from werkzeug.serving import make_server

from app import create_app
from app.extensions import db as _db
from app.models import Categoria, insertar_categorias_semilla
from app.services.registro import registrar_usuario

E2E_PORT = 5099


@pytest.fixture(scope="session")
def e2e_app():
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture(scope="session")
def live_server(e2e_app):
    server = make_server("127.0.0.1", E2E_PORT, e2e_app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{E2E_PORT}"
    server.shutdown()


@pytest.fixture(autouse=True)
def clean_e2e_db(e2e_app):
    with e2e_app.app_context():
        tablas = ", ".join(f'"{t.name}"' for t in _db.metadata.sorted_tables)
        _db.session.execute(text(f"TRUNCATE {tablas} RESTART IDENTITY CASCADE"))
        _db.session.commit()
    yield


@pytest.fixture
def usuario(e2e_app, clean_e2e_db):
    """Crea un usuario de test en la BD y devuelve sus credenciales."""
    with e2e_app.app_context():
        insertar_categorias_semilla()
        cat = Categoria.query.filter_by(nombre="Enfermería").first()
        registrar_usuario(
            "Ana García", "ana@test.es", "pass1234",
            "Hospital E2E", "Urgencias", cat.id,
        )
    return {"email": "ana@test.es", "password": "pass1234"}


@pytest.fixture
def pagina_autenticada(page, live_server, usuario):
    """Página Playwright ya autenticada con el usuario de test."""
    page.goto(f"{live_server}/auth/login")
    page.locator('input[name="email"]').fill(usuario["email"])
    page.locator('input[name="password"]').fill(usuario["password"])
    page.locator('[type="submit"]').click()
    page.wait_for_url(f"{live_server}/")
    return page
