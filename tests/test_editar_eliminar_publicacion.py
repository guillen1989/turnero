"""Tests para editar y eliminar publicaciones propias."""
from datetime import date

from app.extensions import db
from app.models import (
    Categoria, FranjaHoraria, MatchCambio, Notificacion, PublicacionCambio,
    TurnoCedido, TurnoAceptado, insertar_categorias_semilla,
)
from app.services.registro import registrar_usuario


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _usuario(email="u@test.es"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    u = registrar_usuario("Test", email, "pass123", "H1", "Urgencias", cat.id)
    db.session.commit()
    return u


def _login(client, email):
    client.post("/auth/login", data={"email": email, "password": "pass123"})


def _franja(grupo_id):
    return FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id).first()


def _pub(usuario, fecha_cede=date(2026, 9, 1), fecha_acepta=date(2026, 9, 2)):
    franja = _franja(usuario.unidad.grupo_intercambio_id)
    pub = PublicacionCambio(usuario_id=usuario.id)
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=fecha_cede, franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=fecha_acepta, franja_horaria_id=franja.id))
    db.session.commit()
    return pub


# ---------------------------------------------------------------------------
# Editar — acceso
# ---------------------------------------------------------------------------

def test_editar_requiere_login(client, db):
    u = _usuario()
    pub = _pub(u)
    resp = client.get(f"/publicaciones/{pub.id}/editar", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_editar_get_muestra_formulario_pre_rellenado(client, db):
    u = _usuario()
    _login(client, u.email)
    pub = _pub(u)
    resp = client.get(f"/publicaciones/{pub.id}/editar")
    assert resp.status_code == 200
    assert b"2026-09-01" in resp.data


def test_editar_403_si_publicacion_ajena(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)
    pub = _pub(u2)
    resp = client.post(f"/publicaciones/{pub.id}/editar", data={})
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Editar — guardar cambios
# ---------------------------------------------------------------------------

def test_editar_actualiza_turnos(client, db):
    u = _usuario()
    _login(client, u.email)
    pub = _pub(u)
    franja = _franja(u.unidad.grupo_intercambio_id)

    resp = client.post(f"/publicaciones/{pub.id}/editar", data={
        "fecha_cedida_0": "2026-10-15",
        "franja_cedida_0": franja.id,
        "fecha_aceptada_0": "2026-10-20",
        "franja_aceptada_0": franja.id,
    }, follow_redirects=False)

    assert resp.status_code == 302
    db.session.refresh(pub)
    tc = TurnoCedido.query.filter_by(publicacion_id=pub.id).first()
    assert tc.fecha == date(2026, 10, 15)


def test_editar_actualiza_mensaje(client, db):
    u = _usuario()
    _login(client, u.email)
    pub = _pub(u)
    franja = _franja(u.unidad.grupo_intercambio_id)

    client.post(f"/publicaciones/{pub.id}/editar", data={
        "fecha_cedida_0": "2026-10-15",
        "franja_cedida_0": franja.id,
        "fecha_aceptada_0": "2026-10-20",
        "franja_aceptada_0": franja.id,
        "mensaje": "Nuevo mensaje",
    })

    db.session.refresh(pub)
    assert pub.mensaje == "Nuevo mensaje"


def test_editar_elimina_matches_existentes(client, db):
    """Editar rechaza (no borra en silencio) los matches activos y avisa a la
    contraparte, para no dejar una confirmación de la otra parte huérfana."""
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    franja = _franja(u1.unidad.grupo_intercambio_id)

    pub1 = _pub(u1, date(2026, 9, 1), date(2026, 9, 2))
    pub2 = _pub(u2, date(2026, 9, 2), date(2026, 9, 1))

    from app.matching.service import buscar_matches_para, crear_match_directo
    for c in buscar_matches_para(pub1):
        crear_match_directo(pub1, c)
    assert MatchCambio.query.count() == 1
    match = MatchCambio.query.first()

    _login(client, u1.email)
    client.post(f"/publicaciones/{pub1.id}/editar", data={
        "fecha_cedida_0": "2026-11-01",
        "franja_cedida_0": franja.id,
        "fecha_aceptada_0": "2026-11-02",
        "franja_aceptada_0": franja.id,
    })

    db.session.refresh(match)
    assert match.estado == "rechazado"
    assert Notificacion.query.filter_by(usuario_id=u2.id, tipo="rechazo", match_id=match.id).first() is not None


# ---------------------------------------------------------------------------
# Eliminar
# ---------------------------------------------------------------------------

def test_eliminar_requiere_login(client, db):
    u = _usuario()
    pub = _pub(u)
    resp = client.post(f"/publicaciones/{pub.id}/eliminar", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_eliminar_borra_publicacion(client, db):
    u = _usuario()
    _login(client, u.email)
    pub = _pub(u)
    pub_id = pub.id

    resp = client.post(f"/publicaciones/{pub_id}/eliminar", follow_redirects=False)
    assert resp.status_code == 302
    assert db.session.get(PublicacionCambio, pub_id) is None


def test_eliminar_403_si_publicacion_ajena(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)
    pub = _pub(u2)
    resp = client.post(f"/publicaciones/{pub.id}/eliminar")
    assert resp.status_code == 403


def test_eliminar_borra_matches_asociados(client, db):
    """Eliminar la publicación rechaza (no borra en silencio) el match asociado
    y avisa a la contraparte, aunque la propia publicación desaparezca."""
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")

    pub1 = _pub(u1, date(2026, 9, 1), date(2026, 9, 2))
    pub2 = _pub(u2, date(2026, 9, 2), date(2026, 9, 1))

    from app.matching.service import buscar_matches_para, crear_match_directo
    for c in buscar_matches_para(pub1):
        crear_match_directo(pub1, c)
    assert MatchCambio.query.count() == 1
    match = MatchCambio.query.first()

    _login(client, u1.email)
    client.post(f"/publicaciones/{pub1.id}/eliminar")

    assert db.session.get(PublicacionCambio, pub1.id) is None
    db.session.refresh(match)
    assert match.estado == "rechazado"
    assert Notificacion.query.filter_by(usuario_id=u2.id, tipo="rechazo", match_id=match.id).first() is not None


def test_eliminar_regalo_con_match_no_da_error(client, db):
    """Eliminar una publicación tipo regalo que tiene un match no debe dar 500.

    El bug era que SQLAlchemy podía intentar borrar TurnoAceptado (via cascada
    desde la pub) antes que MatchParticipacion.turno_aceptado_id, violando la FK.
    """
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    franja = _franja(u1.unidad.grupo_intercambio_id)
    fecha = date(2026, 9, 1)

    # u1 publica regalo: ofrece trabajar fecha
    regalo = PublicacionCambio(usuario_id=u1.id, tipo="regalo")
    db.session.add(regalo)
    db.session.flush()
    db.session.add(TurnoAceptado(publicacion_id=regalo.id, fecha=fecha, franja_horaria_id=franja.id))

    # u2 publica peticion: quiere librar fecha
    peticion = PublicacionCambio(usuario_id=u2.id, tipo="peticion")
    db.session.add(peticion)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=peticion.id, fecha=fecha, franja_horaria_id=franja.id))
    db.session.commit()

    from app.matching.service import crear_match_directo
    match = crear_match_directo(regalo, peticion)
    assert MatchCambio.query.count() == 1

    _login(client, u1.email)
    resp = client.post(f"/publicaciones/{regalo.id}/eliminar", follow_redirects=False)
    assert resp.status_code == 302
    assert db.session.get(PublicacionCambio, regalo.id) is None
    db.session.refresh(match)
    assert match.estado == "rechazado"


def test_eliminar_publicacion_fuente_con_sintetica_dependiente_no_da_error(client, db):
    """Regresión: eliminar pub_a cuando existe una sintética que la referencia via
    sintetica_pub_a_id lanzaba ForeignKeyViolation porque _cancelar_sinteticas_de
    solo marca estado='cancelada' pero no elimina la fila."""
    from app.matching.service import crear_pub_sintetica

    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    pub_a = _pub(u1, date(2026, 10, 1), date(2026, 10, 2))
    pub_b = _pub(u2, date(2026, 10, 2), date(2026, 10, 1))
    sint = crear_pub_sintetica(pub_a, pub_b)
    sint_id = sint.id
    pub_a_id = pub_a.id

    _login(client, u1.email)
    resp = client.post(f"/publicaciones/{pub_a_id}/eliminar", follow_redirects=False)

    assert resp.status_code == 302
    assert db.session.get(PublicacionCambio, pub_a_id) is None
    assert db.session.get(PublicacionCambio, sint_id) is None


def test_eliminar_con_notificacion_publicacion_id_no_da_error(client, db):
    """Eliminar una publicación que tiene notificaciones por publicacion_id no debe dar 500.

    Regresión: notificacion.publicacion_id FK sin cascade bloqueaba el DELETE.
    """
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    pub = _pub(u1)

    notif = Notificacion(
        usuario_id=u2.id,
        publicacion_id=pub.id,
        tipo="nueva_publicacion_seguido",
    )
    db.session.add(notif)
    db.session.commit()
    notif_id = notif.id

    _login(client, u1.email)
    resp = client.post(f"/publicaciones/{pub.id}/eliminar", follow_redirects=False)
    assert resp.status_code == 302
    assert db.session.get(PublicacionCambio, pub.id) is None
    assert db.session.get(Notificacion, notif_id) is None
