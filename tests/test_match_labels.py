"""Tests de las etiquetas de turno en las tarjetas de match del dashboard.

Las etiquetas muestran el nombre del compañero en lugar de frases impersonales:
  - "Tú libras:" en lugar de "Tú quieres librar:"
  - "Tú trabajas:" en lugar de "Trabajarías:"
  - "Marta libra:" en lugar de "Librarías:" (cuando otra.turno_cedido)
  - "Marta trabaja:" en lugar de "Librarías:" (cuando otra.turno_aceptado)
"""
from datetime import date
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
from app.matching.service import crear_match_directo
from app.services.registro import registrar_usuario


def _usuario(nombre, email):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario(nombre, email, "password123", "H1", "Urgencias", cat.id)


def _franja(grupo_id):
    return FranjaHoraria.query.filter_by(
        grupo_intercambio_id=grupo_id, nombre="Mañana"
    ).first()


def _login(client, email):
    client.post("/auth/login", data={"email": email, "password": "password123"})


def _pub_cambio(usuario, franja, fecha_cede, fecha_acepta):
    pub = PublicacionCambio(usuario_id=usuario.id, tipo="cambio")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=fecha_cede, franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=fecha_acepta, franja_horaria_id=franja.id))
    db.session.commit()
    return pub


def _pub_regalo(usuario, franja, fecha_acepta):
    pub = PublicacionCambio(usuario_id=usuario.id, tipo="regalo")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=fecha_acepta, franja_horaria_id=franja.id))
    db.session.commit()
    return pub


def _pub_peticion(usuario, franja, fecha_cede):
    pub = PublicacionCambio(usuario_id=usuario.id, tipo="peticion")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=fecha_cede, franja_horaria_id=franja.id))
    db.session.commit()
    return pub


# ---------------------------------------------------------------------------
# cambio ↔ cambio
# ---------------------------------------------------------------------------

def test_mi_turno_cedido_muestra_tu_libras(client, db):
    """El turno cedido propio se etiqueta 'Tú libras:' (no 'Tú quieres librar:')."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_ana = _pub_cambio(ana, franja, date(2026, 9, 1), date(2026, 9, 2))
    pub_pedro = _pub_cambio(pedro, franja, date(2026, 9, 2), date(2026, 9, 1))

    with patch("app.push.sender.webpush"):
        crear_match_directo(pub_ana, pub_pedro)

    _login(client, "ana@test.es")
    html = client.get("/?estado=compatible").data.decode()

    assert "Tú libras:" in html
    assert "Tú quieres librar:" not in html


def test_otro_turno_cedido_muestra_nombre_libra(client, db):
    """El turno cedido de la otra persona se etiqueta '[Nombre] libra:'."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_ana = _pub_cambio(ana, franja, date(2026, 9, 1), date(2026, 9, 2))
    pub_pedro = _pub_cambio(pedro, franja, date(2026, 9, 2), date(2026, 9, 1))

    with patch("app.push.sender.webpush"):
        crear_match_directo(pub_ana, pub_pedro)

    _login(client, "ana@test.es")
    html = client.get("/?estado=compatible").data.decode()

    assert "Pedro libra:" in html
    assert "Librarías:" not in html


# ---------------------------------------------------------------------------
# regalo ↔ peticion  (aceptado propio, cedido ajeno)
# ---------------------------------------------------------------------------

def test_mi_turno_aceptado_muestra_tu_trabajas(client, db):
    """El turno aceptado propio se etiqueta 'Tú trabajas:' (no 'Trabajarías:')."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_ana = _pub_regalo(ana, franja, date(2026, 9, 1))   # ana se ofrece a trabajar
    pub_pedro = _pub_peticion(pedro, franja, date(2026, 9, 1))  # pedro quiere librar

    with patch("app.push.sender.webpush"):
        crear_match_directo(pub_ana, pub_pedro)

    _login(client, "ana@test.es")
    html = client.get("/?estado=compatible").data.decode()

    assert "Tú trabajas:" in html
    assert "Trabajarías:" not in html


def test_otro_turno_cedido_en_regalo_peticion_muestra_nombre_libra(client, db):
    """Desde la vista del regalo, el cedido de petición se etiqueta '[Nombre] libra:'."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_ana = _pub_regalo(ana, franja, date(2026, 9, 1))
    pub_pedro = _pub_peticion(pedro, franja, date(2026, 9, 1))

    with patch("app.push.sender.webpush"):
        crear_match_directo(pub_ana, pub_pedro)

    _login(client, "ana@test.es")
    html = client.get("/?estado=compatible").data.decode()

    assert "Pedro libra:" in html


def test_otro_turno_aceptado_en_regalo_peticion_muestra_nombre_trabaja(client, db):
    """Desde la vista de petición, el aceptado de regalo se etiqueta '[Nombre] trabaja:'."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_ana = _pub_regalo(ana, franja, date(2026, 9, 1))
    pub_pedro = _pub_peticion(pedro, franja, date(2026, 9, 1))

    with patch("app.push.sender.webpush"):
        crear_match_directo(pub_ana, pub_pedro)

    _login(client, "pedro@test.es")
    html = client.get("/?estado=compatible").data.decode()

    assert "Ana trabaja:" in html
