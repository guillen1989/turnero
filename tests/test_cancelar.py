"""Tests de integración para cancelar una publicación propia (Fase 3, paso 3)."""
from datetime import date, time

from app.models import (
    Categoria,
    FranjaHoraria,
    PublicacionCambio,
    TurnoCedido,
    TurnoAceptado,
    insertar_categorias_semilla,
)
from app.services.registro import registrar_usuario


def _usuario_y_login(client, nombre="Test User", email="test@test.es"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    usuario = registrar_usuario(nombre, email, "password123", "Hospital T", "Urgencias", cat.id)
    client.post("/auth/login", data={"email": email, "password": "password123"})
    return usuario


def _franja(db, grupo_id):
    franja = FranjaHoraria(
        nombre="Mañana",
        hora_inicio=time(7, 0),
        hora_fin=time(15, 0),
        grupo_intercambio_id=grupo_id,
    )
    db.session.add(franja)
    db.session.commit()
    return franja


def _publicacion(db, usuario, franja):
    pub = PublicacionCambio(usuario_id=usuario.id)
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id))
    db.session.commit()
    return pub


# --- Acceso ---

def test_cancelar_requiere_login(client, db):
    resp = client.post("/publicaciones/1/cancelar", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_cancelar_publicacion_inexistente_devuelve_404(client, db):
    _usuario_y_login(client)
    resp = client.post("/publicaciones/9999/cancelar")
    assert resp.status_code == 404


# --- Lógica de negocio ---

def test_cancelar_publicacion_propia_cambia_estado(client, db):
    usuario = _usuario_y_login(client)
    franja = _franja(db, usuario.unidad.grupo_intercambio_id)
    pub = _publicacion(db, usuario, franja)
    client.post(f"/publicaciones/{pub.id}/cancelar")
    db.session.refresh(pub)
    assert pub.estado == "cancelada"


def test_cancelar_redirige_al_dashboard(client, db):
    usuario = _usuario_y_login(client)
    franja = _franja(db, usuario.unidad.grupo_intercambio_id)
    pub = _publicacion(db, usuario, franja)
    resp = client.post(f"/publicaciones/{pub.id}/cancelar", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")


def test_cancelar_publicacion_ajena_devuelve_403(client, db):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    propietario = registrar_usuario("Propietario", "owner@test.es", "password123", "Hospital T", "Urgencias", cat.id)
    franja = _franja(db, propietario.unidad.grupo_intercambio_id)
    pub = _publicacion(db, propietario, franja)

    _usuario_y_login(client, nombre="Intruso", email="intruso@test.es")
    resp = client.post(f"/publicaciones/{pub.id}/cancelar")
    assert resp.status_code == 403


def test_cancelar_publicacion_ya_cancelada_devuelve_409(client, db):
    usuario = _usuario_y_login(client)
    franja = _franja(db, usuario.unidad.grupo_intercambio_id)
    pub = _publicacion(db, usuario, franja)
    pub.estado = "cancelada"
    db.session.commit()
    resp = client.post(f"/publicaciones/{pub.id}/cancelar")
    assert resp.status_code == 409
