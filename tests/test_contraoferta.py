"""Tests de la funcionalidad de contraoferta (backlog ítem 2)."""
from datetime import date

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
from app.services.registro import registrar_usuario


def _usuario(nombre, email, password="password123"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario(nombre, email, password, "Hospital T", "Urgencias", cat.id)


def _franja(grupo_id, nombre="Mañana"):
    return FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id, nombre=nombre).first()


def _franja_tarde(grupo_id):
    return FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id, nombre="Tarde").first()


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


def _pub_regalo(usuario, franja, fecha):
    pub = PublicacionCambio(usuario_id=usuario.id, tipo="regalo")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=fecha, franja_horaria_id=franja.id))
    db.session.commit()
    return pub


# --- Ruta GET ---

def test_contraoferta_requiere_login(client, db):
    """La ruta GET /cambios/<id>/contraoferta redirige al login si no está autenticado."""
    ana = _usuario("Ana", "ana@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)
    pub = _pub_cambio(ana, franja, date(2026, 9, 3), date(2026, 9, 4))
    resp = client.get(f"/cambios/{pub.id}/contraoferta", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_contraoferta_solo_tipo_cambio(client, db):
    """La ruta de contraoferta devuelve 404 para publicaciones que no son tipo cambio."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)
    pub_regalo = _pub_regalo(ana, franja, date(2026, 9, 3))

    _login(client, "pedro@test.es")
    resp = client.get(f"/cambios/{pub_regalo.id}/contraoferta")
    assert resp.status_code == 404


def test_contraoferta_no_disponible_propia_publicacion(client, db):
    """El autor no puede hacer contraoferta a su propia publicación."""
    ana = _usuario("Ana", "ana@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)
    pub = _pub_cambio(ana, franja, date(2026, 9, 3), date(2026, 9, 4))

    _login(client, "ana@test.es")
    resp = client.get(f"/cambios/{pub.id}/contraoferta", follow_redirects=True)
    html = resp.data.decode()
    assert "propia" in html.lower() or resp.status_code in (302, 403)


def test_contraoferta_get_muestra_formulario(client, db):
    """GET /cambios/<id>/contraoferta muestra un formulario con cedidos y aceptados."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)
    pub = _pub_cambio(ana, franja, date(2026, 9, 3), date(2026, 9, 4))

    _login(client, "pedro@test.es")
    resp = client.get(f"/cambios/{pub.id}/contraoferta")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "fecha_cedida_0" in html or "contraoferta" in html.lower()


# --- Ruta POST ---

def test_contraoferta_crea_publicacion_cambio(client, db):
    """POST válida crea una nueva publicación de tipo cambio para Pedro."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)
    pub_ana = _pub_cambio(ana, franja, date(2026, 9, 3), date(2026, 9, 4))

    _login(client, "pedro@test.es")
    resp = client.post(
        f"/cambios/{pub_ana.id}/contraoferta",
        data={
            "fecha_cedida_0": "2026-09-04",
            "franja_cedida_0": str(franja.id),
            "fecha_aceptada_0": "2026-09-08",
            "franja_aceptada_0": str(franja.id),
            "mensaje": "¿Te parece bien?",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    pub_pedro = PublicacionCambio.query.filter_by(
        usuario_id=pedro.id, tipo="cambio"
    ).first()
    assert pub_pedro is not None
    assert len(pub_pedro.turnos_cedidos) == 1
    assert pub_pedro.turnos_cedidos[0].fecha == date(2026, 9, 4)
    assert pub_pedro.mensaje == "¿Te parece bien?"


def test_contraoferta_notifica_a_autor_original(client, db):
    """La contraoferta crea una Notificacion de tipo 'contraoferta' para Ana."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)
    pub_ana = _pub_cambio(ana, franja, date(2026, 9, 3), date(2026, 9, 4))

    _login(client, "pedro@test.es")
    client.post(
        f"/cambios/{pub_ana.id}/contraoferta",
        data={
            "fecha_cedida_0": "2026-09-04",
            "franja_cedida_0": str(franja.id),
            "fecha_aceptada_0": "2026-09-08",
            "franja_aceptada_0": str(franja.id),
            "mensaje": "Propuesta",
        },
    )
    notif = Notificacion.query.filter_by(usuario_id=ana.id, tipo="contraoferta").first()
    assert notif is not None
    assert notif.publicacion_id is not None


def test_contraoferta_rechaza_sin_solapamiento(client, db):
    """Si ningún turno de la contraoferta coincide con la publicación original, da error."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)
    pub_ana = _pub_cambio(ana, franja, date(2026, 9, 3), date(2026, 9, 4))

    _login(client, "pedro@test.es")
    resp = client.post(
        f"/cambios/{pub_ana.id}/contraoferta",
        data={
            # día 10 y día 11 — ninguno coincide con los de Ana (3 y 4)
            "fecha_cedida_0": "2026-09-10",
            "franja_cedida_0": str(franja.id),
            "fecha_aceptada_0": "2026-09-11",
            "franja_aceptada_0": str(franja.id),
            "mensaje": "Propuesta",
        },
        follow_redirects=True,
    )
    html = resp.data.decode()
    assert "coincidir" in html.lower() or "solapamiento" in html.lower() or "coincid" in html.lower()
    assert PublicacionCambio.query.filter_by(usuario_id=pedro.id).count() == 0


def test_contraoferta_acepta_solapamiento_con_aceptado_original(client, db):
    """Solapamiento con un aceptado del original es suficiente para pasar la validación."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)
    franja_tarde = _franja_tarde(ana.unidad.grupo_intercambio_id)
    pub_ana = _pub_cambio(ana, franja, date(2026, 9, 3), date(2026, 9, 4))

    _login(client, "pedro@test.es")
    # Pedro cede 04/09 (coincide con el aceptado de Ana), acepta 08/09 (no coincide con nada)
    resp = client.post(
        f"/cambios/{pub_ana.id}/contraoferta",
        data={
            "fecha_cedida_0": "2026-09-04",
            "franja_cedida_0": str(franja.id),
            "fecha_aceptada_0": "2026-09-08",
            "franja_aceptada_0": str(franja_tarde.id),
            "mensaje": "¿Aceptas?",
        },
        follow_redirects=True,
    )
    assert PublicacionCambio.query.filter_by(usuario_id=pedro.id).count() == 1


def test_contraoferta_acepta_solapamiento_con_cedido_original(client, db):
    """Solapamiento con un cedido del original (Pedro ofrece trabajar lo que Ana quiere librar)."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)
    franja_tarde = _franja_tarde(ana.unidad.grupo_intercambio_id)
    pub_ana = _pub_cambio(ana, franja, date(2026, 9, 3), date(2026, 9, 4))

    _login(client, "pedro@test.es")
    # Pedro acepta 03/09 (coincide con el cedido de Ana), cede 08/09
    resp = client.post(
        f"/cambios/{pub_ana.id}/contraoferta",
        data={
            "fecha_cedida_0": "2026-09-08",
            "franja_cedida_0": str(franja_tarde.id),
            "fecha_aceptada_0": "2026-09-03",
            "franja_aceptada_0": str(franja.id),
            "mensaje": "Puedo cubrirte",
        },
        follow_redirects=True,
    )
    assert PublicacionCambio.query.filter_by(usuario_id=pedro.id).count() == 1


def test_contraoferta_crea_match_si_es_bilateral(client, db):
    """Si la contraoferta forma un match completo con el original, se crea el match."""
    from app.models import MatchCambio

    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)
    pub_ana = _pub_cambio(ana, franja, date(2026, 9, 3), date(2026, 9, 4))

    _login(client, "pedro@test.es")
    # Pedro cede 03/09 (= cedido de Ana) y acepta 04/09 (= aceptado de Ana) → match bilateral
    client.post(
        f"/cambios/{pub_ana.id}/contraoferta",
        data={
            "fecha_cedida_0": "2026-09-04",
            "franja_cedida_0": str(franja.id),
            "fecha_aceptada_0": "2026-09-03",
            "franja_aceptada_0": str(franja.id),
            "mensaje": "¿Hacemos el cambio?",
        },
    )
    assert MatchCambio.query.count() == 1


def test_contraoferta_rechaza_sin_cedidos(client, db):
    """La contraoferta sin turnos cedidos da error."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)
    pub_ana = _pub_cambio(ana, franja, date(2026, 9, 3), date(2026, 9, 4))

    _login(client, "pedro@test.es")
    resp = client.post(
        f"/cambios/{pub_ana.id}/contraoferta",
        data={
            "fecha_aceptada_0": "2026-09-04",
            "franja_aceptada_0": str(franja.id),
            "mensaje": "Sin cedidos",
        },
        follow_redirects=True,
    )
    assert PublicacionCambio.query.filter_by(usuario_id=pedro.id).count() == 0
