"""Tests de la acción 'Me interesa' sobre publicaciones ajenas."""
from datetime import date
from unittest.mock import patch

from app.extensions import db
from app.models import (
    Categoria, FranjaHoraria, MatchCambio, PublicacionCambio,
    TurnoCedido, TurnoAceptado, insertar_categorias_semilla,
)
from app.services.registro import registrar_usuario


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup(cat_nombre="Enfermería"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre=cat_nombre).first()
    ana = registrar_usuario("Ana", "ana@test.es", "pass", "H1", "Urgencias", cat.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "pass", "H1", "Urgencias", cat.id)
    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=ana.unidad.grupo_intercambio_id, nombre="Mañana"
    ).first()
    return ana, pedro, franja


def _login(client, email):
    client.post("/auth/login", data={"email": email, "password": "pass"})


def _pub_cambio(usuario, franja, fecha_cede=date(2026, 9, 1), fecha_acepta=date(2026, 9, 2)):
    pub = PublicacionCambio(usuario_id=usuario.id, tipo="cambio")
    db.session.add(pub)
    db.session.flush()
    tc = TurnoCedido(publicacion_id=pub.id, fecha=fecha_cede, franja_horaria_id=franja.id)
    ta = TurnoAceptado(publicacion_id=pub.id, fecha=fecha_acepta, franja_horaria_id=franja.id)
    db.session.add(tc)
    db.session.add(ta)
    db.session.commit()
    return pub, tc, ta


def _pub_regalo(usuario, franja, fecha=date(2026, 9, 5)):
    pub = PublicacionCambio(usuario_id=usuario.id, tipo="regalo")
    db.session.add(pub)
    db.session.flush()
    ta = TurnoAceptado(publicacion_id=pub.id, fecha=fecha, franja_horaria_id=franja.id)
    db.session.add(ta)
    db.session.commit()
    return pub, ta


def _pub_peticion(usuario, franja, fecha=date(2026, 9, 3)):
    pub = PublicacionCambio(usuario_id=usuario.id, tipo="peticion")
    db.session.add(pub)
    db.session.flush()
    tc = TurnoCedido(publicacion_id=pub.id, fecha=fecha, franja_horaria_id=franja.id)
    db.session.add(tc)
    db.session.commit()
    return pub, tc


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------

def test_me_interesa_requiere_login(client, db):
    ana, pedro, franja = _setup()
    pub, _, _ = _pub_cambio(ana, franja)
    resp = client.post(f"/cambios/{pub.id}/me-interesa", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_me_interesa_propia_pub_redirige_con_aviso(client, db):
    ana, pedro, franja = _setup()
    pub, tc, ta = _pub_cambio(ana, franja)
    _login(client, "ana@test.es")
    resp = client.post(f"/cambios/{pub.id}/me-interesa",
                       data={"turno_cedido_id": tc.id, "turno_aceptado_id": ta.id},
                       follow_redirects=True)
    assert resp.status_code == 200
    assert MatchCambio.query.count() == 0


def test_me_interesa_pub_inactiva_redirige(client, db):
    ana, pedro, franja = _setup()
    pub, tc, ta = _pub_cambio(ana, franja)
    pub.estado = "cancelada"
    db.session.commit()
    _login(client, "pedro@test.es")
    resp = client.post(f"/cambios/{pub.id}/me-interesa",
                       data={"turno_cedido_id": tc.id, "turno_aceptado_id": ta.id},
                       follow_redirects=True)
    assert resp.status_code == 200
    assert MatchCambio.query.count() == 0


def test_me_interesa_categoria_distinta_retorna_403(client, db):
    ana, _, franja = _setup()
    insertar_categorias_semilla()
    cat2 = Categoria.query.filter_by(nombre="Auxiliar de enfermería (TCAE)").first()
    otro = registrar_usuario("Otro", "otro@test.es", "pass", "H1", "Urgencias", cat2.id)
    pub, tc, ta = _pub_cambio(ana, franja)
    _login(client, "otro@test.es")
    resp = client.post(f"/cambios/{pub.id}/me-interesa",
                       data={"turno_cedido_id": tc.id, "turno_aceptado_id": ta.id})
    assert resp.status_code == 403


def test_me_interesa_turno_ajeno_redirige_con_aviso(client, db):
    ana, pedro, franja = _setup()
    pub_a, tc_a, ta_a = _pub_cambio(ana, franja)
    pub_b, tc_b, ta_b = _pub_cambio(pedro, franja, date(2026, 10, 1), date(2026, 10, 2))
    _login(client, "pedro@test.es")
    # tc_b pertenece a pub_b, no a pub_a → debe fallar
    resp = client.post(f"/cambios/{pub_a.id}/me-interesa",
                       data={"turno_cedido_id": tc_b.id, "turno_aceptado_id": ta_a.id},
                       follow_redirects=True)
    assert resp.status_code == 200
    assert MatchCambio.query.count() == 0


# ---------------------------------------------------------------------------
# Cambio (tipo)
# ---------------------------------------------------------------------------

def test_me_interesa_cambio_crea_match(client, db):
    ana, pedro, franja = _setup()
    pub_a, tc_a, ta_a = _pub_cambio(ana, franja)
    _login(client, "pedro@test.es")
    with patch("app.push.sender.webpush"):
        resp = client.post(f"/cambios/{pub_a.id}/me-interesa",
                           data={"turno_cedido_id": tc_a.id, "turno_aceptado_id": ta_a.id},
                           follow_redirects=False)
    assert resp.status_code == 302
    assert MatchCambio.query.count() == 1
    assert PublicacionCambio.query.count() == 2  # pub_a + pub_b espejo


def test_me_interesa_cambio_sin_turnos_da_aviso(client, db):
    ana, pedro, franja = _setup()
    pub_a, _, _ = _pub_cambio(ana, franja)
    _login(client, "pedro@test.es")
    resp = client.post(f"/cambios/{pub_a.id}/me-interesa", data={}, follow_redirects=True)
    assert resp.status_code == 200
    assert MatchCambio.query.count() == 0


# ---------------------------------------------------------------------------
# Regalo (tipo)
# ---------------------------------------------------------------------------

def test_me_interesa_regalo_crea_peticion_espejo(client, db):
    ana, pedro, franja = _setup()
    pub_a, ta_a = _pub_regalo(ana, franja)
    _login(client, "pedro@test.es")
    with patch("app.push.sender.webpush"):
        resp = client.post(f"/cambios/{pub_a.id}/me-interesa",
                           data={},
                           follow_redirects=False)
    assert resp.status_code == 302
    assert MatchCambio.query.count() == 1
    pub_b = PublicacionCambio.query.filter_by(usuario_id=pedro.id).first()
    assert pub_b is not None
    assert pub_b.tipo == "peticion"
    assert pub_b.turnos_cedidos[0].franja_horaria_id == ta_a.franja_horaria_id
    assert pub_b.turnos_cedidos[0].fecha == ta_a.fecha


# ---------------------------------------------------------------------------
# Petición (tipo)
# ---------------------------------------------------------------------------

def test_me_interesa_peticion_crea_regalo_espejo(client, db):
    """Petición con un cedido específico: flujo sin form data (salto de diálogo)."""
    ana, pedro, franja = _setup()
    pub_a, tc_a = _pub_peticion(ana, franja)
    _login(client, "pedro@test.es")
    with patch("app.push.sender.webpush"):
        resp = client.post(f"/cambios/{pub_a.id}/me-interesa",
                           data={},
                           follow_redirects=False)
    assert resp.status_code == 302
    assert MatchCambio.query.count() == 1
    pub_b = PublicacionCambio.query.filter_by(usuario_id=pedro.id).first()
    assert pub_b is not None
    assert pub_b.tipo == "regalo"
    assert pub_b.turnos_aceptados[0].franja_horaria_id == tc_a.franja_horaria_id
    assert pub_b.turnos_aceptados[0].fecha == tc_a.fecha


def test_me_interesa_peticion_multiturn_requiere_seleccion(client, db):
    """Petición con varios cedidos: sin form data no crea match."""
    ana, pedro, franja = _setup()
    pub_a = PublicacionCambio(usuario_id=ana.id, tipo="peticion")
    db.session.add(pub_a)
    db.session.flush()
    tc1 = TurnoCedido(publicacion_id=pub_a.id, fecha=date(2026, 9, 3), franja_horaria_id=franja.id)
    tc2 = TurnoCedido(publicacion_id=pub_a.id, fecha=date(2026, 9, 4), franja_horaria_id=franja.id)
    db.session.add_all([tc1, tc2])
    db.session.commit()
    _login(client, "pedro@test.es")
    resp = client.post(f"/cambios/{pub_a.id}/me-interesa", data={}, follow_redirects=True)
    assert MatchCambio.query.count() == 0
    assert "Selecciona el turno" in resp.get_data(as_text=True)


# ---------------------------------------------------------------------------
# Junte (tipo)
# ---------------------------------------------------------------------------

def test_me_interesa_push_va_al_autor_no_al_que_hace_clic(client, db):
    """La push debe notificar a Ana (autora), no a Pedro (quien hace clic)."""
    ana, pedro, franja = _setup()
    pub_a, tc_a, ta_a = _pub_cambio(ana, franja)
    _login(client, "pedro@test.es")
    with patch("app.matching.service.enviar_push_condicional") as mock_push:
        client.post(f"/cambios/{pub_a.id}/me-interesa",
                    data={"turno_cedido_id": tc_a.id, "turno_aceptado_id": ta_a.id})
    mock_push.assert_called_once()
    usuario_notificado = mock_push.call_args.args[0]
    assert usuario_notificado.id == ana.id


def test_me_interesa_junte_crea_match(client, db):
    ana, pedro, franja = _setup()

    pub_a = PublicacionCambio(usuario_id=ana.id, tipo="junte")
    db.session.add(pub_a)
    db.session.flush()
    tc1 = TurnoCedido(publicacion_id=pub_a.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id)
    tc2 = TurnoCedido(publicacion_id=pub_a.id, fecha=date(2026, 9, 3), franja_horaria_id=franja.id)
    ta1 = TurnoAceptado(publicacion_id=pub_a.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id)
    ta2 = TurnoAceptado(publicacion_id=pub_a.id, fecha=date(2026, 9, 4), franja_horaria_id=franja.id)
    db.session.add_all([tc1, tc2, ta1, ta2])
    db.session.commit()

    _login(client, "pedro@test.es")
    with patch("app.push.sender.webpush"):
        resp = client.post(f"/cambios/{pub_a.id}/me-interesa", data={}, follow_redirects=False)
    assert resp.status_code == 302
    assert MatchCambio.query.count() == 1
    pub_b = PublicacionCambio.query.filter_by(usuario_id=pedro.id).first()
    assert pub_b.tipo == "junte"
    fechas_cedidas_b = {tc.fecha for tc in pub_b.turnos_cedidos}
    assert fechas_cedidas_b == {date(2026, 9, 2), date(2026, 9, 4)}
