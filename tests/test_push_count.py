"""Tests del contador de push de match: debe reflejar notificaciones no leídas,
no el total de matches propuestos, para evitar el acumulativo al resolver matches."""
import json
from datetime import date
from unittest.mock import patch

from app.extensions import db
from app.models import (
    Categoria,
    FranjaHoraria,
    Notificacion,
    PublicacionCambio,
    TurnoCedido,
    TurnoAceptado,
    insertar_categorias_semilla,
)
from app.matching.service import crear_match_directo
from app.push.sender import _contar_pendientes
from app.services.registro import registrar_usuario


def _usuario(nombre, email):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario(nombre, email, "password123", "H1", "Urgencias", cat.id)


def _franja(grupo_id):
    return FranjaHoraria.query.filter_by(
        grupo_intercambio_id=grupo_id, nombre="Mañana"
    ).first()


def _pub_cambio(usuario, franja, fecha_cede, fecha_acepta):
    pub = PublicacionCambio(usuario_id=usuario.id, tipo="cambio")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=fecha_cede, franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=fecha_acepta, franja_horaria_id=franja.id))
    db.session.commit()
    return pub


def _login(client, email):
    client.post("/auth/login", data={"email": email, "password": "password123"})


# ---------------------------------------------------------------------------
# 1. El contador usa Notificacion(leida=False), no matches propuestos
# ---------------------------------------------------------------------------

def test_contar_pendientes_match_cuenta_notificaciones_no_leidas(app, db):
    """Después de crear un match, _contar_pendientes devuelve 1 (la notificación creada)."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_ana = _pub_cambio(ana, franja, date(2026, 9, 1), date(2026, 9, 2))
    pub_pedro = _pub_cambio(pedro, franja, date(2026, 9, 2), date(2026, 9, 1))

    with patch("app.push.sender.webpush"):
        crear_match_directo(pub_ana, pub_pedro)

    assert _contar_pendientes(pedro, "match") == 1


def test_contar_pendientes_match_ignora_notificaciones_leidas(app, db):
    """Si la notificación ya está leída, el contador devuelve 0."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_ana = _pub_cambio(ana, franja, date(2026, 9, 1), date(2026, 9, 2))
    pub_pedro = _pub_cambio(pedro, franja, date(2026, 9, 2), date(2026, 9, 1))

    with patch("app.push.sender.webpush"):
        crear_match_directo(pub_ana, pub_pedro)

    Notificacion.query.filter_by(usuario_id=pedro.id, tipo="nuevo_match").update({"leida": True})
    db.session.commit()

    assert _contar_pendientes(pedro, "match") == 0


def test_contar_pendientes_match_acumula_sin_leer(app, db):
    """Dos matches sin leer → contador devuelve 2."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    luis = _usuario("Luis", "luis@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub1_pedro = _pub_cambio(pedro, franja, date(2026, 9, 1), date(2026, 9, 2))
    pub_ana = _pub_cambio(ana, franja, date(2026, 9, 2), date(2026, 9, 1))
    pub2_pedro = _pub_cambio(pedro, franja, date(2026, 9, 3), date(2026, 9, 4))
    pub_luis = _pub_cambio(luis, franja, date(2026, 9, 4), date(2026, 9, 3))

    with patch("app.push.sender.webpush"):
        crear_match_directo(pub1_pedro, pub_ana)
        crear_match_directo(pub2_pedro, pub_luis)

    assert _contar_pendientes(pedro, "match") == 2


# ---------------------------------------------------------------------------
# 2. El dashboard marca las notificaciones como leídas
# ---------------------------------------------------------------------------

def test_dashboard_compatible_marca_notificaciones_como_leidas(client, db):
    """GET /?estado=compatible marca las notificaciones nuevo_match del usuario como leídas."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_ana = _pub_cambio(ana, franja, date(2026, 9, 1), date(2026, 9, 2))
    pub_pedro = _pub_cambio(pedro, franja, date(2026, 9, 2), date(2026, 9, 1))

    with patch("app.push.sender.webpush"):
        crear_match_directo(pub_ana, pub_pedro)

    _login(client, "pedro@test.es")
    client.get("/?estado=compatible")

    no_leidas = Notificacion.query.filter_by(
        usuario_id=pedro.id, tipo="nuevo_match", leida=False
    ).count()
    assert no_leidas == 0


def test_dashboard_compatible_reduce_conteo_push_a_cero(client, app, db):
    """Tras visitar el tab Compatibles, _contar_pendientes devuelve 0."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_ana = _pub_cambio(ana, franja, date(2026, 9, 1), date(2026, 9, 2))
    pub_pedro = _pub_cambio(pedro, franja, date(2026, 9, 2), date(2026, 9, 1))

    with patch("app.push.sender.webpush"):
        crear_match_directo(pub_ana, pub_pedro)

    _login(client, "pedro@test.es")
    client.get("/?estado=compatible")

    with app.app_context():
        pedro_reload = db.session.get(db.session.get(pedro.__class__, pedro.id).__class__, pedro.id)
        assert _contar_pendientes(pedro, "match") == 0


def test_push_count_no_acumula_tras_visita_dashboard(client, app, db):
    """Después de visitar el dashboard, un nuevo match vuelve el contador a 1 (no acumula)."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    luis = _usuario("Luis", "luis@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub1_pedro = _pub_cambio(pedro, franja, date(2026, 9, 1), date(2026, 9, 2))
    pub_ana = _pub_cambio(ana, franja, date(2026, 9, 2), date(2026, 9, 1))

    with patch("app.push.sender.webpush"):
        crear_match_directo(pub1_pedro, pub_ana)

    _login(client, "pedro@test.es")
    client.get("/?estado=compatible")

    pub2_pedro = _pub_cambio(pedro, franja, date(2026, 9, 3), date(2026, 9, 4))
    pub_luis = _pub_cambio(luis, franja, date(2026, 9, 4), date(2026, 9, 3))

    with patch("app.push.sender.webpush"):
        crear_match_directo(pub2_pedro, pub_luis)

    assert _contar_pendientes(pedro, "match") == 1
