"""Tests de integración para el visor de cambios publicados (/cambios)."""
from datetime import date

from app.extensions import db
from app.models import (
    Categoria, FranjaHoraria, PublicacionCambio, TurnoCedido, TurnoAceptado,
    insertar_categorias_semilla,
)
from app.services.registro import registrar_usuario


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _usuario(email="a@test.es", hospital="H1", unidad="Urgencias", cat_nombre="Enfermería"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre=cat_nombre).first()
    u = registrar_usuario("Test", email, "pass123", hospital, unidad, cat.id)
    db.session.commit()
    return u


def _login(client, email, password="pass123"):
    client.post("/auth/login", data={"email": email, "password": password})


def _publicar(usuario, fecha_cede, fecha_acepta):
    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=usuario.unidad.grupo_intercambio_id
    ).first()
    pub = PublicacionCambio(usuario_id=usuario.id)
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=fecha_cede, franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=fecha_acepta, franja_horaria_id=franja.id))
    db.session.commit()
    return pub


# ---------------------------------------------------------------------------
# Acceso
# ---------------------------------------------------------------------------

def test_cambios_requiere_login(client, db):
    resp = client.get("/cambios", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_cambios_accesible_autenticado(client, db):
    u = _usuario()
    _login(client, u.email)
    resp = client.get("/cambios")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Visibilidad
# ---------------------------------------------------------------------------

def test_cambios_no_muestra_publicaciones_propias(client, db):
    u = _usuario()
    _login(client, u.email)
    _publicar(u, date(2026, 9, 1), date(2026, 9, 2))
    resp = client.get("/cambios")
    assert b"Test" not in resp.data or resp.data.count(b"Test") == 1  # solo el nav
    assert PublicacionCambio.query.count() == 1  # hay publicación pero no se muestra


def test_cambios_muestra_publicacion_de_mismo_grupo_y_categoria(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")  # mismo hospital/unidad → mismo grupo
    _login(client, u1.email)
    _publicar(u2, date(2026, 9, 5), date(2026, 9, 6))
    resp = client.get("/cambios")
    assert resp.status_code == 200
    assert b"05/09/2026" in resp.data


def test_cambios_no_muestra_publicacion_de_otra_categoria(client, db):
    u1 = _usuario(email="u1@test.es", cat_nombre="Enfermería")
    u2 = _usuario(email="u2@test.es", cat_nombre="Auxiliar de enfermería (TCAE)")
    _login(client, u1.email)
    _publicar(u2, date(2026, 9, 5), date(2026, 9, 6))
    resp = client.get("/cambios")
    assert b"05/09/2026" not in resp.data


def test_cambios_no_muestra_publicacion_de_otro_grupo(client, db):
    u1 = _usuario(email="u1@test.es", hospital="H1", unidad="Urgencias")
    u2 = _usuario(email="u2@test.es", hospital="H2", unidad="UCI")  # grupo diferente
    _login(client, u1.email)
    _publicar(u2, date(2026, 9, 5), date(2026, 9, 6))
    resp = client.get("/cambios")
    assert b"05/09/2026" not in resp.data


# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------

def test_cambios_filtro_mes(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)
    _publicar(u2, date(2026, 9, 5), date(2026, 9, 6))   # septiembre
    _publicar(u2, date(2026, 10, 5), date(2026, 10, 6))  # octubre

    resp_sep = client.get("/cambios?mes=9")
    assert b"05/09/2026" in resp_sep.data
    assert b"05/10/2026" not in resp_sep.data

    resp_oct = client.get("/cambios?mes=10")
    assert b"05/10/2026" in resp_oct.data
    assert b"05/09/2026" not in resp_oct.data


def test_cambios_filtro_dia(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)
    _publicar(u2, date(2026, 9, 5), date(2026, 9, 6))   # día 5
    _publicar(u2, date(2026, 9, 15), date(2026, 9, 16))  # día 15

    resp = client.get("/cambios?dia=5")
    assert b"05/09/2026" in resp.data
    assert b"15/09/2026" not in resp.data


def test_cambios_filtro_mes_y_dia(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)
    _publicar(u2, date(2026, 9, 5), date(2026, 9, 6))
    _publicar(u2, date(2026, 10, 5), date(2026, 10, 6))

    resp = client.get("/cambios?mes=9&dia=5")
    assert b"05/09/2026" in resp.data
    assert b"05/10/2026" not in resp.data


def test_cambios_sin_filtro_muestra_todas_del_grupo(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)
    _publicar(u2, date(2026, 9, 1), date(2026, 9, 2))
    _publicar(u2, date(2026, 10, 1), date(2026, 10, 2))

    resp = client.get("/cambios")
    assert b"01/09/2026" in resp.data
    assert b"01/10/2026" in resp.data
