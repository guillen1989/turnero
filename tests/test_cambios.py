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


def test_cambios_filtro_usuario_por_nombre(client, db):
    from app.services.registro import registrar_usuario as reg
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    u1 = reg("Ana García", "u1@test.es", "pass123", "H1", "Urgencias", cat.id)
    u2 = reg("Pedro López", "u2@test.es", "pass123", "H1", "Urgencias", cat.id)
    db.session.commit()
    _login(client, u1.email)
    _publicar(u2, date(2026, 9, 1), date(2026, 9, 2))

    resp = client.get("/cambios?usuario=Pedro")
    assert b"01/09/2026" in resp.data

    resp2 = client.get("/cambios?usuario=Ana")
    assert b"01/09/2026" not in resp2.data


def test_cambios_filtro_usuario_insensible_a_mayusculas(client, db):
    from app.services.registro import registrar_usuario as reg
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    u1 = reg("Ana García", "u1@test.es", "pass123", "H1", "Urgencias", cat.id)
    u2 = reg("Pedro López", "u2@test.es", "pass123", "H1", "Urgencias", cat.id)
    db.session.commit()
    _login(client, u1.email)
    _publicar(u2, date(2026, 9, 1), date(2026, 9, 2))

    assert b"01/09/2026" in client.get("/cambios?usuario=pedro").data
    assert b"01/09/2026" in client.get("/cambios?usuario=PEDRO").data
    assert b"01/09/2026" in client.get("/cambios?usuario=pEdRo").data


def test_cambios_filtro_dia_incluye_turno_aceptado(client, db):
    """El filtro por día muestra publicaciones cuyo turno aceptado coincide, no solo el cedido."""
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)
    # u2 quiere librar el día 5, se ofrece a trabajar el día 10
    _publicar(u2, date(2026, 9, 5), date(2026, 9, 10))

    resp = client.get("/cambios?dia=10")
    assert b"05/09/2026" in resp.data


def test_cambios_filtro_mes_incluye_turno_aceptado(client, db):
    """El filtro por mes muestra publicaciones cuyo turno aceptado coincide."""
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)
    # u2 quiere librar en septiembre, se ofrece a trabajar en octubre
    _publicar(u2, date(2026, 9, 5), date(2026, 10, 1))

    resp = client.get("/cambios?mes=10")
    assert b"05/09/2026" in resp.data


def test_cambios_filtro_mes_y_dia_incluye_turno_aceptado(client, db):
    """El filtro combinado mes+día también busca en el turno aceptado."""
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)
    # cedido: 5 sep | aceptado: 1 oct
    _publicar(u2, date(2026, 9, 5), date(2026, 10, 1))

    resp = client.get("/cambios?mes=10&dia=1")
    assert b"05/09/2026" in resp.data


def test_cambios_filtro_tipo_cambio(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)

    pub_cambio = _publicar(u2, date(2026, 9, 1), date(2026, 9, 2))

    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u2.unidad.grupo_intercambio_id
    ).first()
    pub_regalo = PublicacionCambio(usuario_id=u2.id, tipo="regalo")
    db.session.add(pub_regalo)
    db.session.flush()
    db.session.add(TurnoAceptado(publicacion_id=pub_regalo.id, fecha=date(2026, 9, 3), franja_horaria_id=franja.id))
    db.session.commit()

    resp = client.get("/cambios?tipo=cambio")
    assert b"01/09/2026" in resp.data
    assert b"03/09/2026" not in resp.data


def test_cambios_filtro_tipo_regalo(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)

    _publicar(u2, date(2026, 9, 1), date(2026, 9, 2))  # cambio normal

    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u2.unidad.grupo_intercambio_id
    ).first()
    pub_regalo = PublicacionCambio(usuario_id=u2.id, tipo="regalo")
    db.session.add(pub_regalo)
    db.session.flush()
    db.session.add(TurnoAceptado(publicacion_id=pub_regalo.id, fecha=date(2026, 9, 10), franja_horaria_id=franja.id))
    db.session.commit()

    resp = client.get("/cambios?tipo=regalo")
    assert b"10/09/2026" in resp.data
    assert b"01/09/2026" not in resp.data


def test_cambios_sin_filtro_tipo_muestra_todos(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)

    _publicar(u2, date(2026, 9, 1), date(2026, 9, 2))

    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u2.unidad.grupo_intercambio_id
    ).first()
    pub_regalo = PublicacionCambio(usuario_id=u2.id, tipo="regalo")
    db.session.add(pub_regalo)
    db.session.flush()
    db.session.add(TurnoAceptado(publicacion_id=pub_regalo.id, fecha=date(2026, 9, 10), franja_horaria_id=franja.id))
    db.session.commit()

    resp = client.get("/cambios")
    assert b"01/09/2026" in resp.data
    assert b"10/09/2026" in resp.data


def test_cambios_filtro_franja(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)

    grupo_id = u2.unidad.grupo_intercambio_id
    franjas = FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id).order_by(FranjaHoraria.hora_inicio).all()
    assert len(franjas) >= 2, "Se necesitan al menos 2 franjas para este test"
    franja_a, franja_b = franjas[0], franjas[1]

    # Publicación con franja_a como cedido y franja_b como aceptado
    pub = PublicacionCambio(usuario_id=u2.id)
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=date(2026, 9, 1), franja_horaria_id=franja_a.id))
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=date(2026, 9, 2), franja_horaria_id=franja_b.id))
    db.session.commit()

    # La publicación aparece al filtrar por franja_a (está en cedidos)
    resp_a = client.get(f"/cambios?franja={franja_a.id}")
    assert b"01/09/2026" in resp_a.data

    # También aparece al filtrar por franja_b (está en aceptados — incluye regalos)
    resp_b = client.get(f"/cambios?franja={franja_b.id}")
    assert b"02/09/2026" in resp_b.data

    # Una franja que no aparece en ninguna parte no devuelve la publicación
    if len(franjas) >= 3:
        franja_c = franjas[2]
        resp_c = client.get(f"/cambios?franja={franja_c.id}")
        assert b"01/09/2026" not in resp_c.data
