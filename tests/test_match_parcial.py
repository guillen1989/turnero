"""Tests del aviso de coincidencia parcial (cambio ↔ regalo / cambio ↔ peticion)."""
import json
from datetime import date, time
from unittest.mock import patch

from app.extensions import db
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
from app.matching.service import crear_match_directo
from app.push.sender import enviar_push_condicional
from app.services.registro import registrar_usuario


def _usuario(nombre, email, password="password123"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario(nombre, email, password, "Hospital T", "Urgencias", cat.id)


def _franja(grupo_id, nombre="Mañana"):
    return FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id, nombre=nombre).first()


def _login(client, email, password="password123"):
    client.post("/auth/login", data={"email": email, "password": password})


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


# --- Validación del badge en el dashboard ---

def test_dashboard_usuario_cambio_ve_coincidencia_parcial_con_regalo(client, db):
    """Juan (cambio) ve '¡Coincidencia parcial!' en su dashboard cuando el match es con un regalo."""
    juan = _usuario("Juan", "juan@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(juan.unidad.grupo_intercambio_id)

    pub_juan = _pub_cambio(juan, franja, date(2026, 9, 26), date(2026, 9, 27))
    pub_pedro = _pub_regalo(pedro, franja, date(2026, 9, 26))
    crear_match_directo(pub_juan, pub_pedro)

    _login(client, "juan@test.es")
    resp = client.get("/?estado=compatible")
    html = resp.data.decode()

    assert "¡Coincidencia parcial!" in html
    assert "¡Compatible!" not in html


def test_dashboard_usuario_regalo_ve_compatible_no_parcial(client, db):
    """Pedro (regalo) ve '¡Compatible!' porque desde su perspectiva el match es completo."""
    juan = _usuario("Juan", "juan@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(juan.unidad.grupo_intercambio_id)

    pub_juan = _pub_cambio(juan, franja, date(2026, 9, 26), date(2026, 9, 27))
    pub_pedro = _pub_regalo(pedro, franja, date(2026, 9, 26))
    crear_match_directo(pub_juan, pub_pedro)

    _login(client, "pedro@test.es")
    resp = client.get("/?estado=compatible")
    html = resp.data.decode()

    assert "¡Compatible!" in html
    assert "¡Coincidencia parcial!" not in html


def test_dashboard_usuario_cambio_ve_coincidencia_parcial_con_peticion(client, db):
    """Juan (cambio) ve '¡Coincidencia parcial!' cuando el match es con una petición."""
    juan = _usuario("Juan", "juan@test.es")
    luis = _usuario("Luis", "luis@test.es")
    franja = _franja(juan.unidad.grupo_intercambio_id)

    pub_juan = _pub_cambio(juan, franja, date(2026, 9, 26), date(2026, 9, 27))
    pub_luis = _pub_peticion(luis, franja, date(2026, 9, 27))
    crear_match_directo(pub_juan, pub_luis)

    _login(client, "juan@test.es")
    resp = client.get("/?estado=compatible")
    html = resp.data.decode()

    assert "¡Coincidencia parcial!" in html


def test_dashboard_cambio_vs_cambio_muestra_compatible(client, db):
    """Un match completo cambio↔cambio muestra '¡Compatible!' sin aviso parcial."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_ana = _pub_cambio(ana, franja, date(2026, 9, 25), date(2026, 9, 26))
    pub_pedro = _pub_cambio(pedro, franja, date(2026, 9, 26), date(2026, 9, 25))
    crear_match_directo(pub_ana, pub_pedro)

    _login(client, "ana@test.es")
    resp = client.get("/?estado=compatible")
    html = resp.data.decode()

    assert "¡Compatible!" in html
    assert "¡Coincidencia parcial!" not in html


# --- Push de tipo match_parcial ---

SUBSCRIPTION = {
    "endpoint": "https://push.example.com/test",
    "keys": {"p256dh": "FAKE_P256DH", "auth": "FAKE_AUTH"},
}


def test_push_match_parcial_usa_texto_diferente(app, db):
    """enviar_push_condicional con tipo 'match_parcial' usa el texto de coincidencia parcial."""
    juan = _usuario("Juan", "juan@test.es")
    juan.push_activo = True
    juan.notif_match = True
    juan.push_subscription = json.dumps(SUBSCRIPTION)
    db.session.commit()

    app.config["VAPID_PRIVATE_KEY"] = "fake-key"
    app.config["VAPID_CLAIM_EMAIL"] = "admin@test.es"

    payloads_enviados = []

    def fake_webpush(**kwargs):
        payloads_enviados.append(json.loads(kwargs["data"]))

    with patch("app.push.sender.webpush", side_effect=fake_webpush):
        enviar_push_condicional(juan, "match_parcial")

    assert len(payloads_enviados) == 1
    assert "parcial" in payloads_enviados[0]["body"].lower()


def test_push_match_parcial_respeta_preferencia_notif_match(app, db):
    """Si notif_match está desactivado, no se envía el push de match_parcial."""
    juan = _usuario("Juan", "juan@test.es")
    juan.push_activo = True
    juan.notif_match = False
    juan.push_subscription = json.dumps(SUBSCRIPTION)
    db.session.commit()

    app.config["VAPID_PRIVATE_KEY"] = "fake-key"

    with patch("app.push.sender.webpush") as mock_wp:
        enviar_push_condicional(juan, "match_parcial")
        mock_wp.assert_not_called()


def test_crear_match_parcial_envia_push_a_ambos_usuarios(app, db):
    """crear_match_directo en pareja parcial envía push a ambos participantes."""
    juan = _usuario("Juan", "juan@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    for u in (juan, pedro):
        u.push_activo = True
        u.notif_match = True
        u.push_subscription = json.dumps(SUBSCRIPTION)
    db.session.commit()

    app.config["VAPID_PRIVATE_KEY"] = "fake-key"
    app.config["VAPID_CLAIM_EMAIL"] = "admin@test.es"
    franja = _franja(juan.unidad.grupo_intercambio_id)

    pub_juan = _pub_cambio(juan, franja, date(2026, 9, 26), date(2026, 9, 27))
    pub_pedro = _pub_regalo(pedro, franja, date(2026, 9, 26))

    llamadas = []

    def fake_webpush(**kwargs):
        llamadas.append(json.loads(kwargs["data"]))

    with patch("app.push.sender.webpush", side_effect=fake_webpush):
        crear_match_directo(pub_juan, pub_pedro)

    assert len(llamadas) == 2
    textos = [ll["body"] for ll in llamadas]
    assert any("parcial" in t.lower() for t in textos)
    assert any("parcial" not in t.lower() for t in textos)
