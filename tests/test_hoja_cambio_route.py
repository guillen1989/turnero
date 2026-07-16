"""Tests de la ruta GET /matches/<id>/hoja-cambio.pdf."""
from datetime import date

from app.extensions import db
from app.models import (
    Categoria,
    FranjaHoraria,
    MatchCambio,
    MatchParticipacion,
    PublicacionCambio,
    TurnoCedido,
    insertar_categorias_semilla,
)
from app.services.registro import registrar_usuario

FIRMA_VALIDA = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4"
    "2mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _setup_match(db, estado="propuesto", tipo="directo_2"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario("Ana", "ana@test.es", "password123", "H1", "Urgencias", cat.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "H1", "Urgencias", cat.id)

    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=ana.unidad.grupo_intercambio_id, nombre="Mañana"
    ).first()

    pub_ana = PublicacionCambio(usuario_id=ana.id)
    db.session.add(pub_ana)
    db.session.flush()
    tc_ana = TurnoCedido(publicacion_id=pub_ana.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id)
    db.session.add(tc_ana)

    pub_pedro = PublicacionCambio(usuario_id=pedro.id)
    db.session.add(pub_pedro)
    db.session.flush()
    tc_pedro = TurnoCedido(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id)
    db.session.add(tc_pedro)

    match = MatchCambio(tipo=tipo, estado=estado)
    db.session.add(match)
    db.session.flush()
    db.session.add(MatchParticipacion(
        match_id=match.id, publicacion_id=pub_ana.id, turno_cedido_id=tc_ana.id,
        confirmado=(estado == "confirmado_total"), firma_data=FIRMA_VALIDA if estado == "confirmado_total" else None,
    ))
    db.session.add(MatchParticipacion(
        match_id=match.id, publicacion_id=pub_pedro.id, turno_cedido_id=tc_pedro.id,
        confirmado=(estado == "confirmado_total"), firma_data=FIRMA_VALIDA if estado == "confirmado_total" else None,
    ))
    db.session.commit()

    return ana, pedro, match


def test_hoja_cambio_requiere_login(client, db):
    resp = client.get("/matches/1/hoja-cambio.pdf", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_hoja_cambio_no_participante_devuelve_403(client, db):
    ana, pedro, match = _setup_match(db, estado="confirmado_total")
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    registrar_usuario("Intruso", "intruso@test.es", "password123", "H1", "Urgencias", cat.id)
    client.post("/auth/login", data={"email": "intruso@test.es", "password": "password123"})
    resp = client.get(f"/matches/{match.id}/hoja-cambio.pdf")
    assert resp.status_code == 403


def test_hoja_cambio_match_no_confirmado_total_devuelve_409(client, db):
    ana, pedro, match = _setup_match(db, estado="propuesto")
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    resp = client.get(f"/matches/{match.id}/hoja-cambio.pdf")
    assert resp.status_code == 409


def test_hoja_cambio_cadena_devuelve_409(client, db):
    ana, pedro, match = _setup_match(db, estado="confirmado_total", tipo="cadena_3")
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    resp = client.get(f"/matches/{match.id}/hoja-cambio.pdf")
    assert resp.status_code == 409


def test_hoja_cambio_devuelve_pdf(client, db):
    ana, pedro, match = _setup_match(db, estado="confirmado_total")
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    resp = client.get(f"/matches/{match.id}/hoja-cambio.pdf")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data[:5] == b"%PDF-"


def test_hoja_cambio_participante_no_ana_tambien_puede_descargar(client, db):
    ana, pedro, match = _setup_match(db, estado="confirmado_total")
    client.post("/auth/login", data={"email": "pedro@test.es", "password": "password123"})
    resp = client.get(f"/matches/{match.id}/hoja-cambio.pdf")
    assert resp.status_code == 200
