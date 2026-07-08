"""Tests para la pantalla introductoria de onboarding."""
from app.extensions import db
from app.models import Categoria, insertar_categorias_semilla
from app.models.usuario import Usuario
from app.services.registro import registrar_usuario


def _usuario(email="u@test.es", onboarding_visto=False):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    u = registrar_usuario("Test", email, "pass123", "H1", "Urgencias", cat.id)
    u.onboarding_visto = onboarding_visto
    db.session.commit()
    return u


def _login(client, email, password="pass123"):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


def test_como_funciona_requiere_login(client, db):
    resp = client.get("/como-funciona", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_como_funciona_accesible_autenticado(client, db):
    u = _usuario(onboarding_visto=True)
    _login(client, u.email)
    resp = client.get("/como-funciona")
    assert resp.status_code == 200
    assert b"como-funciona" in resp.data or b"Turnero" in resp.data


def test_como_funciona_marca_onboarding_visto(client, db):
    u = _usuario()
    assert u.onboarding_visto is False
    _login(client, u.email)

    client.get("/como-funciona")

    db.session.refresh(u)
    assert u.onboarding_visto is True


def test_login_redirige_a_onboarding_si_no_visto(client, db):
    u = _usuario(onboarding_visto=False)
    resp = _login(client, u.email)
    assert resp.status_code == 302
    assert "/como-funciona" in resp.headers["Location"]


def test_login_redirige_a_index_si_ya_visto(client, db):
    u = _usuario(onboarding_visto=True)
    resp = _login(client, u.email)
    assert resp.status_code == 302
    assert "/como-funciona" not in resp.headers["Location"]


def test_login_next_tiene_prioridad_sobre_onboarding(client, db):
    """El parámetro ?next= prevalece aunque no se haya visto el onboarding."""
    u = _usuario(onboarding_visto=False)
    resp = client.post(
        "/auth/login?next=/cambios",
        data={"email": u.email, "password": "pass123"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/cambios" in resp.headers["Location"]


def test_como_funciona_seccion_calendario_aparece_primero(client, db):
    """Ronda 2, Paso 5: la explicación del calendario es la primera sección."""
    u = _usuario(onboarding_visto=True)
    _login(client, u.email)
    resp = client.get("/como-funciona")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert 'id="calendario"' in html
    pos_calendario = html.index("Descubre cambios en el calendario")
    pos_publica = html.index("Publica tu cambio")
    assert pos_calendario < pos_publica
