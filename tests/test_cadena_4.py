"""Tests para matching a 4 bandas: motor de búsqueda y creación de matches."""
from datetime import date, timedelta

import pytest

from app.extensions import db
from app.matching.service import buscar_cadenas_4_para, crear_match_cadena_4
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


# --- Helpers ---

def _usuario(nombre, email, hospital="H1", unidad="Urgencias"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario(nombre, email, "password123", hospital, unidad, cat.id)


def _franja(grupo_id, nombre="Mañana"):
    return FranjaHoraria.query.filter_by(
        grupo_intercambio_id=grupo_id, nombre=nombre
    ).first()


def _pub(usuario, fecha_cede, franja_cede, fecha_acepta, franja_acepta, tipo="cambio"):
    pub = PublicacionCambio(usuario_id=usuario.id, tipo=tipo)
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(
        publicacion_id=pub.id, fecha=fecha_cede, franja_horaria_id=franja_cede.id
    ))
    db.session.add(TurnoAceptado(
        publicacion_id=pub.id, fecha=fecha_acepta, franja_horaria_id=franja_acepta.id
    ))
    db.session.commit()
    return pub


def _setup_ciclo(db):
    """
    Crea Ana, Pedro, María y Luis con publicaciones que forman el ciclo
    Ana→Pedro→María→Luis→Ana:
      - Ana cede mañana_1  → Pedro la acepta
      - Pedro cede tarde_2 → María la acepta
      - María cede noche_3 → Luis la acepta
      - Luis cede mañana_4 → Ana la acepta
    """
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    maria = _usuario("María", "maria@test.es")
    luis = _usuario("Luis", "luis@test.es")

    gid = ana.unidad.grupo_intercambio_id
    fr_m = _franja(gid, "Mañana")
    fr_t = _franja(gid, "Tarde")
    fr_n = _franja(gid, "Noche")

    # Ana cede mañana_1 (Pedro acepta), acepta mañana_4 (Luis cede)
    pub_ana = _pub(ana, date(2026, 7, 1), fr_m, date(2026, 7, 4), fr_m)
    # Pedro cede tarde_2 (María acepta), acepta mañana_1 (Ana cede)
    pub_pedro = _pub(pedro, date(2026, 7, 2), fr_t, date(2026, 7, 1), fr_m)
    # María cede noche_3 (Luis acepta), acepta tarde_2 (Pedro cede)
    pub_maria = _pub(maria, date(2026, 7, 3), fr_n, date(2026, 7, 2), fr_t)
    # Luis cede mañana_4 (Ana acepta), acepta noche_3 (María cede)
    pub_luis = _pub(luis, date(2026, 7, 4), fr_m, date(2026, 7, 3), fr_n)

    return pub_ana, pub_pedro, pub_maria, pub_luis, ana, pedro, maria, luis


# --- buscar_cadenas_4_para ---

def test_detecta_cadena_4_basica(db):
    """El servicio detecta el ciclo Ana→Pedro→María→Luis→Ana."""
    pub_ana, pub_pedro, pub_maria, pub_luis, *_ = _setup_ciclo(db)

    cadenas = buscar_cadenas_4_para(pub_ana)

    assert len(cadenas) == 1
    ids_encontrados = {cadenas[0][0].id, cadenas[0][1].id, cadenas[0][2].id}
    assert ids_encontrados == {pub_pedro.id, pub_maria.id, pub_luis.id}


def test_cadena_4_no_detecta_ciclo_incompleto(db):
    """Si el ciclo no se cierra, no hay cadena."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    maria = _usuario("María", "maria@test.es")
    luis = _usuario("Luis", "luis@test.es")

    gid = ana.unidad.grupo_intercambio_id
    fr_m = _franja(gid, "Mañana")
    fr_t = _franja(gid, "Tarde")
    fr_n = _franja(gid, "Noche")

    pub_ana = _pub(ana, date(2026, 7, 1), fr_m, date(2026, 7, 4), fr_m)
    _pub(pedro, date(2026, 7, 2), fr_t, date(2026, 7, 1), fr_m)
    _pub(maria, date(2026, 7, 3), fr_n, date(2026, 7, 2), fr_t)
    # Luis acepta mañana_1 en vez de noche_3 → el ciclo María→Luis se rompe
    _pub(luis, date(2026, 7, 4), fr_m, date(2026, 7, 1), fr_m)

    assert buscar_cadenas_4_para(pub_ana) == []


def test_cadena_4_no_detecta_cadena_3_como_cadena_4(db):
    """Un ciclo cerrado de 3 (C→A directo) no se detecta como cadena de 4."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    maria = _usuario("María", "maria@test.es")

    gid = ana.unidad.grupo_intercambio_id
    fr_m = _franja(gid, "Mañana")
    fr_t = _franja(gid, "Tarde")
    fr_n = _franja(gid, "Noche")

    pub_ana = _pub(ana, date(2026, 7, 1), fr_m, date(2026, 7, 3), fr_n)
    _pub(pedro, date(2026, 7, 2), fr_t, date(2026, 7, 1), fr_m)
    _pub(maria, date(2026, 7, 3), fr_n, date(2026, 7, 2), fr_t)

    assert buscar_cadenas_4_para(pub_ana) == []


def test_cadena_4_respeta_filtro_de_categoria(db):
    """Usuarios de distinta categoría no forman cadena."""
    insertar_categorias_semilla()
    cat_enf = Categoria.query.filter_by(nombre="Enfermería").first()
    cat_aux = Categoria.query.filter_by(nombre="Auxiliar de enfermería (TCAE)").first()

    ana = registrar_usuario("Ana", "ana@test.es", "password123", "H1", "Urgencias", cat_enf.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "H1", "Urgencias", cat_enf.id)
    maria = registrar_usuario("María", "maria@test.es", "password123", "H1", "Urgencias", cat_enf.id)
    luis = registrar_usuario("Luis", "luis@test.es", "password123", "H1", "Urgencias", cat_aux.id)

    gid = ana.unidad.grupo_intercambio_id
    fr_m = _franja(gid, "Mañana")
    fr_t = _franja(gid, "Tarde")
    fr_n = _franja(gid, "Noche")

    pub_ana = _pub(ana, date(2026, 7, 1), fr_m, date(2026, 7, 4), fr_m)
    _pub(pedro, date(2026, 7, 2), fr_t, date(2026, 7, 1), fr_m)
    _pub(maria, date(2026, 7, 3), fr_n, date(2026, 7, 2), fr_t)
    _pub(luis, date(2026, 7, 4), fr_m, date(2026, 7, 3), fr_n)

    # Luis es de distinta categoría → no forma cadena
    assert buscar_cadenas_4_para(pub_ana) == []


def test_cadena_4_no_duplica_si_ya_existe(db):
    """Si el match ya existe para el cuarteto, no lo devuelve de nuevo."""
    pub_ana, pub_pedro, pub_maria, pub_luis, *_ = _setup_ciclo(db)

    crear_match_cadena_4(pub_ana, pub_pedro, pub_maria, pub_luis)

    cadenas = buscar_cadenas_4_para(pub_ana)
    assert cadenas == []


def test_cadena_4_solo_tipo_cambio(db):
    """Las cadenas de 4 solo se buscan para publicaciones de tipo 'cambio'."""
    ana = _usuario("Ana", "ana@test.es")
    gid = ana.unidad.grupo_intercambio_id
    fr_m = _franja(gid, "Mañana")
    fr_t = _franja(gid, "Tarde")

    pub_junte = PublicacionCambio(usuario_id=ana.id, tipo="junte")
    db.session.add(pub_junte)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub_junte.id, fecha=date(2026, 7, 1), franja_horaria_id=fr_m.id))
    db.session.add(TurnoAceptado(publicacion_id=pub_junte.id, fecha=date(2026, 7, 2), franja_horaria_id=fr_t.id))
    db.session.commit()

    assert buscar_cadenas_4_para(pub_junte) == []


# --- crear_match_cadena_4 ---

def test_crear_match_cadena_4_tipo_y_estado(db):
    pub_ana, pub_pedro, pub_maria, pub_luis, *_ = _setup_ciclo(db)

    match = crear_match_cadena_4(pub_ana, pub_pedro, pub_maria, pub_luis)

    assert match is not None
    assert match.tipo == "cadena_4"
    assert match.estado == "propuesto"


def test_crear_match_cadena_4_genera_cuatro_participaciones(db):
    pub_ana, pub_pedro, pub_maria, pub_luis, *_ = _setup_ciclo(db)

    match = crear_match_cadena_4(pub_ana, pub_pedro, pub_maria, pub_luis)

    parts = MatchParticipacion.query.filter_by(match_id=match.id).all()
    assert len(parts) == 4
    pub_ids = {p.publicacion_id for p in parts}
    assert pub_ids == {pub_ana.id, pub_pedro.id, pub_maria.id, pub_luis.id}


def test_crear_match_cadena_4_cada_participacion_tiene_turno_cedido(db):
    pub_ana, pub_pedro, pub_maria, pub_luis, *_ = _setup_ciclo(db)

    match = crear_match_cadena_4(pub_ana, pub_pedro, pub_maria, pub_luis)

    for p in match.participaciones:
        assert p.turno_cedido_id is not None


def test_crear_match_cadena_4_genera_cuatro_notificaciones(db):
    pub_ana, pub_pedro, pub_maria, pub_luis, ana, pedro, maria, luis = _setup_ciclo(db)

    match = crear_match_cadena_4(pub_ana, pub_pedro, pub_maria, pub_luis)

    notifs = Notificacion.query.filter_by(match_id=match.id, tipo="nuevo_match").all()
    assert len(notifs) == 4
    usuarios = {n.usuario_id for n in notifs}
    assert usuarios == {ana.id, pedro.id, maria.id, luis.id}


def test_cadena_4_confirmacion_total_requiere_cuatro(db):
    """El match solo se cierra cuando los cuatro confirman."""
    from app.services.matches import confirmar_participacion

    pub_ana, pub_pedro, pub_maria, pub_luis, ana, pedro, maria, luis = _setup_ciclo(db)
    match = crear_match_cadena_4(pub_ana, pub_pedro, pub_maria, pub_luis)

    confirmar_participacion(match, ana.id)
    assert match.estado == "confirmado_parcial"

    confirmar_participacion(match, pedro.id)
    assert match.estado == "confirmado_parcial"

    confirmar_participacion(match, maria.id)
    assert match.estado == "confirmado_parcial"

    confirmar_participacion(match, luis.id)
    assert match.estado == "confirmado_total"


def test_cadena_4_publicacion_se_confirma_cuando_todos_confirman(db):
    """Las publicaciones de los 4 pasan a 'confirmada' tras confirmación total."""
    from app.services.matches import confirmar_participacion

    pub_ana, pub_pedro, pub_maria, pub_luis, ana, pedro, maria, luis = _setup_ciclo(db)
    match = crear_match_cadena_4(pub_ana, pub_pedro, pub_maria, pub_luis)

    confirmar_participacion(match, ana.id)
    confirmar_participacion(match, pedro.id)
    confirmar_participacion(match, maria.id)
    confirmar_participacion(match, luis.id)

    db.session.refresh(pub_ana)
    db.session.refresh(pub_pedro)
    db.session.refresh(pub_maria)
    db.session.refresh(pub_luis)

    assert pub_ana.estado == "confirmada"
    assert pub_pedro.estado == "confirmada"
    assert pub_maria.estado == "confirmada"
    assert pub_luis.estado == "confirmada"


# --- Integración con la ruta de publicar ---

def test_publicar_crea_match_cadena_4_cuando_hay_ciclo(client, db):
    """Al publicar la cuarta publicación que cierra el ciclo se crea un cadena_4 match."""
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario("Ana", "ana@test.es", "password123", "H1", "Urgencias", cat.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "H1", "Urgencias", cat.id)
    maria = registrar_usuario("María", "maria@test.es", "password123", "H1", "Urgencias", cat.id)
    luis = registrar_usuario("Luis", "luis@test.es", "password123", "H1", "Urgencias", cat.id)

    gid = ana.unidad.grupo_intercambio_id
    fr_m = FranjaHoraria.query.filter_by(grupo_intercambio_id=gid, nombre="Mañana").first()
    fr_t = FranjaHoraria.query.filter_by(grupo_intercambio_id=gid, nombre="Tarde").first()
    fr_n = FranjaHoraria.query.filter_by(grupo_intercambio_id=gid, nombre="Noche").first()

    dia1 = date.today() + timedelta(days=1)
    dia2 = date.today() + timedelta(days=2)
    dia3 = date.today() + timedelta(days=3)
    dia4 = date.today() + timedelta(days=4)

    _pub(ana, dia1, fr_m, dia4, fr_m)
    _pub(pedro, dia2, fr_t, dia1, fr_m)
    _pub(maria, dia3, fr_n, dia2, fr_t)

    client.post("/auth/login", data={"email": "luis@test.es", "password": "password123"})
    client.post("/publicar", data={
        "fecha_cedida_0": dia4.isoformat(),
        "franja_cedida_0": fr_m.id,
        "fecha_aceptada_0": dia3.isoformat(),
        "franja_aceptada_0": fr_n.id,
    })

    match = MatchCambio.query.filter_by(tipo="cadena_4").first()
    assert match is not None
    assert match.estado == "propuesto"
    assert MatchParticipacion.query.filter_by(match_id=match.id).count() == 4


def test_cadena_4_aparece_en_tab_compatible(client, db):
    """Un cadena_4 match propuesto aparece en el tab 'Compatibles' del dashboard
    con su propio badge, distinto del de cadena_3."""
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario("Ana", "ana@test.es", "password123", "H1", "Urgencias", cat.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "H1", "Urgencias", cat.id)
    maria = registrar_usuario("María", "maria@test.es", "password123", "H1", "Urgencias", cat.id)
    luis = registrar_usuario("Luis", "luis@test.es", "password123", "H1", "Urgencias", cat.id)

    gid = ana.unidad.grupo_intercambio_id
    fr_m = FranjaHoraria.query.filter_by(grupo_intercambio_id=gid, nombre="Mañana").first()
    fr_t = FranjaHoraria.query.filter_by(grupo_intercambio_id=gid, nombre="Tarde").first()
    fr_n = FranjaHoraria.query.filter_by(grupo_intercambio_id=gid, nombre="Noche").first()

    pub_ana = _pub(ana, date(2026, 7, 1), fr_m, date(2026, 7, 4), fr_m)
    pub_pedro = _pub(pedro, date(2026, 7, 2), fr_t, date(2026, 7, 1), fr_m)
    pub_maria = _pub(maria, date(2026, 7, 3), fr_n, date(2026, 7, 2), fr_t)
    pub_luis = _pub(luis, date(2026, 7, 4), fr_m, date(2026, 7, 3), fr_n)
    crear_match_cadena_4(pub_ana, pub_pedro, pub_maria, pub_luis)

    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    resp = client.get("/?estado=compatible")

    assert resp.status_code == 200
    assert "Cambio a 4 bandas".encode() in resp.data

    # Botón para avisar por WhatsApp a los otros 3, con la cadena completa
    # (los 4 tramos: libra/trabaja de cada participante) en el texto.
    html = resp.data.decode()
    assert "wa.me" in html
    assert "Avisar por WhatsApp" in html

    # El texto debe usar el nombre de cada usuario, no "Tú libras"/"Tú trabajas"
    # (ambiguo al reenviarlo por WhatsApp a los demás).
    import re
    from urllib.parse import unquote

    match_href = re.search(r'href="https://wa\.me/\?text=([^"]+)"', html)
    assert match_href is not None
    wa_texto = unquote(match_href.group(1))
    assert "Tú libra" not in wa_texto
    assert "Tú trabaja" not in wa_texto
    assert "Ana libra:" in wa_texto or "Ana trabaja:" in wa_texto
