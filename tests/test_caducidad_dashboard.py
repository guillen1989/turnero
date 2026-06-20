"""Test de integración: la caducidad se aplica al cargar el dashboard (Fase 6, paso 2)."""
from datetime import date, time
from unittest.mock import patch

from app.extensions import db
from app.models import (
    Categoria,
    FranjaHoraria,
    PublicacionCambio,
    TurnoCedido,
    TurnoAceptado,
    insertar_categorias_semilla,
)
from app.services.registro import registrar_usuario


def _setup(client):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    usuario = registrar_usuario("Ana", "ana@test.es", "password123", "H1", "Urgencias", cat.id)
    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=usuario.unidad.grupo_intercambio_id, nombre="Mañana"
    ).first()

    pub = PublicacionCambio(usuario_id=usuario.id)
    db.session.add(pub)
    db.session.flush()
    # Turno con fecha pasada
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=date(2020, 1, 1), franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=date(2020, 1, 2), franja_horaria_id=franja.id))
    db.session.commit()

    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    return pub


def test_dashboard_caduca_publicaciones_expiradas(client, db):
    """Al visitar el dashboard, las publicaciones con turnos pasados pasan a 'caducada'."""
    pub = _setup(client)
    assert pub.estado == "abierta"

    client.get("/")

    db.session.refresh(pub)
    assert pub.estado == "caducada"
