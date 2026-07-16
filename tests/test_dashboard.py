"""Tests para el dashboard del usuario autenticado (Fase 3, paso 1)."""
from datetime import date, time, timedelta

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
from app.extensions import db
from app.services.registro import registrar_usuario

# PNG 1x1 transparente válido, usado como firma de prueba.
FIRMA_VALIDA = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4"
    "2mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _usuario_y_login(client, email="test@test.es"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    usuario = registrar_usuario(
        "Test User", email, "password123", "Hospital T", "Urgencias", cat.id
    )
    client.post("/auth/login", data={"email": email, "password": "password123"})
    return usuario


def _franja(grupo_intercambio_id):
    return FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_intercambio_id, nombre="Mañana").first()


def _publicacion(usuario, franja, fecha_cedida=date(2026, 8, 1), fecha_aceptada=date(2026, 8, 2)):
    pub = PublicacionCambio(usuario_id=usuario.id)
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=fecha_cedida, franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=fecha_aceptada, franja_horaria_id=franja.id))
    db.session.commit()
    return pub


def test_index_no_autenticado_muestra_landing(client, db):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Crear cuenta".encode() in resp.data


def test_index_autenticado_muestra_dashboard(client, db):
    _usuario_y_login(client)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Mis cambios publicados".encode() in resp.data


def test_dashboard_sin_publicaciones_muestra_estado_vacio(client, db):
    _usuario_y_login(client)
    # La pestaña por defecto es "Activos"; sin nada, muestra estado vacío
    resp = client.get("/")
    assert "No tienes".encode() in resp.data


def test_dashboard_activos_sin_publicaciones_muestra_estado_vacio(client, db):
    _usuario_y_login(client)
    resp = client.get("/?estado=abierta")
    assert "No tienes publicaciones activas".encode() in resp.data


def test_dashboard_muestra_publicaciones_propias(client, db):
    usuario = _usuario_y_login(client)
    franja = _franja(usuario.unidad.grupo_intercambio_id)
    _publicacion(usuario, franja)
    resp = client.get("/?estado=abierta")
    assert b"01/08/2026" in resp.data


def test_dashboard_tab_activos_es_default(client, db):
    """La pestaña Activos es la activa al entrar sin parámetro de estado."""
    _usuario_y_login(client)
    resp = client.get("/")
    assert b"estado-tab--active" in resp.data
    html = resp.data.decode()
    idx = html.find("estado-tab--active")
    assert "Activos" in html[idx:idx + 200]


def test_dashboard_tab_compatible_muestra_match_propuesto(client, db):
    """Pestaña Compatibles: muestra match en estado propuesto con botones de acción."""
    ana = _usuario_y_login(client, email="ana@test.es")
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "Hospital T", "Urgencias", cat.id)
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_ana = _publicacion(ana, franja, fecha_cedida=date(2026, 9, 1), fecha_aceptada=date(2026, 9, 2))
    pub_pedro = _publicacion(pedro, franja, fecha_cedida=date(2026, 9, 2), fecha_aceptada=date(2026, 9, 1))

    match = MatchCambio(tipo="directo_2", estado="propuesto")
    db.session.add(match)
    db.session.flush()
    tc_ana = pub_ana.turnos_cedidos[0]
    tc_pedro = pub_pedro.turnos_cedidos[0]
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_ana.id, turno_cedido_id=tc_ana.id))
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_pedro.id, turno_cedido_id=tc_pedro.id))
    db.session.commit()

    resp = client.get("/")  # default = compatible
    assert b"Pedro" in resp.data
    assert b"Confirmar" in resp.data
    assert b"Rechazar" in resp.data


def test_dashboard_activos_muestra_pub_sin_match(client, db):
    """La pestaña por defecto (Activos) muestra publicaciones sin match junto con los compatibles."""
    usuario = _usuario_y_login(client)
    franja = _franja(usuario.unidad.grupo_intercambio_id)
    _publicacion(usuario, franja, fecha_cedida=date(2026, 10, 1), fecha_aceptada=date(2026, 10, 2))

    resp = client.get("/")
    # La pub sin match aparece en Activos
    assert b'class="turno"' in resp.data
    assert b"01/10/2026" in resp.data


def test_dashboard_activos_muestra_solo_publicaciones_sin_match(client, db):
    """Pestaña Activos: solo publicaciones sin ningún match activo."""
    usuario = _usuario_y_login(client)
    franja = _franja(usuario.unidad.grupo_intercambio_id)
    _publicacion(usuario, franja, fecha_cedida=date(2026, 10, 1), fecha_aceptada=date(2026, 10, 2))
    pub_caducada = _publicacion(usuario, franja, fecha_cedida=date(2026, 11, 1), fecha_aceptada=date(2026, 11, 2))
    pub_caducada.estado = "caducada"
    db.session.commit()

    resp = client.get("/?estado=abierta")
    assert b"01/10/2026" in resp.data
    assert b"01/11/2026" not in resp.data


def test_dashboard_filtro_estado_caducada(client, db):
    usuario = _usuario_y_login(client)
    franja = _franja(usuario.unidad.grupo_intercambio_id)
    _publicacion(usuario, franja, fecha_cedida=date(2026, 10, 1), fecha_aceptada=date(2026, 10, 2))
    pub_caducada = _publicacion(usuario, franja, fecha_cedida=date(2026, 11, 1), fecha_aceptada=date(2026, 11, 2))
    pub_caducada.estado = "caducada"
    db.session.commit()

    resp = client.get("/?estado=caducada")
    assert b"01/11/2026" in resp.data
    assert b"01/10/2026" not in resp.data


def test_dashboard_filtro_estado_confirmada(client, db):
    usuario = _usuario_y_login(client)
    franja = _franja(usuario.unidad.grupo_intercambio_id)
    _publicacion(usuario, franja, fecha_cedida=date(2026, 10, 1), fecha_aceptada=date(2026, 10, 2))
    pub_confirmada = _publicacion(usuario, franja, fecha_cedida=date(2026, 11, 1), fecha_aceptada=date(2026, 11, 2))
    pub_confirmada.estado = "confirmada"
    db.session.commit()

    resp = client.get("/?estado=confirmada")
    assert b"01/11/2026" in resp.data
    assert b"01/10/2026" not in resp.data


def _setup_match_parcial(usuario_confirma, usuario_pendiente, franja):
    """Crea un match confirmado_parcial: usuario_confirma ya confirmó, usuario_pendiente no."""
    pub_a = PublicacionCambio(usuario_id=usuario_confirma.id)
    pub_b = PublicacionCambio(usuario_id=usuario_pendiente.id)
    db.session.add_all([pub_a, pub_b])
    db.session.flush()
    tc_a = TurnoCedido(publicacion_id=pub_a.id, fecha=date(2026, 10, 1), franja_horaria_id=franja.id)
    tc_b = TurnoCedido(publicacion_id=pub_b.id, fecha=date(2026, 10, 2), franja_horaria_id=franja.id)
    db.session.add_all([tc_a, tc_b])
    db.session.flush()
    match = MatchCambio(tipo="directo_2", estado="confirmado_parcial")
    db.session.add(match)
    db.session.flush()
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_a.id, turno_cedido_id=tc_a.id, confirmado=True))
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_b.id, turno_cedido_id=tc_b.id, confirmado=False))
    db.session.commit()
    return pub_a


def test_dashboard_tab_pendiente_muestra_match_confirmado_parcial(client, db):
    """Pestaña Pendientes: muestra matches en estado confirmado_parcial para ambas partes."""
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario("Ana", "ana@test.es", "password123", "Hospital T", "Urgencias", cat.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "Hospital T", "Urgencias", cat.id)
    db.session.commit()
    franja = _franja(ana.unidad.grupo_intercambio_id)
    _setup_match_parcial(ana, pedro, franja)  # confirmado_parcial

    # Ana (quien ya confirmó) ve la match card en pendiente
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    resp = client.get("/?estado=pendiente")
    assert b"01/10/2026" in resp.data

    # Pedro (quien aún no confirmó) también la ve en pendiente
    client.post("/auth/login", data={"email": "pedro@test.es", "password": "password123"})
    resp = client.get("/?estado=pendiente")
    assert b"02/10/2026" in resp.data


def test_dashboard_tab_pendiente_no_muestra_match_propuesto(client, db):
    """Un match propuesto (nadie confirmó) aparece en Compatibles, no en Pendientes."""
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario("Ana", "ana@test.es", "password123", "Hospital T", "Urgencias", cat.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "Hospital T", "Urgencias", cat.id)
    db.session.commit()
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_a = PublicacionCambio(usuario_id=ana.id)
    pub_b = PublicacionCambio(usuario_id=pedro.id)
    db.session.add_all([pub_a, pub_b])
    db.session.flush()
    tc_a = TurnoCedido(publicacion_id=pub_a.id, fecha=date(2026, 10, 1), franja_horaria_id=franja.id)
    tc_b = TurnoCedido(publicacion_id=pub_b.id, fecha=date(2026, 10, 2), franja_horaria_id=franja.id)
    db.session.add_all([tc_a, tc_b])
    db.session.flush()
    match = MatchCambio(tipo="directo_2", estado="propuesto")
    db.session.add(match)
    db.session.flush()
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_a.id, turno_cedido_id=tc_a.id, confirmado=False))
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_b.id, turno_cedido_id=tc_b.id, confirmado=False))
    db.session.commit()

    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    # En compatibles aparece
    resp_compat = client.get("/")
    assert b"01/10/2026" in resp_compat.data
    # En pendientes NO aparece
    resp_pend = client.get("/?estado=pendiente")
    assert b"01/10/2026" not in resp_pend.data


def test_dashboard_match_propuesto_permite_editar_la_publicacion(client, db):
    """Aunque una publicación tenga un match propuesto (incluso parcial: solo
    uno de varios turnos cedidos coincide), el usuario debe poder seguir
    editándola desde su match card, ya que otros turnos de la misma
    publicación pueden seguir sin resolver."""
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario("Ana", "ana@test.es", "password123", "Hospital T", "Urgencias", cat.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "Hospital T", "Urgencias", cat.id)
    db.session.commit()
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_a = PublicacionCambio(usuario_id=ana.id)
    pub_b = PublicacionCambio(usuario_id=pedro.id)
    db.session.add_all([pub_a, pub_b])
    db.session.flush()
    tc_a = TurnoCedido(publicacion_id=pub_a.id, fecha=date(2026, 10, 1), franja_horaria_id=franja.id)
    tc_b = TurnoCedido(publicacion_id=pub_b.id, fecha=date(2026, 10, 2), franja_horaria_id=franja.id)
    db.session.add_all([tc_a, tc_b])
    db.session.flush()
    match = MatchCambio(tipo="directo_2", estado="propuesto")
    db.session.add(match)
    db.session.flush()
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_a.id, turno_cedido_id=tc_a.id, confirmado=False))
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_b.id, turno_cedido_id=tc_b.id, confirmado=False))
    db.session.commit()

    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    resp = client.get("/")
    assert f'/publicaciones/{pub_a.id}/editar'.encode() in resp.data


def test_dashboard_match_confirmado_parcial_permite_editar_la_publicacion(client, db):
    """Igual que con un match propuesto: mientras el match no esté
    confirmado_total (aquí confirmado por una parte, pendiente por la otra),
    ambas partes deben poder editar su publicación desde la pestaña
    Pendientes."""
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario("Ana", "ana@test.es", "password123", "Hospital T", "Urgencias", cat.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "Hospital T", "Urgencias", cat.id)
    db.session.commit()
    franja = _franja(ana.unidad.grupo_intercambio_id)
    pub_a = _setup_match_parcial(ana, pedro, franja)

    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    resp = client.get("/?estado=pendiente")
    assert f'/publicaciones/{pub_a.id}/editar'.encode() in resp.data


def test_dashboard_activos_excluye_pubs_con_match_confirmado_parcial(client, db):
    """La pestaña Activos no muestra la tarjeta de publicación de una pub con
    match confirmado_parcial: ese caso vive solo en Pendientes, sin cambios."""
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario("Ana", "ana@test.es", "password123", "Hospital T", "Urgencias", cat.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "Hospital T", "Urgencias", cat.id)
    db.session.commit()
    franja = _franja(ana.unidad.grupo_intercambio_id)

    # pub con match en confirmado_parcial → debe aparecer en pendiente, no en activos
    _setup_match_parcial(ana, pedro, franja)
    # pub sin match → debe aparecer en activos
    pub_sin_match = _publicacion(ana, franja, fecha_cedida=date(2026, 12, 1), fecha_aceptada=date(2026, 12, 2))

    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    resp_activos = client.get("/?estado=abierta")
    # Las pub cards usan <span class="turno">; las match cards no.
    assert b'class="turno">01/10/2026' not in resp_activos.data   # confirmado_parcial → fuera de activos
    assert b'class="turno">01/12/2026' in resp_activos.data        # sin match → en activos


def test_dashboard_activos_muestra_pub_original_y_tarjeta_de_match_propuesto(client, db):
    """Con un match propuesto (aún sin confirmar por nadie), Activos debe
    mostrar DOS tarjetas distintas: la publicación original (editable, con
    todos sus turnos abiertos) y, además, la tarjeta del match propuesto
    (sin botón Editar — solo Confirmar/Rechazar)."""
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario("Ana", "ana@test.es", "password123", "Hospital T", "Urgencias", cat.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "Hospital T", "Urgencias", cat.id)
    db.session.commit()
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_a = PublicacionCambio(usuario_id=ana.id)
    pub_b = PublicacionCambio(usuario_id=pedro.id)
    db.session.add_all([pub_a, pub_b])
    db.session.flush()
    tc_a = TurnoCedido(publicacion_id=pub_a.id, fecha=date(2026, 10, 1), franja_horaria_id=franja.id)
    tc_b = TurnoCedido(publicacion_id=pub_b.id, fecha=date(2026, 10, 2), franja_horaria_id=franja.id)
    db.session.add_all([tc_a, tc_b])
    db.session.flush()
    match = MatchCambio(tipo="directo_2", estado="propuesto")
    db.session.add(match)
    db.session.flush()
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_a.id, turno_cedido_id=tc_a.id, confirmado=False))
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_b.id, turno_cedido_id=tc_b.id, confirmado=False))
    db.session.commit()

    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    resp = client.get("/")
    html = resp.data.decode()

    # Tarjeta original de la publicación, con su turno y el botón Editar.
    assert 'class="turno">01/10/2026' in html
    editar_url = f"/publicaciones/{pub_a.id}/editar"
    assert editar_url in html
    # El botón Editar aparece una sola vez: solo en la tarjeta original,
    # no en la tarjeta de match.
    assert html.count(editar_url) == 1
    # La tarjeta de match sigue mostrando Confirmar/Rechazar.
    assert "Confirmar" in html and "Rechazar" in html


def test_dashboard_tab_activos_conteo_con_match_propuesto(client, db):
    """El contador de Activos incluye el match propuesto (compatible)."""
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario("Ana", "ana@test.es", "password123", "Hospital T", "Urgencias", cat.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "Hospital T", "Urgencias", cat.id)
    db.session.commit()
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_a = PublicacionCambio(usuario_id=ana.id)
    pub_b = PublicacionCambio(usuario_id=pedro.id)
    db.session.add_all([pub_a, pub_b])
    db.session.flush()
    tc_a = TurnoCedido(publicacion_id=pub_a.id, fecha=date(2026, 10, 1), franja_horaria_id=franja.id)
    tc_b = TurnoCedido(publicacion_id=pub_b.id, fecha=date(2026, 10, 2), franja_horaria_id=franja.id)
    db.session.add_all([tc_a, tc_b])
    db.session.flush()
    match = MatchCambio(tipo="directo_2", estado="propuesto")
    db.session.add(match)
    db.session.flush()
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_a.id, turno_cedido_id=tc_a.id, confirmado=False))
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_b.id, turno_cedido_id=tc_b.id, confirmado=False))
    db.session.commit()

    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    resp = client.get("/")
    html = resp.data.decode()
    assert "Activos" in html
    # La publicación original (editable) y su match propuesto se muestran
    # como dos tarjetas distintas en Activos, así que el contador cuenta 2.
    assert "(2)" in html


def test_dashboard_no_muestra_publicaciones_ajenas(client, db):
    _usuario_y_login(client, email="ana@test.es")
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    otro = registrar_usuario("Otro", "otro@test.es", "password123", "Hospital T", "Urgencias", cat.id)
    franja = _franja(otro.unidad.grupo_intercambio_id)
    _publicacion(otro, franja)
    resp = client.get("/?estado=abierta")
    assert b"No tienes publicaciones" in resp.data
    assert b"01/08/2026" not in resp.data


def test_dashboard_confirmados_muestra_nombre_partner(client, db):
    """En la pestaña confirmados, se muestra el nombre del compañero del intercambio."""
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario("Ana", "ana@test.es", "password123", "H1", "Urgencias", cat.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "H1", "Urgencias", cat.id)
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_ana = PublicacionCambio(usuario_id=ana.id, estado="confirmada")
    pub_pedro = PublicacionCambio(usuario_id=pedro.id, estado="confirmada")
    db.session.add_all([pub_ana, pub_pedro])
    db.session.flush()
    tc_ana = TurnoCedido(publicacion_id=pub_ana.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id, estado="resuelto")
    tc_pedro = TurnoCedido(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id, estado="resuelto")
    db.session.add_all([tc_ana, tc_pedro])
    db.session.flush()
    match = MatchCambio(tipo="directo_2", estado="confirmado_total")
    db.session.add(match)
    db.session.flush()
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_ana.id, turno_cedido_id=tc_ana.id, confirmado=True))
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_pedro.id, turno_cedido_id=tc_pedro.id, confirmado=True))
    db.session.commit()

    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    resp = client.get("/?estado=confirmada")
    assert b"Pedro" in resp.data


def test_contador_activos_ignora_self_matches(client, db):
    """El contador de Activos no cuenta matches donde ambas publicaciones son del mismo usuario."""
    usuario = _usuario_y_login(client)
    franja = _franja(usuario.unidad.grupo_intercambio_id)
    pub1 = _publicacion(usuario, franja, fecha_cedida=date(2026, 9, 1), fecha_aceptada=date(2026, 9, 2))
    pub2 = _publicacion(usuario, franja, fecha_cedida=date(2026, 9, 2), fecha_aceptada=date(2026, 9, 1))
    # Crea un self-match artificial entre las dos publicaciones del mismo usuario
    match = MatchCambio(tipo="directo_2", estado="propuesto")
    db.session.add(match)
    db.session.flush()
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub1.id))
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub2.id))
    db.session.commit()

    resp = client.get("/")
    html = resp.data.decode()
    assert "Activos" in html
    # self-match no cuenta como compatible, y pubs con match propuesto se excluyen de abierta → (0)
    assert "(0)" in html


def test_dashboard_tabs_muestran_conteos(client, db):
    """Cada pestaña muestra entre paréntesis el número de publicaciones que contiene."""
    usuario = _usuario_y_login(client)
    franja = _franja(usuario.unidad.grupo_intercambio_id)
    # 2 activas (sin match)
    _publicacion(usuario, franja, fecha_cedida=date(2026, 10, 1), fecha_aceptada=date(2026, 10, 2))
    _publicacion(usuario, franja, fecha_cedida=date(2026, 10, 3), fecha_aceptada=date(2026, 10, 4))
    # 1 confirmada
    pub_conf = _publicacion(usuario, franja, fecha_cedida=date(2026, 11, 1), fecha_aceptada=date(2026, 11, 2))
    pub_conf.estado = "confirmada"
    # 1 caducada
    pub_cad = _publicacion(usuario, franja, fecha_cedida=date(2026, 12, 1), fecha_aceptada=date(2026, 12, 2))
    pub_cad.estado = "caducada"
    db.session.commit()

    resp = client.get("/")
    assert b"(2)" in resp.data  # activas
    assert b"(1)" in resp.data  # confirmadas y caducadas comparten el (1)


def test_dashboard_confirmada_muestra_match_de_pub_parcialmente_resuelta(client, db):
    """La pestaña Confirmados muestra matches confirmado_total aunque la pub sea parcialmente_resuelta."""
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario("Ana", "ana@test.es", "password123", "H1", "Urgencias", cat.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "H1", "Urgencias", cat.id)
    franja = _franja(ana.unidad.grupo_intercambio_id)

    # pub_ana tiene 2 turnos cedidos: 1 resuelto y 1 abierto → parcialmente_resuelta
    pub_ana = PublicacionCambio(usuario_id=ana.id, estado="parcialmente_resuelta")
    db.session.add(pub_ana)
    db.session.flush()
    tc_ana_resuelto = TurnoCedido(
        publicacion_id=pub_ana.id, fecha=date(2026, 9, 1),
        franja_horaria_id=franja.id, estado="resuelto",
    )
    tc_ana_abierto = TurnoCedido(
        publicacion_id=pub_ana.id, fecha=date(2026, 9, 2),
        franja_horaria_id=franja.id,
    )
    ta_ana_resuelto = TurnoAceptado(
        publicacion_id=pub_ana.id, fecha=date(2026, 9, 10),
        franja_horaria_id=franja.id, estado="resuelto",
    )
    db.session.add_all([tc_ana_resuelto, tc_ana_abierto, ta_ana_resuelto])

    pub_pedro = PublicacionCambio(usuario_id=pedro.id, estado="confirmada")
    db.session.add(pub_pedro)
    db.session.flush()
    tc_pedro = TurnoCedido(
        publicacion_id=pub_pedro.id, fecha=date(2026, 9, 10),
        franja_horaria_id=franja.id, estado="resuelto",
    )
    db.session.add(tc_pedro)

    match = MatchCambio(tipo="directo_2", estado="confirmado_total")
    db.session.add(match)
    db.session.flush()
    db.session.add(MatchParticipacion(
        match_id=match.id, publicacion_id=pub_ana.id,
        turno_cedido_id=tc_ana_resuelto.id, turno_aceptado_id=ta_ana_resuelto.id,
        confirmado=True,
    ))
    db.session.add(MatchParticipacion(
        match_id=match.id, publicacion_id=pub_pedro.id,
        turno_cedido_id=tc_pedro.id, confirmado=True,
    ))
    db.session.commit()

    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    resp = client.get("/?estado=confirmada")
    html = resp.data.decode()

    # La tarjeta del match confirmado debe aparecer con el nombre del partner
    assert "Pedro" in html
    # y la fecha del turno que Ana cedió en ese match
    assert "01/09/2026" in html


def test_dashboard_activos_oculta_turnos_resueltos(client, db):
    """En el dashboard, una pub parcialmente_resuelta solo muestra los turnos aún abiertos."""
    usuario = _usuario_y_login(client)
    franja = _franja(usuario.unidad.grupo_intercambio_id)

    pub = PublicacionCambio(usuario_id=usuario.id, estado="parcialmente_resuelta")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(
        publicacion_id=pub.id, fecha=date(2026, 10, 1), franja_horaria_id=franja.id,
    ))
    db.session.add(TurnoCedido(
        publicacion_id=pub.id, fecha=date(2026, 10, 2), franja_horaria_id=franja.id,
        estado="resuelto",
    ))
    db.session.add(TurnoAceptado(
        publicacion_id=pub.id, fecha=date(2026, 11, 1), franja_horaria_id=franja.id,
    ))
    db.session.add(TurnoAceptado(
        publicacion_id=pub.id, fecha=date(2026, 11, 2), franja_horaria_id=franja.id,
        estado="resuelto",
    ))
    db.session.commit()

    resp = client.get("/")
    html = resp.data.decode()
    assert "01/10/2026" in html   # cedido abierto → visible
    assert "02/10/2026" not in html  # cedido resuelto → oculto
    assert "01/11/2026" in html   # aceptado abierto → visible
    assert "02/11/2026" not in html  # aceptado resuelto → oculto


def test_confirmar_total_resuelve_turno_aceptado(client, db):
    """Al confirmar totalmente un match cambio↔cambio, el turno_aceptado vinculado queda resuelto."""
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario("Ana", "ana@test.es", "password123", "H1", "Urgencias", cat.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "H1", "Urgencias", cat.id)
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_ana = PublicacionCambio(usuario_id=ana.id)
    pub_pedro = PublicacionCambio(usuario_id=pedro.id)
    db.session.add_all([pub_ana, pub_pedro])
    db.session.flush()

    tc_ana = TurnoCedido(publicacion_id=pub_ana.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id)
    tc_pedro = TurnoCedido(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id)
    ta_ana = TurnoAceptado(publicacion_id=pub_ana.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id)
    ta_pedro = TurnoAceptado(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id)
    db.session.add_all([tc_ana, tc_pedro, ta_ana, ta_pedro])
    db.session.flush()

    match = MatchCambio(tipo="directo_2", estado="propuesto")
    db.session.add(match)
    db.session.flush()
    db.session.add(MatchParticipacion(
        match_id=match.id, publicacion_id=pub_ana.id,
        turno_cedido_id=tc_ana.id, turno_aceptado_id=ta_ana.id,
    ))
    db.session.add(MatchParticipacion(
        match_id=match.id, publicacion_id=pub_pedro.id,
        turno_cedido_id=tc_pedro.id, turno_aceptado_id=ta_pedro.id,
    ))
    db.session.commit()

    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    client.post(f"/matches/{match.id}/confirmar", data={"firma": FIRMA_VALIDA})
    client.get("/auth/logout")
    client.post("/auth/login", data={"email": "pedro@test.es", "password": "password123"})
    client.post(f"/matches/{match.id}/confirmar", data={"firma": FIRMA_VALIDA})

    db.session.refresh(ta_ana)
    db.session.refresh(ta_pedro)
    assert ta_ana.estado == "resuelto"
    assert ta_pedro.estado == "resuelto"


def test_dashboard_junte_wa_mensaje_incluye_semana_y_dias(client, db):
    """El enlace de WhatsApp de un junte activo incluye la semana, el nº de noches,
    los días a trabajar y los días a librar."""
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario("Ana", "ana@test.es", "pass123", "H1", "Urgencias", cat.id)
    db.session.commit()
    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=ana.unidad.grupo_intercambio_id
    ).first()

    # 2026-08-03 es lunes. LMVD: cede Vie(+4) y Dom(+6), recibe Mar(+1) y Jue(+3)
    lunes = date(2026, 8, 3)
    pub = PublicacionCambio(usuario_id=ana.id, tipo="junte")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=lunes + timedelta(days=4), franja_horaria_id=franja.id))
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=lunes + timedelta(days=6), franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=lunes + timedelta(days=1), franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=lunes + timedelta(days=3), franja_horaria_id=franja.id))
    db.session.commit()

    client.post("/auth/login", data={"email": "ana@test.es", "password": "pass123"})
    resp = client.get("/")
    html = resp.data.decode()

    # El href del botón Compartir lleva el texto URL-encoded
    # "4 noches" → "4%20noches", "Busco trabajar" → "Busco%20trabajar", etc.
    assert "4%20noches" in html
    assert "Busco%20trabajar" in html
    assert "Busco%20librar" in html
    # La semana del 03/08/2026 ("03%2F08%2F2026")
    assert "03%2F08%2F2026" in html
