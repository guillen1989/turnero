"""Tests de la ruta /calendario (Paso 2): navegación mensual + wiring con
el servicio construir_calendario_mes. Sin drill-down todavía (Paso 4)."""
from datetime import date

from app.extensions import db
from app.models import (
    Categoria,
    FranjaHoraria,
    PublicacionCambio,
    TurnoAceptado,
    TurnoCedido,
    insertar_categorias_semilla,
)
from app.services.registro import registrar_usuario


def _usuario(nombre, email, hospital="H1", unidad="Urgencias"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario(nombre, email, "password123", hospital, unidad, cat.id)


def _login(client, email):
    client.post("/auth/login", data={"email": email, "password": "password123"})


def _franja(grupo_id, nombre="Mañana"):
    return FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id, nombre=nombre).first()


def test_calendario_requiere_login(client, db):
    resp = client.get("/calendario/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_calendario_get_default_devuelve_200(client, db):
    u = _usuario("Ana", "ana@test.es")
    _login(client, u.email)
    resp = client.get("/calendario/")
    assert resp.status_code == 200


def test_calendario_navegacion_mes_siguiente_y_anterior(client, db):
    u = _usuario("Ana", "ana@test.es")
    _login(client, u.email)
    resp = client.get("/calendario/?anyo=2026&mes=7")
    assert resp.status_code == 200
    assert b"anyo=2026&amp;mes=8" in resp.data or b"mes=8" in resp.data
    assert b"mes=6" in resp.data


def test_calendario_modo_invalido_usa_ofertas_por_defecto(client, db):
    u = _usuario("Ana", "ana@test.es")
    _login(client, u.email)
    resp = client.get("/calendario/?modo=noexiste")
    assert resp.status_code == 200
    assert b'data-modo-actual="ofertas"' in resp.data


def test_calendario_modo_ofertas_muestra_franja_del_turno_aceptado(client, db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = ana.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")

    pub = PublicacionCambio(usuario_id=pedro.id, tipo="regalo")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=date(2026, 7, 3), franja_horaria_id=manana.id))
    db.session.commit()

    _login(client, ana.email)
    resp = client.get("/calendario/?anyo=2026&mes=7&modo=ofertas")
    assert resp.status_code == 200
    assert "Mañana".encode("utf-8") in resp.data


def test_calendario_modo_peticiones_muestra_franja_del_turno_cedido(client, db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = ana.unidad.grupo_intercambio_id
    tarde = _franja(gid, "Tarde")

    pub = PublicacionCambio(usuario_id=pedro.id, tipo="peticion")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=date(2026, 7, 5), franja_horaria_id=tarde.id))
    db.session.commit()

    _login(client, ana.email)
    resp = client.get("/calendario/?anyo=2026&mes=7&modo=peticiones")
    assert resp.status_code == 200
    assert "Tarde".encode("utf-8") in resp.data


def test_calendario_no_muestra_publicaciones_de_categoria_distinta(client, db):
    insertar_categorias_semilla()
    cat_enf = Categoria.query.filter_by(nombre="Enfermería").first()
    cat_aux = Categoria.query.filter_by(nombre="Auxiliar de enfermería (TCAE)").first()
    ana = registrar_usuario("Ana", "ana@test.es", "password123", "H1", "Urgencias", cat_enf.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "H1", "Urgencias", cat_aux.id)

    gid = ana.unidad.grupo_intercambio_id
    noche = _franja(gid, "Noche")
    pub = PublicacionCambio(usuario_id=pedro.id, tipo="regalo")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=date(2026, 7, 9), franja_horaria_id=noche.id))
    db.session.commit()

    _login(client, ana.email)
    resp = client.get("/calendario/?anyo=2026&mes=7&modo=ofertas")
    assert resp.status_code == 200
    assert "Noche".encode("utf-8") not in resp.data
