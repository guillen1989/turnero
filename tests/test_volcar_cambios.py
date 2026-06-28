"""Tests para volcar cambios confirmados a la planilla."""
from datetime import date, time, datetime, timezone

import pytest

from app.models import (
    Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria, Usuario,
    PublicacionCambio, TurnoCedido, TurnoAceptado, MatchCambio, MatchParticipacion,
    TurnoPlanilla,
)
from app.models.planilla import NotaDia
from app.services.planilla import añadir_turno
from app.services.volcar_cambios import get_matches_pendientes_volcar, volcar_matches_a_planilla


def _usuario(db, email, grupo, unidad, categoria):
    u = Usuario(nombre=email.split("@")[0], email=email, unidad=unidad, categoria=categoria)
    u.set_password("pw")
    db.session.add(u)
    db.session.commit()
    return u


def _setup_dos_usuarios(db):
    hospital = Hospital(nombre="H-volcar")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    unidad = Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo)
    categoria = Categoria(nombre="Cat-volcar")
    franja_m = FranjaHoraria(
        nombre="Mañana", hora_inicio=time(8), hora_fin=time(15),
        grupo_intercambio=grupo,
    )
    franja_t = FranjaHoraria(
        nombre="Tarde", hora_inicio=time(15), hora_fin=time(22),
        grupo_intercambio=grupo,
    )
    db.session.add_all([unidad, categoria, franja_m, franja_t])
    db.session.commit()

    u_a = _usuario(db, "user_a@t.es", grupo, unidad, categoria)
    u_b = _usuario(db, "user_b@t.es", grupo, unidad, categoria)
    return u_a, u_b, franja_m, franja_t


def _crear_match_confirmado(db, u_a, u_b, franja_m, franja_t):
    """Crea un match confirmado donde A cede mañana del 10 y recibe tarde del 20."""
    pub_a = PublicacionCambio(usuario=u_a, tipo="cambio")
    pub_b = PublicacionCambio(usuario=u_b, tipo="cambio")
    db.session.add_all([pub_a, pub_b])
    db.session.commit()

    cedido_a = TurnoCedido(publicacion=pub_a, fecha=date(2026, 7, 10),
                           franja_horaria_id=franja_m.id, estado="resuelto")
    aceptado_a = TurnoAceptado(publicacion=pub_a, fecha=date(2026, 7, 20),
                               franja_horaria_id=franja_t.id, cualquier_franja=False,
                               estado="abierto")
    cedido_b = TurnoCedido(publicacion=pub_b, fecha=date(2026, 7, 20),
                           franja_horaria_id=franja_t.id, estado="resuelto")
    aceptado_b = TurnoAceptado(publicacion=pub_b, fecha=date(2026, 7, 10),
                               franja_horaria_id=franja_m.id, cualquier_franja=False,
                               estado="abierto")
    db.session.add_all([cedido_a, aceptado_a, cedido_b, aceptado_b])
    db.session.commit()

    match = MatchCambio(tipo="directo_2", estado="confirmado_total",
                        fecha_confirmacion_total=datetime.now(timezone.utc))
    db.session.add(match)
    db.session.commit()

    p_a = MatchParticipacion(match=match, publicacion=pub_a,
                             turno_cedido=cedido_a, turno_aceptado=aceptado_a,
                             confirmado=True, volcado_planilla=False)
    p_b = MatchParticipacion(match=match, publicacion=pub_b,
                             turno_cedido=cedido_b, turno_aceptado=aceptado_b,
                             confirmado=True, volcado_planilla=False)
    db.session.add_all([p_a, p_b])
    db.session.commit()
    return match, p_a, p_b


# ── get_matches_pendientes_volcar ─────────────────────────────────────────────

def test_sin_matches_devuelve_lista_vacia(db):
    u_a, u_b, franja_m, franja_t = _setup_dos_usuarios(db)
    resultado = get_matches_pendientes_volcar(u_a)
    assert resultado == []


def test_devuelve_match_confirmado_pendiente(db):
    u_a, u_b, franja_m, franja_t = _setup_dos_usuarios(db)
    _crear_match_confirmado(db, u_a, u_b, franja_m, franja_t)
    resultado = get_matches_pendientes_volcar(u_a)
    assert len(resultado) == 1
    item = resultado[0]
    assert item["cedido"].fecha == date(2026, 7, 10)
    assert item["recibido"].fecha == date(2026, 7, 20)
    assert len(item["companeros"]) == 1
    assert item["companeros"][0].email == "user_b@t.es"


def test_excluye_match_ya_volcado(db):
    u_a, u_b, franja_m, franja_t = _setup_dos_usuarios(db)
    match, p_a, p_b = _crear_match_confirmado(db, u_a, u_b, franja_m, franja_t)
    p_a.volcado_planilla = True
    db.session.commit()
    resultado = get_matches_pendientes_volcar(u_a)
    assert resultado == []


def test_excluye_match_no_confirmado_total(db):
    u_a, u_b, franja_m, franja_t = _setup_dos_usuarios(db)
    match, p_a, p_b = _crear_match_confirmado(db, u_a, u_b, franja_m, franja_t)
    match.estado = "propuesto"
    db.session.commit()
    resultado = get_matches_pendientes_volcar(u_a)
    assert resultado == []


# ── volcar_matches_a_planilla ─────────────────────────────────────────────────

def test_volcar_elimina_cedido_de_planilla(db):
    u_a, u_b, franja_m, franja_t = _setup_dos_usuarios(db)
    match, p_a, p_b = _crear_match_confirmado(db, u_a, u_b, franja_m, franja_t)
    # Pre-cargar la planilla: A tiene mañana el día 10
    añadir_turno(u_a, date(2026, 7, 10), franja_m.id)
    assert TurnoPlanilla.query.filter_by(
        usuario_id=u_a.id, fecha=date(2026, 7, 10)
    ).count() == 1

    volcar_matches_a_planilla(u_a, [p_a.id])

    assert TurnoPlanilla.query.filter_by(
        usuario_id=u_a.id, fecha=date(2026, 7, 10)
    ).count() == 0


def test_volcar_añade_recibido_a_planilla(db):
    u_a, u_b, franja_m, franja_t = _setup_dos_usuarios(db)
    match, p_a, p_b = _crear_match_confirmado(db, u_a, u_b, franja_m, franja_t)

    volcar_matches_a_planilla(u_a, [p_a.id])

    turno_recibido = TurnoPlanilla.query.filter_by(
        usuario_id=u_a.id, fecha=date(2026, 7, 20)
    ).first()
    assert turno_recibido is not None
    assert turno_recibido.franja_horaria_id == franja_t.id


def test_volcar_marca_volcado_planilla(db):
    u_a, u_b, franja_m, franja_t = _setup_dos_usuarios(db)
    match, p_a, p_b = _crear_match_confirmado(db, u_a, u_b, franja_m, franja_t)

    volcar_matches_a_planilla(u_a, [p_a.id])

    db.session.refresh(p_a)
    assert p_a.volcado_planilla is True


def test_volcar_crea_nota_en_dia_cedido(db):
    u_a, u_b, franja_m, franja_t = _setup_dos_usuarios(db)
    match, p_a, p_b = _crear_match_confirmado(db, u_a, u_b, franja_m, franja_t)

    volcar_matches_a_planilla(u_a, [p_a.id])

    nota_cedido = NotaDia.query.filter_by(
        usuario_id=u_a.id, fecha=date(2026, 7, 10)
    ).first()
    assert nota_cedido is not None
    assert "cediste" in nota_cedido.texto.lower() or "user_b" in nota_cedido.texto.lower()


def test_volcar_crea_nota_en_dia_recibido(db):
    u_a, u_b, franja_m, franja_t = _setup_dos_usuarios(db)
    match, p_a, p_b = _crear_match_confirmado(db, u_a, u_b, franja_m, franja_t)

    volcar_matches_a_planilla(u_a, [p_a.id])

    nota_recibido = NotaDia.query.filter_by(
        usuario_id=u_a.id, fecha=date(2026, 7, 20)
    ).first()
    assert nota_recibido is not None
    assert "recibiste" in nota_recibido.texto.lower() or "user_b" in nota_recibido.texto.lower()


def test_volcar_no_aplica_si_no_pertenece_al_usuario(db):
    u_a, u_b, franja_m, franja_t = _setup_dos_usuarios(db)
    match, p_a, p_b = _crear_match_confirmado(db, u_a, u_b, franja_m, franja_t)

    # u_a intenta volcar la participación de u_b → no debe aplicar nada
    n = volcar_matches_a_planilla(u_a, [p_b.id])
    assert n == 0
    db.session.refresh(p_b)
    assert p_b.volcado_planilla is False


def test_volcar_devuelve_cantidad_volcada(db):
    u_a, u_b, franja_m, franja_t = _setup_dos_usuarios(db)
    match, p_a, p_b = _crear_match_confirmado(db, u_a, u_b, franja_m, franja_t)

    n = volcar_matches_a_planilla(u_a, [p_a.id])
    assert n == 1


def test_volcar_idempotente_segunda_llamada_no_duplica(db):
    u_a, u_b, franja_m, franja_t = _setup_dos_usuarios(db)
    match, p_a, p_b = _crear_match_confirmado(db, u_a, u_b, franja_m, franja_t)

    volcar_matches_a_planilla(u_a, [p_a.id])
    n = volcar_matches_a_planilla(u_a, [p_a.id])
    assert n == 0
    # Solo un turno recibido en el planilla
    assert TurnoPlanilla.query.filter_by(
        usuario_id=u_a.id, fecha=date(2026, 7, 20)
    ).count() == 1


# ── ruta POST /planilla/volcar-cambios ────────────────────────────────────────

def _login(client, db, email, grupo=None, unidad=None, categoria=None):
    if grupo is None:
        hospital = Hospital(nombre=f"HR-{email}")
        grupo = GrupoIntercambio()
        db.session.add_all([hospital, grupo])
        db.session.commit()
        unidad = Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo)
        categoria = Categoria(nombre=f"CR-{email}")
        db.session.add_all([unidad, categoria])
        db.session.commit()
    u = Usuario(nombre="R", email=email, unidad=unidad, categoria=categoria)
    u.set_password("pw")
    db.session.add(u)
    db.session.commit()
    client.post("/auth/login", data={"email": email, "password": "pw"})
    return u


def test_ruta_volcar_aplica_cambio_y_redirige(client, db):
    u_a, u_b, franja_m, franja_t = _setup_dos_usuarios(db)
    match, p_a, p_b = _crear_match_confirmado(db, u_a, u_b, franja_m, franja_t)
    añadir_turno(u_a, date(2026, 7, 10), franja_m.id)

    # Logueamos u_a mediante el cliente
    client.post("/auth/login", data={"email": "user_a@t.es", "password": "pw"})
    resp = client.post("/planilla/volcar-cambios", data={
        "participacion_id[]": [str(p_a.id)],
        "anyo": 2026,
        "mes": 7,
    }, follow_redirects=False)
    assert resp.status_code == 302

    db.session.refresh(p_a)
    assert p_a.volcado_planilla is True
