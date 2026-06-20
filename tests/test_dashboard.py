"""Tests para el dashboard del usuario autenticado (Fase 3, paso 1)."""
from datetime import date, time

from app.models import (
    Categoria,
    FranjaHoraria,
    MatchCambio,
    MatchParticipacion,
    PublicacionCambio,
    TurnoCedido,
    TurnoAceptado,
    insertar_categorias_semilla,
)
from app.extensions import db
from app.services.registro import registrar_usuario


def _usuario_y_login(client, email="test@test.es"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    usuario = registrar_usuario(
        "Test User", email, "password123", "Hospital T", "Urgencias", cat.id
    )
    client.post("/auth/login", data={"email": email, "password": "password123"})
    return usuario


def _franja(grupo_intercambio_id):
    return FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_intercambio_id, nombre="Mañana").first()


def _publicacion(usuario, franja, fecha_cedida=date(2026, 8, 1), fecha_aceptada=date(2026, 8, 2)):
    pub = PublicacionCambio(usuario_id=usuario.id)
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=fecha_cedida, franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=fecha_aceptada, franja_horaria_id=franja.id))
    db.session.commit()
    return pub


def test_index_no_autenticado_muestra_landing(client, db):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Crear cuenta".encode() in resp.data


def test_index_autenticado_muestra_dashboard(client, db):
    _usuario_y_login(client)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Mis publicaciones".encode() in resp.data


def test_dashboard_sin_publicaciones_muestra_estado_vacio(client, db):
    _usuario_y_login(client)
    resp = client.get("/")
    assert "No tienes publicaciones".encode() in resp.data


def test_dashboard_muestra_publicaciones_propias(client, db):
    usuario = _usuario_y_login(client)
    franja = _franja(usuario.unidad.grupo_intercambio_id)
    _publicacion(usuario, franja)
    resp = client.get("/")
    assert b"2026-08-01" in resp.data


def test_dashboard_muestra_match_propuesto(client, db):
    """Cuando hay un match propuesto, el dashboard lo muestra con botones de acción."""
    ana = _usuario_y_login(client, email="ana@test.es")
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "Hospital T", "Urgencias", cat.id)
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_ana = _publicacion(ana, franja, fecha_cedida=date(2026, 9, 1), fecha_aceptada=date(2026, 9, 2))
    pub_pedro = _publicacion(pedro, franja, fecha_cedida=date(2026, 9, 2), fecha_aceptada=date(2026, 9, 1))

    match = MatchCambio(tipo="directo_2", estado="propuesto")
    db.session.add(match)
    db.session.flush()
    tc_ana = pub_ana.turnos_cedidos[0]
    tc_pedro = pub_pedro.turnos_cedidos[0]
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_ana.id, turno_cedido_id=tc_ana.id))
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_pedro.id, turno_cedido_id=tc_pedro.id))
    db.session.commit()

    resp = client.get("/")
    assert b"Cambios compatibles encontrados" in resp.data
    assert b"Pedro" in resp.data
    assert b"Confirmar" in resp.data
    assert b"Rechazar" in resp.data


def test_dashboard_no_muestra_publicaciones_ajenas(client, db):
    _usuario_y_login(client, email="ana@test.es")
    # Segundo usuario — misma unidad, sin login
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    otro = registrar_usuario("Otro", "otro@test.es", "password123", "Hospital T", "Urgencias", cat.id)
    franja = _franja(otro.unidad.grupo_intercambio_id)
    _publicacion(otro, franja)
    resp = client.get("/")
    assert b"No tienes publicaciones" in resp.data
    assert b"2026-08-01" not in resp.data
