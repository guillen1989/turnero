"""Tests para matching a 3 bandas: motor de búsqueda y creación de matches."""
from datetime import date, timedelta

import pytest

from app.extensions import db
from app.matching.service import buscar_cadenas_3_para, crear_match_cadena_3
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
    Crea Ana, Pedro y María con publicaciones que forman el ciclo A→Pedro→María→A:
      - Ana cede mañana_1  → Pedro la acepta
      - Pedro cede tarde_2 → María la acepta
      - María cede noche_3 → Ana la acepta
    """
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    maria = _usuario("María", "maria@test.es")

    gid = ana.unidad.grupo_intercambio_id
    fr_m = _franja(gid, "Mañana")
    fr_t = _franja(gid, "Tarde")
    fr_n = _franja(gid, "Noche")

    # Ana cede mañana_1 (que Pedro acepta), acepta noche_3 (que María cede)
    pub_ana = _pub(ana, date(2026, 7, 1), fr_m, date(2026, 7, 3), fr_n)
    # Pedro cede tarde_2 (que María acepta), acepta mañana_1 (que Ana cede)
    pub_pedro = _pub(pedro, date(2026, 7, 2), fr_t, date(2026, 7, 1), fr_m)
    # María cede noche_3 (que Ana acepta), acepta tarde_2 (que Pedro cede)
    pub_maria = _pub(maria, date(2026, 7, 3), fr_n, date(2026, 7, 2), fr_t)

    return pub_ana, pub_pedro, pub_maria, ana, pedro, maria


# --- buscar_cadenas_3_para ---

def test_detecta_cadena_3_basica(db):
    """El servicio detecta el ciclo A→Pedro→María→A."""
    pub_ana, pub_pedro, pub_maria, *_ = _setup_ciclo(db)

    cadenas = buscar_cadenas_3_para(pub_ana)

    assert len(cadenas) == 1
    ids_encontrados = {cadenas[0][0].id, cadenas[0][1].id}
    assert ids_encontrados == {pub_pedro.id, pub_maria.id}


def test_cadena_3_no_detecta_ciclo_incompleto(db):
    """Si el ciclo no se cierra, no hay cadena."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    maria = _usuario("María", "maria@test.es")

    gid = ana.unidad.grupo_intercambio_id
    fr_m = _franja(gid, "Mañana")
    fr_t = _franja(gid, "Tarde")
    fr_n = _franja(gid, "Noche")

    # Ana cede mañana_1, acepta noche_3
    pub_ana = _pub(ana, date(2026, 7, 1), fr_m, date(2026, 7, 3), fr_n)
    # Pedro cede tarde_2, acepta mañana_1
    _pub(pedro, date(2026, 7, 2), fr_t, date(2026, 7, 1), fr_m)
    # María cede noche_3, pero acepta mañana_1 (no tarde_2) → el ciclo P→M se rompe
    _pub(maria, date(2026, 7, 3), fr_n, date(2026, 7, 1), fr_m)

    assert buscar_cadenas_3_para(pub_ana) == []


def test_cadena_3_no_detecta_match_directo_como_cadena(db):
    """Un match directo A↔B no se detecta como cadena de 3."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")

    gid = ana.unidad.grupo_intercambio_id
    fr_m = _franja(gid, "Mañana")
    fr_t = _franja(gid, "Tarde")

    pub_ana = _pub(ana, date(2026, 7, 1), fr_m, date(2026, 7, 2), fr_t)
    _pub(pedro, date(2026, 7, 2), fr_t, date(2026, 7, 1), fr_m)

    assert buscar_cadenas_3_para(pub_ana) == []


def test_cadena_3_respeta_filtro_de_categoria(db):
    """Usuarios de distinta categoría no forman cadena."""
    insertar_categorias_semilla()
    cat_enf = Categoria.query.filter_by(nombre="Enfermería").first()
    cat_aux = Categoria.query.filter_by(nombre="Auxiliar de enfermería (TCAE)").first()

    ana = registrar_usuario("Ana", "ana@test.es", "password123", "H1", "Urgencias", cat_enf.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "H1", "Urgencias", cat_enf.id)
    maria = registrar_usuario("María", "maria@test.es", "password123", "H1", "Urgencias", cat_aux.id)

    gid = ana.unidad.grupo_intercambio_id
    fr_m = _franja(gid, "Mañana")
    fr_t = _franja(gid, "Tarde")
    fr_n = _franja(gid, "Noche")

    pub_ana = _pub(ana, date(2026, 7, 1), fr_m, date(2026, 7, 2), fr_t)
    _pub(pedro, date(2026, 7, 2), fr_t, date(2026, 7, 3), fr_n)
    _pub(maria, date(2026, 7, 3), fr_n, date(2026, 7, 1), fr_m)

    # María es de distinta categoría → no forma cadena con Ana y Pedro
    assert buscar_cadenas_3_para(pub_ana) == []


def test_cadena_3_no_duplica_si_ya_existe(db):
    """Si el match ya existe para ese triple, no lo devuelve de nuevo."""
    pub_ana, pub_pedro, pub_maria, *_ = _setup_ciclo(db)

    # Creamos el match con el orden correcto del ciclo A→Pedro→María→A
    crear_match_cadena_3(pub_ana, pub_pedro, pub_maria)

    # Nueva búsqueda no debe devolver el mismo triple
    cadenas = buscar_cadenas_3_para(pub_ana)
    assert cadenas == []


def test_cadena_3_solo_tipo_cambio(db):
    """Las cadenas de 3 solo se buscan para publicaciones de tipo 'cambio'."""
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

    assert buscar_cadenas_3_para(pub_junte) == []


def _pub_listas(usuario, cedidos, aceptados):
    """Crea una pub de tipo cambio con múltiples cedidos y/o aceptados.

    cedidos / aceptados: lista de (fecha, franja).
    """
    pub = PublicacionCambio(usuario_id=usuario.id, tipo="cambio")
    db.session.add(pub)
    db.session.flush()
    for fecha, franja in cedidos:
        db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=fecha, franja_horaria_id=franja.id))
    for fecha, franja in aceptados:
        db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=fecha, franja_horaria_id=franja.id))
    db.session.commit()
    return pub


def test_cadena_3_detecta_ciclos_para_todos_los_cedidos(db):
    """Con dos cedidos abiertos, el motor encuentra cadenas independientes para cada uno."""
    guillen = _usuario("Guillén", "guillen@test.es")
    u_b1    = _usuario("B1", "b1@test.es")
    u_c1    = _usuario("C1", "c1@test.es")
    u_b2    = _usuario("B2", "b2@test.es")
    u_c2    = _usuario("C2", "c2@test.es")

    gid = guillen.unidad.grupo_intercambio_id
    fr_m = _franja(gid, "Mañana")
    fr_t = _franja(gid, "Tarde")
    fr_n = _franja(gid, "Noche")
    d1, d2, d3, d4, d5 = [date(2026, 7, i) for i in range(1, 6)]

    # Guillén cede {día1-Tarde, día2-Mañana}, acepta día3-Noche
    pub_g = _pub_listas(guillen, [(d1, fr_t), (d2, fr_m)], [(d3, fr_n)])

    # Ciclo 1: Guillén→B1 (día1-Tarde), B1→C1 (día4-Tarde), C1→Guillén (día3-Noche)
    pub_b1 = _pub(u_b1, d4, fr_t, d1, fr_t)
    pub_c1 = _pub(u_c1, d3, fr_n, d4, fr_t)

    # Ciclo 2: Guillén→B2 (día2-Mañana), B2→C2 (día5-Mañana), C2→Guillén (día3-Noche)
    pub_b2 = _pub(u_b2, d5, fr_m, d2, fr_m)
    pub_c2 = _pub(u_c2, d3, fr_n, d5, fr_m)

    cadenas = buscar_cadenas_3_para(pub_g)

    assert len(cadenas) == 2
    pares = {frozenset({c[0].id, c[1].id}) for c in cadenas}
    assert frozenset({pub_b1.id, pub_c1.id}) in pares
    assert frozenset({pub_b2.id, pub_c2.id}) in pares


def test_cadena_3_detecta_ciclos_para_todos_los_aceptados(db):
    """Con dos aceptados distintos, el motor encuentra cadenas que se cierran por cualquiera de ellos."""
    guillen = _usuario("Guillén", "guillen@test.es")
    u_b1    = _usuario("B1", "b1@test.es")
    u_c1    = _usuario("C1", "c1@test.es")
    u_b2    = _usuario("B2", "b2@test.es")
    u_c2    = _usuario("C2", "c2@test.es")

    gid = guillen.unidad.grupo_intercambio_id
    fr_m = _franja(gid, "Mañana")
    fr_t = _franja(gid, "Tarde")
    fr_n = _franja(gid, "Noche")
    d1, d2, d3, d4, d5, d6 = [date(2026, 7, i) for i in range(1, 7)]

    # Guillén cede día1-Tarde, acepta {día3-Noche, día4-Mañana}
    pub_g = _pub_listas(guillen, [(d1, fr_t)], [(d3, fr_n), (d4, fr_m)])

    # Ciclo 1 cierra por día3-Noche: Guillén→B1 (día1-Tarde), B1→C1 (día5-Tarde), C1→Guillén (día3-Noche)
    pub_b1 = _pub(u_b1, d5, fr_t, d1, fr_t)
    pub_c1 = _pub(u_c1, d3, fr_n, d5, fr_t)

    # Ciclo 2 cierra por día4-Mañana: Guillén→B2 (día1-Tarde), B2→C2 (día6-Tarde), C2→Guillén (día4-Mañana)
    pub_b2 = _pub(u_b2, d6, fr_t, d1, fr_t)
    pub_c2 = _pub(u_c2, d4, fr_m, d6, fr_t)

    cadenas = buscar_cadenas_3_para(pub_g)

    assert len(cadenas) == 2
    pares = {frozenset({c[0].id, c[1].id}) for c in cadenas}
    assert frozenset({pub_b1.id, pub_c1.id}) in pares
    assert frozenset({pub_b2.id, pub_c2.id}) in pares


# --- crear_match_cadena_3 ---

def test_crear_match_cadena_3_tipo_y_estado(db):
    pub_ana, pub_pedro, pub_maria, *_ = _setup_ciclo(db)

    match = crear_match_cadena_3(pub_ana, pub_pedro, pub_maria)

    assert match is not None
    assert match.tipo == "cadena_3"
    assert match.estado == "propuesto"


def test_crear_match_cadena_3_genera_tres_participaciones(db):
    pub_ana, pub_pedro, pub_maria, *_ = _setup_ciclo(db)

    match = crear_match_cadena_3(pub_ana, pub_pedro, pub_maria)

    parts = MatchParticipacion.query.filter_by(match_id=match.id).all()
    assert len(parts) == 3
    pub_ids = {p.publicacion_id for p in parts}
    assert pub_ids == {pub_ana.id, pub_pedro.id, pub_maria.id}


def test_crear_match_cadena_3_cada_participacion_tiene_turno_cedido(db):
    pub_ana, pub_pedro, pub_maria, *_ = _setup_ciclo(db)

    match = crear_match_cadena_3(pub_ana, pub_pedro, pub_maria)

    for p in match.participaciones:
        assert p.turno_cedido_id is not None


def test_crear_match_cadena_3_genera_tres_notificaciones(db):
    pub_ana, pub_pedro, pub_maria, ana, pedro, maria = _setup_ciclo(db)

    match = crear_match_cadena_3(pub_ana, pub_pedro, pub_maria)

    notifs = Notificacion.query.filter_by(match_id=match.id, tipo="nuevo_match").all()
    assert len(notifs) == 3
    usuarios = {n.usuario_id for n in notifs}
    assert usuarios == {ana.id, pedro.id, maria.id}


def test_cadena_3_confirmacion_total_requiere_tres(db):
    """El match solo se cierra cuando los tres confirman."""
    from app.services.matches import confirmar_participacion

    pub_ana, pub_pedro, pub_maria, ana, pedro, maria = _setup_ciclo(db)
    match = crear_match_cadena_3(pub_ana, pub_pedro, pub_maria)

    confirmar_participacion(match, ana.id)
    assert match.estado == "confirmado_parcial"

    confirmar_participacion(match, pedro.id)
    assert match.estado == "confirmado_parcial"

    confirmar_participacion(match, maria.id)
    assert match.estado == "confirmado_total"


def test_cadena_3_publicacion_se_confirma_cuando_todos_confirman(db):
    """Las publicaciones de los 3 pasan a 'confirmada' tras confirmación total."""
    from app.services.matches import confirmar_participacion

    pub_ana, pub_pedro, pub_maria, ana, pedro, maria = _setup_ciclo(db)
    match = crear_match_cadena_3(pub_ana, pub_pedro, pub_maria)

    confirmar_participacion(match, ana.id)
    confirmar_participacion(match, pedro.id)
    confirmar_participacion(match, maria.id)

    db.session.refresh(pub_ana)
    db.session.refresh(pub_pedro)
    db.session.refresh(pub_maria)

    assert pub_ana.estado == "confirmada"
    assert pub_pedro.estado == "confirmada"
    assert pub_maria.estado == "confirmada"


# --- Integración con la ruta de publicar ---

def test_publicar_crea_match_cadena_3_cuando_hay_ciclo(client, db):
    """Al publicar la tercera publicación que cierra el ciclo se crea un cadena_3 match."""
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario("Ana", "ana@test.es", "password123", "H1", "Urgencias", cat.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "H1", "Urgencias", cat.id)
    maria = registrar_usuario("María", "maria@test.es", "password123", "H1", "Urgencias", cat.id)

    gid = ana.unidad.grupo_intercambio_id
    fr_m = FranjaHoraria.query.filter_by(grupo_intercambio_id=gid, nombre="Mañana").first()
    fr_t = FranjaHoraria.query.filter_by(grupo_intercambio_id=gid, nombre="Tarde").first()
    fr_n = FranjaHoraria.query.filter_by(grupo_intercambio_id=gid, nombre="Noche").first()

    # Fechas futuras relativas a hoy: la ruta /publicar rechaza fechas pasadas.
    dia1 = date.today() + timedelta(days=1)
    dia2 = date.today() + timedelta(days=2)
    dia3 = date.today() + timedelta(days=3)

    # Ana y Pedro publican (sin ciclo todavía)
    pub_ana = _pub(ana, dia1, fr_m, dia3, fr_n)
    pub_pedro = _pub(pedro, dia2, fr_t, dia1, fr_m)

    # María publica → cierra el ciclo
    client.post("/auth/login", data={"email": "maria@test.es", "password": "password123"})
    client.post("/publicar", data={
        "fecha_cedida_0": dia3.isoformat(),
        "franja_cedida_0": fr_n.id,
        "fecha_aceptada_0": dia2.isoformat(),
        "franja_aceptada_0": fr_t.id,
    })

    match = MatchCambio.query.filter_by(tipo="cadena_3").first()
    assert match is not None
    assert match.estado == "propuesto"
    assert MatchParticipacion.query.filter_by(match_id=match.id).count() == 3


def test_cadena_3_aparece_en_tab_compatible(client, db):
    """Un cadena_3 match propuesto aparece en el tab 'Compatibles' del dashboard."""
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario("Ana", "ana@test.es", "password123", "H1", "Urgencias", cat.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "H1", "Urgencias", cat.id)
    maria = registrar_usuario("María", "maria@test.es", "password123", "H1", "Urgencias", cat.id)

    gid = ana.unidad.grupo_intercambio_id
    fr_m = FranjaHoraria.query.filter_by(grupo_intercambio_id=gid, nombre="Mañana").first()
    fr_t = FranjaHoraria.query.filter_by(grupo_intercambio_id=gid, nombre="Tarde").first()
    fr_n = FranjaHoraria.query.filter_by(grupo_intercambio_id=gid, nombre="Noche").first()

    pub_ana = _pub(ana, date(2026, 7, 1), fr_m, date(2026, 7, 3), fr_n)
    pub_pedro = _pub(pedro, date(2026, 7, 2), fr_t, date(2026, 7, 1), fr_m)
    pub_maria = _pub(maria, date(2026, 7, 3), fr_n, date(2026, 7, 2), fr_t)
    crear_match_cadena_3(pub_ana, pub_pedro, pub_maria)

    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    resp = client.get("/?estado=compatible")

    assert resp.status_code == 200
    assert "Cambio a 3 bandas".encode() in resp.data
