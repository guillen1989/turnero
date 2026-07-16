"""
Tests de flujos críticos — ejercen secuencias de operaciones sobre múltiples
modelos, simulando el recorrido real del usuario. Detectan bugs de integridad
referencial o de estado inconsistente que los tests unitarios no ven.
"""
from datetime import date
from unittest.mock import patch

from app.extensions import db
from app.matching.service import buscar_matches_para, crear_match_directo, crear_pub_sintetica
from app.models import (
    Categoria, FranjaHoraria, MatchCambio, Notificacion,
    PublicacionCambio, TurnoCedido, TurnoAceptado,
    insertar_categorias_semilla,
)
from app.services.registro import registrar_usuario

# PNG 1x1 transparente válido, usado como firma de prueba.
FIRMA_VALIDA = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4"
    "2mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dos_usuarios():
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    u1 = registrar_usuario("A", "a@test.es", "pass1234", "H1", "Urgencias", cat.id)
    u2 = registrar_usuario("B", "b@test.es", "pass1234", "H1", "Urgencias", cat.id)
    return u1, u2


def _franja(grupo_id):
    return FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id).first()


def _pub_db(usuario, fecha_cede=date(2026, 9, 1), fecha_acepta=date(2026, 9, 2)):
    franja = _franja(usuario.unidad.grupo_intercambio_id)
    pub = PublicacionCambio(usuario_id=usuario.id)
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=fecha_cede, franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=fecha_acepta, franja_horaria_id=franja.id))
    db.session.commit()
    return pub


def _login(client, email):
    client.post("/auth/login", data={"email": email, "password": "pass1234"})


# ---------------------------------------------------------------------------
# Flujo 1: publicar → eliminar via HTTP (recorrido HTTP completo)
# ---------------------------------------------------------------------------

def test_flujo_publicar_y_eliminar_via_http(client, db):
    """Publicar y eliminar usando solo HTTP — sin acceso directo a la BD."""
    u, _ = _dos_usuarios()
    _login(client, "a@test.es")
    franja = _franja(u.unidad.grupo_intercambio_id)

    resp = client.post("/publicar", data={
        "fecha_cedida_0": "2026-09-01",
        "franja_cedida_0": franja.id,
        "fecha_aceptada_0": "2026-09-02",
        "franja_aceptada_0": franja.id,
    }, follow_redirects=False)
    assert resp.status_code == 302

    pub = PublicacionCambio.query.filter_by(usuario_id=u.id).first()
    assert pub is not None
    pub_id = pub.id

    resp = client.post(f"/publicaciones/{pub_id}/eliminar", follow_redirects=False)
    assert resp.status_code == 302
    assert db.session.get(PublicacionCambio, pub_id) is None


# ---------------------------------------------------------------------------
# Flujo 2: me-interesa → confirmar ambas partes → match cerrado
# ---------------------------------------------------------------------------

def test_flujo_me_interesa_confirmar_ambas_partes(client, db):
    """Match creado via me-interesa; ambas partes confirman via HTTP."""
    u1, u2 = _dos_usuarios()
    franja = _franja(u1.unidad.grupo_intercambio_id)

    pub = PublicacionCambio(usuario_id=u1.id, tipo="regalo")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id))
    db.session.commit()

    _login(client, "b@test.es")
    with patch("app.push.sender.webpush"):
        assert client.post(f"/cambios/{pub.id}/me-interesa", follow_redirects=False).status_code == 302

    match = MatchCambio.query.first()
    assert match is not None
    assert match.estado == "propuesto"

    with patch("app.push.sender.webpush"):
        assert client.post(
            f"/matches/{match.id}/confirmar", data={"firma": FIRMA_VALIDA}, follow_redirects=False
        ).status_code == 302
    db.session.refresh(match)
    assert match.estado == "confirmado_parcial"

    client.get("/auth/logout")
    _login(client, "a@test.es")
    with patch("app.push.sender.webpush"):
        assert client.post(
            f"/matches/{match.id}/confirmar", data={"firma": FIRMA_VALIDA}, follow_redirects=False
        ).status_code == 302
    db.session.refresh(match)
    assert match.estado == "confirmado_total"


# ---------------------------------------------------------------------------
# Flujo 3: me-interesa → rechazar → match en estado rechazado
# ---------------------------------------------------------------------------

def test_flujo_me_interesa_y_rechazar(client, db):
    """Match creado via me-interesa; una parte rechaza via HTTP."""
    u1, u2 = _dos_usuarios()
    franja = _franja(u1.unidad.grupo_intercambio_id)

    pub = PublicacionCambio(usuario_id=u1.id, tipo="regalo")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id))
    db.session.commit()

    _login(client, "b@test.es")
    with patch("app.push.sender.webpush"):
        client.post(f"/cambios/{pub.id}/me-interesa")

    match = MatchCambio.query.first()
    assert match is not None

    with patch("app.push.sender.webpush"):
        resp = client.post(f"/matches/{match.id}/rechazar", follow_redirects=False)
    assert resp.status_code == 302
    db.session.refresh(match)
    assert match.estado == "rechazado"


# ---------------------------------------------------------------------------
# Flujo 4: eliminar pub con sintética dependiente Y notificación asociada
# (combina las dos causas de FK violation que han fallado en producción)
# ---------------------------------------------------------------------------

def test_flujo_eliminar_pub_con_sintetica_y_notificacion(client, db):
    """
    Regresión compuesta: pub_a tiene una sintética (cadena_3) Y una notificación.
    Eliminar pub_a debe borrar todo sin 500.
    """
    u1, u2 = _dos_usuarios()
    pub_a = _pub_db(u1, date(2026, 10, 1), date(2026, 10, 2))
    pub_b = _pub_db(u2, date(2026, 10, 2), date(2026, 10, 1))
    sint = crear_pub_sintetica(pub_a, pub_b)

    notif = Notificacion(
        usuario_id=u2.id,
        publicacion_id=pub_a.id,
        tipo="nueva_publicacion_seguido",
    )
    db.session.add(notif)
    db.session.commit()
    pub_a_id, sint_id, notif_id = pub_a.id, sint.id, notif.id

    _login(client, "a@test.es")
    resp = client.post(f"/publicaciones/{pub_a_id}/eliminar", follow_redirects=False)

    assert resp.status_code == 302
    assert db.session.get(PublicacionCambio, pub_a_id) is None
    assert db.session.get(PublicacionCambio, sint_id) is None
    assert db.session.get(Notificacion, notif_id) is None


# ---------------------------------------------------------------------------
# Flujo 5: editar publicación con match existente → match eliminado, sin 500
# ---------------------------------------------------------------------------

def test_flujo_editar_pub_invalida_match_existente(client, db):
    """Editar una pub con match propuesto rechaza el match (y avisa a la
    contraparte) en vez de borrarlo en silencio, y no da 500."""
    u1, u2 = _dos_usuarios()
    pub1 = _pub_db(u1, date(2026, 9, 1), date(2026, 9, 2))
    pub2 = _pub_db(u2, date(2026, 9, 2), date(2026, 9, 1))
    for candidata in buscar_matches_para(pub1):
        crear_match_directo(pub1, candidata)
    assert MatchCambio.query.count() == 1
    match = MatchCambio.query.first()

    _login(client, "a@test.es")
    franja = _franja(u1.unidad.grupo_intercambio_id)
    resp = client.post(f"/publicaciones/{pub1.id}/editar", data={
        "fecha_cedida_0": "2026-11-01",
        "franja_cedida_0": franja.id,
        "fecha_aceptada_0": "2026-11-02",
        "franja_aceptada_0": franja.id,
    }, follow_redirects=False)

    assert resp.status_code == 302
    db.session.refresh(match)
    assert match.estado == "rechazado"
    assert Notificacion.query.filter_by(usuario_id=u2.id, tipo="rechazo", match_id=match.id).first() is not None
