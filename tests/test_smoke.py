"""
Smoke tests — verifican que las rutas críticas responden con HTTP 2xx/3xx.
Si alguno falla con 500, una ruta básica está rota.
No verifican comportamiento de negocio; solo que la ruta no explota.
"""
from datetime import date
from unittest.mock import patch

from app.extensions import db
from app.models import (
    Categoria, FranjaHoraria, MatchCambio, MatchParticipacion,
    PublicacionCambio, TurnoCedido, TurnoAceptado,
    insertar_categorias_semilla,
)
from app.services.registro import registrar_usuario


def _setup(email="smoke@test.es"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario("Smoke", email, "pass1234", "H1", "Urgencias", cat.id)


def _login(client, email):
    client.post("/auth/login", data={"email": email, "password": "pass1234"})


def _franja(grupo_id):
    return FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id).first()


def _pub(usuario, fecha_cede=date(2026, 9, 1), fecha_acepta=date(2026, 9, 2)):
    franja = _franja(usuario.unidad.grupo_intercambio_id)
    pub = PublicacionCambio(usuario_id=usuario.id)
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=fecha_cede, franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=fecha_acepta, franja_horaria_id=franja.id))
    db.session.commit()
    return pub


def _match_entre(u1, u2):
    pub_a = _pub(u1, date(2026, 9, 1), date(2026, 9, 2))
    pub_b = _pub(u2, date(2026, 9, 2), date(2026, 9, 1))
    tc_a = TurnoCedido.query.filter_by(publicacion_id=pub_a.id).first()
    tc_b = TurnoCedido.query.filter_by(publicacion_id=pub_b.id).first()
    match = MatchCambio(tipo="directo_2", estado="propuesto")
    db.session.add(match)
    db.session.flush()
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_a.id, turno_cedido_id=tc_a.id))
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_b.id, turno_cedido_id=tc_b.id))
    db.session.commit()
    return match


# ---------------------------------------------------------------------------
# Rutas públicas (sin login)
# ---------------------------------------------------------------------------

def test_smoke_health(client, db):
    assert client.get("/health").status_code == 200


def test_smoke_como_funciona(client, db):
    u = _setup()
    _login(client, u.email)
    assert client.get("/como-funciona").status_code == 200


def test_smoke_login_get(client, db):
    assert client.get("/auth/login").status_code == 200


def test_smoke_registro_get(client, db):
    assert client.get("/auth/registro").status_code == 200


def test_smoke_index_sin_login(client, db):
    assert client.get("/").status_code == 200


# ---------------------------------------------------------------------------
# Rutas autenticadas (GET)
# ---------------------------------------------------------------------------

def test_smoke_dashboard(client, db):
    u = _setup()
    _login(client, u.email)
    assert client.get("/").status_code == 200


def test_smoke_publicar_get(client, db):
    u = _setup()
    _login(client, u.email)
    assert client.get("/publicar").status_code == 200


def test_smoke_cambios_get(client, db):
    u = _setup()
    _login(client, u.email)
    assert client.get("/cambios").status_code == 200


def test_smoke_perfil_get(client, db):
    u = _setup()
    _login(client, u.email)
    assert client.get("/auth/perfil").status_code == 200


def test_smoke_editar_pub_get(client, db):
    u = _setup()
    _login(client, u.email)
    pub = _pub(u)
    assert client.get(f"/publicaciones/{pub.id}/editar").status_code == 200


# ---------------------------------------------------------------------------
# Acciones POST críticas (happy path → 302)
# ---------------------------------------------------------------------------

def test_smoke_publicar_post(client, db):
    u = _setup()
    _login(client, u.email)
    franja = _franja(u.unidad.grupo_intercambio_id)
    resp = client.post("/publicar", data={
        "fecha_cedida_0": "2026-09-01",
        "franja_cedida_0": franja.id,
        "fecha_aceptada_0": "2026-09-02",
        "franja_aceptada_0": franja.id,
    }, follow_redirects=False)
    assert resp.status_code == 302


def test_smoke_eliminar_pub_post(client, db):
    u = _setup()
    _login(client, u.email)
    pub = _pub(u)
    resp = client.post(f"/publicaciones/{pub.id}/eliminar", follow_redirects=False)
    assert resp.status_code == 302


def test_smoke_me_interesa_post(client, db):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    u1 = registrar_usuario("U1", "u1@test.es", "pass1234", "H1", "Urgencias", cat.id)
    u2 = registrar_usuario("U2", "u2@test.es", "pass1234", "H1", "Urgencias", cat.id)
    franja = _franja(u1.unidad.grupo_intercambio_id)
    pub = PublicacionCambio(usuario_id=u1.id, tipo="regalo")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id))
    db.session.commit()
    _login(client, "u2@test.es")
    with patch("app.push.sender.webpush"):
        resp = client.post(f"/cambios/{pub.id}/me-interesa", follow_redirects=False)
    assert resp.status_code == 302


def test_smoke_confirmar_match_post(client, db):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    u1 = registrar_usuario("U1", "u1@test.es", "pass1234", "H1", "Urgencias", cat.id)
    u2 = registrar_usuario("U2", "u2@test.es", "pass1234", "H1", "Urgencias", cat.id)
    match = _match_entre(u1, u2)
    _login(client, "u1@test.es")
    with patch("app.push.sender.webpush"):
        resp = client.post(f"/matches/{match.id}/confirmar", follow_redirects=False)
    assert resp.status_code == 302


def test_smoke_rechazar_match_post(client, db):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    u1 = registrar_usuario("U1", "u1@test.es", "pass1234", "H1", "Urgencias", cat.id)
    u2 = registrar_usuario("U2", "u2@test.es", "pass1234", "H1", "Urgencias", cat.id)
    match = _match_entre(u1, u2)
    _login(client, "u1@test.es")
    with patch("app.push.sender.webpush"):
        resp = client.post(f"/matches/{match.id}/rechazar", follow_redirects=False)
    assert resp.status_code == 302
