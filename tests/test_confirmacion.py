"""Tests de integración para confirmar y rechazar matches (Fase 5)."""
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


# --- Helper: crea dos usuarios con un match propuesto entre ellos ---

def _setup_match(db):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario("Ana", "ana@test.es", "password123", "H1", "Urgencias", cat.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "H1", "Urgencias", cat.id)

    franja = FranjaHoraria(
        nombre="Mañana", hora_inicio=time(7, 0), hora_fin=time(15, 0),
        grupo_intercambio_id=ana.unidad.grupo_intercambio_id,
    )
    db.session.add(franja)
    db.session.flush()

    pub_ana = PublicacionCambio(usuario_id=ana.id)
    db.session.add(pub_ana)
    db.session.flush()
    tc_ana = TurnoCedido(publicacion_id=pub_ana.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id)
    db.session.add(tc_ana)
    db.session.add(TurnoAceptado(publicacion_id=pub_ana.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id))

    pub_pedro = PublicacionCambio(usuario_id=pedro.id)
    db.session.add(pub_pedro)
    db.session.flush()
    tc_pedro = TurnoCedido(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id)
    db.session.add(tc_pedro)
    db.session.add(TurnoAceptado(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id))

    match = MatchCambio(tipo="directo_2", estado="propuesto")
    db.session.add(match)
    db.session.flush()
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_ana.id, turno_cedido_id=tc_ana.id))
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_pedro.id, turno_cedido_id=tc_pedro.id))
    db.session.commit()

    return ana, pedro, match


# --- Acceso ---

def test_confirmar_requiere_login(client, db):
    resp = client.post("/matches/1/confirmar", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_rechazar_requiere_login(client, db):
    resp = client.post("/matches/1/rechazar", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_confirmar_match_no_propio_devuelve_403(client, db):
    ana, pedro, match = _setup_match(db)
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    registrar_usuario("Intruso", "intruso@test.es", "password123", "H1", "Urgencias", cat.id)
    client.post("/auth/login", data={"email": "intruso@test.es", "password": "password123"})
    resp = client.post(f"/matches/{match.id}/confirmar")
    assert resp.status_code == 403


def test_rechazar_match_no_propio_devuelve_403(client, db):
    ana, pedro, match = _setup_match(db)
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    registrar_usuario("Intruso", "intruso@test.es", "password123", "H1", "Urgencias", cat.id)
    client.post("/auth/login", data={"email": "intruso@test.es", "password": "password123"})
    resp = client.post(f"/matches/{match.id}/rechazar")
    assert resp.status_code == 403


# --- Confirmación ---

def test_confirmar_primera_parte_establece_confirmado_parcial(client, db):
    ana, pedro, match = _setup_match(db)
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    client.post(f"/matches/{match.id}/confirmar")
    db.session.refresh(match)
    assert match.estado == "confirmado_parcial"


def test_confirmar_primera_parte_no_resuelve_turno(client, db):
    ana, pedro, match = _setup_match(db)
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    client.post(f"/matches/{match.id}/confirmar")
    part_ana = MatchParticipacion.query.filter_by(match_id=match.id, publicacion_id=match.participaciones[0].publicacion_id).first()
    db.session.refresh(part_ana.turno_cedido)
    assert part_ana.turno_cedido.estado == "abierto"


def test_confirmar_parcial_notifica_a_la_otra_parte(client, db):
    ana, pedro, match = _setup_match(db)
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    client.post(f"/matches/{match.id}/confirmar")
    n = Notificacion.query.filter_by(usuario_id=pedro.id, tipo="confirmacion_parcial").first()
    assert n is not None
    assert n.match_id == match.id


def test_confirmar_ambas_partes_establece_confirmado_total(client, db):
    ana, pedro, match = _setup_match(db)
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    client.post(f"/matches/{match.id}/confirmar")
    client.get("/auth/logout")
    client.post("/auth/login", data={"email": "pedro@test.es", "password": "password123"})
    client.post(f"/matches/{match.id}/confirmar")
    db.session.refresh(match)
    assert match.estado == "confirmado_total"


def test_confirmar_total_resuelve_turnos_cedidos(client, db):
    ana, pedro, match = _setup_match(db)
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    client.post(f"/matches/{match.id}/confirmar")
    client.get("/auth/logout")
    client.post("/auth/login", data={"email": "pedro@test.es", "password": "password123"})
    client.post(f"/matches/{match.id}/confirmar")
    for p in match.participaciones:
        db.session.refresh(p.turno_cedido)
        assert p.turno_cedido.estado == "resuelto"


def test_confirmar_total_actualiza_estado_publicaciones(client, db):
    ana, pedro, match = _setup_match(db)
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    client.post(f"/matches/{match.id}/confirmar")
    client.get("/auth/logout")
    client.post("/auth/login", data={"email": "pedro@test.es", "password": "password123"})
    client.post(f"/matches/{match.id}/confirmar")
    for p in match.participaciones:
        db.session.refresh(p.publicacion)
        assert p.publicacion.estado == "confirmada"


def test_confirmar_match_cerrado_devuelve_409(client, db):
    ana, pedro, match = _setup_match(db)
    match.estado = "rechazado"
    db.session.commit()
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    resp = client.post(f"/matches/{match.id}/confirmar")
    assert resp.status_code == 409


# --- Rechazo ---

def test_rechazar_establece_rechazado(client, db):
    ana, pedro, match = _setup_match(db)
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    client.post(f"/matches/{match.id}/rechazar")
    db.session.refresh(match)
    assert match.estado == "rechazado"


def test_rechazar_notifica_a_la_otra_parte(client, db):
    ana, pedro, match = _setup_match(db)
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    client.post(f"/matches/{match.id}/rechazar")
    n = Notificacion.query.filter_by(usuario_id=pedro.id, tipo="rechazo").first()
    assert n is not None
    assert n.match_id == match.id


def test_rechazar_redirige_al_dashboard(client, db):
    ana, pedro, match = _setup_match(db)
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    resp = client.post(f"/matches/{match.id}/rechazar", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")
