"""Tests de integración: crear MatchCambio y Notificaciones al publicar (Fase 4, paso 3)."""
from datetime import date, time

from app.extensions import db
from app.models import (
    Categoria,
    FranjaHoraria,
    MatchCambio,
    MatchParticipacion,
    Notificacion,
    PublicacionCambio,
    TurnoCedido,
    TurnoAceptado,
    insertar_categorias_semilla,
)
from app.services.registro import registrar_usuario


# --- Helpers ---

def _usuario(nombre, email):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario(nombre, email, "password123", "Hospital T", "Urgencias", cat.id)


def _franja(grupo_id, nombre="Mañana"):
    return FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id, nombre=nombre).first()


# --- Tests: creación de MatchCambio tras publicar ---

def test_publicar_crea_match_cuando_hay_coincidencia(client, db):
    """Al publicar y existir coincidencia directa se crea un MatchCambio."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)

    # Pedro publica primero (sin match todavía)
    pub_pedro = PublicacionCambio(usuario_id=pedro.id)
    db.session.add(pub_pedro)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id))
    db.session.commit()

    # Ana publica → debe disparar el matching y crear un MatchCambio
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    client.post("/publicar", data={
        "fecha_cedida_0": "2026-09-01",
        "franja_cedida_0": franja.id,
        "fecha_aceptada_0": "2026-09-02",
        "franja_aceptada_0": franja.id,
    })

    assert MatchCambio.query.count() == 1
    match = MatchCambio.query.first()
    assert match.tipo == "directo_2"
    assert match.estado == "propuesto"


def test_publicar_crea_dos_participaciones(client, db):
    """Un match directo genera exactamente dos MatchParticipacion (una por publicación)."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_pedro = PublicacionCambio(usuario_id=pedro.id)
    db.session.add(pub_pedro)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id))
    db.session.commit()

    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    client.post("/publicar", data={
        "fecha_cedida_0": "2026-09-01",
        "franja_cedida_0": franja.id,
        "fecha_aceptada_0": "2026-09-02",
        "franja_aceptada_0": franja.id,
    })

    assert MatchParticipacion.query.count() == 2


def test_publicar_crea_notificacion_para_cada_usuario(client, db):
    """Cada usuario implicado en el match recibe una notificación de tipo 'nuevo_match'."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_pedro = PublicacionCambio(usuario_id=pedro.id)
    db.session.add(pub_pedro)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id))
    db.session.commit()

    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    client.post("/publicar", data={
        "fecha_cedida_0": "2026-09-01",
        "franja_cedida_0": franja.id,
        "fecha_aceptada_0": "2026-09-02",
        "franja_aceptada_0": franja.id,
    })

    notificaciones = Notificacion.query.filter_by(tipo="nuevo_match").all()
    usuarios_notificados = {n.usuario_id for n in notificaciones}
    assert ana.id in usuarios_notificados
    assert pedro.id in usuarios_notificados


def test_publicar_sin_coincidencia_no_crea_match(client, db):
    """Si no hay coincidencia no se crea ningún MatchCambio."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)
    franja2 = _franja(ana.unidad.grupo_intercambio_id, nombre="Tarde")

    pub_pedro = PublicacionCambio(usuario_id=pedro.id)
    db.session.add(pub_pedro)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 3), franja_horaria_id=franja2.id))
    db.session.add(TurnoAceptado(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id))
    db.session.commit()

    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    client.post("/publicar", data={
        "fecha_cedida_0": "2026-09-01",
        "franja_cedida_0": franja.id,
        "fecha_aceptada_0": "2026-09-02",
        "franja_aceptada_0": franja.id,
    })

    assert MatchCambio.query.count() == 0
