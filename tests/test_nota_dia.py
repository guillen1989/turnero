"""Tests para notas por día en la planilla."""
from datetime import date, time

import pytest

from app.models import Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria, Usuario
from app.models.planilla import NotaDia
from app.services.planilla import guardar_nota_dia, get_notas_mes


def _setup(db, email="nota@test.es"):
    hospital = Hospital(nombre=f"H-{email}")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    unidad = Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo)
    categoria = Categoria(nombre=f"Cat-{email}")
    franja = FranjaHoraria(
        nombre="Mañana", hora_inicio=time(8), hora_fin=time(15),
        grupo_intercambio=grupo,
    )
    db.session.add_all([unidad, categoria, franja])
    db.session.commit()

    usuario = Usuario(nombre="Test", email=email, unidad=unidad, categoria=categoria)
    usuario.set_password("pass")
    db.session.add(usuario)
    db.session.commit()
    return usuario


# ── guardar_nota_dia ──────────────────────────────────────────────────────────

def test_guardar_nota_dia_crea_nueva(db):
    usuario = _setup(db, "nota_crea@t.es")
    fecha = date(2026, 7, 10)
    nota = guardar_nota_dia(usuario, fecha, "Reunión de equipo")
    assert nota is not None
    assert nota.texto == "Reunión de equipo"
    assert nota.fecha == fecha
    assert nota.usuario_id == usuario.id


def test_guardar_nota_dia_actualiza_existente(db):
    usuario = _setup(db, "nota_upd@t.es")
    fecha = date(2026, 7, 10)
    guardar_nota_dia(usuario, fecha, "Texto inicial")
    nota = guardar_nota_dia(usuario, fecha, "Texto nuevo")
    assert nota.texto == "Texto nuevo"
    assert NotaDia.query.filter_by(usuario_id=usuario.id, fecha=fecha).count() == 1


def test_guardar_nota_dia_texto_vacio_elimina_nota(db):
    usuario = _setup(db, "nota_del@t.es")
    fecha = date(2026, 7, 10)
    guardar_nota_dia(usuario, fecha, "Algo")
    resultado = guardar_nota_dia(usuario, fecha, "")
    assert resultado is None
    assert NotaDia.query.filter_by(usuario_id=usuario.id, fecha=fecha).count() == 0


def test_guardar_nota_dia_texto_solo_espacios_elimina(db):
    usuario = _setup(db, "nota_ws@t.es")
    fecha = date(2026, 7, 5)
    guardar_nota_dia(usuario, fecha, "Algo")
    resultado = guardar_nota_dia(usuario, fecha, "   ")
    assert resultado is None


def test_guardar_nota_dia_vacio_sin_nota_previa_no_crea(db):
    usuario = _setup(db, "nota_noexiste@t.es")
    resultado = guardar_nota_dia(usuario, date(2026, 7, 1), "")
    assert resultado is None
    assert NotaDia.query.filter_by(usuario_id=usuario.id).count() == 0


# ── get_notas_mes ─────────────────────────────────────────────────────────────

def test_get_notas_mes_devuelve_dict(db):
    usuario = _setup(db, "nota_mes@t.es")
    guardar_nota_dia(usuario, date(2026, 7, 5), "Nota cinco")
    guardar_nota_dia(usuario, date(2026, 7, 20), "Nota veinte")
    guardar_nota_dia(usuario, date(2026, 8, 1), "Otro mes")

    notas = get_notas_mes(usuario, 2026, 7)
    assert len(notas) == 2
    assert date(2026, 7, 5) in notas
    assert date(2026, 7, 20) in notas
    assert date(2026, 8, 1) not in notas
    assert notas[date(2026, 7, 5)].texto == "Nota cinco"


def test_get_notas_mes_mes_sin_notas_devuelve_dict_vacio(db):
    usuario = _setup(db, "nota_vacio@t.es")
    notas = get_notas_mes(usuario, 2026, 7)
    assert notas == {}


# ── ruta /planilla/dia/nota ───────────────────────────────────────────────────

def _login(client, db, email):
    hospital = Hospital(nombre=f"H2-{email}")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()
    unidad = Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo)
    categoria = Categoria(nombre=f"C2-{email}")
    db.session.add_all([unidad, categoria])
    db.session.commit()
    usuario = Usuario(nombre="R", email=email, unidad=unidad, categoria=categoria)
    usuario.set_password("pw")
    db.session.add(usuario)
    db.session.commit()
    client.post("/auth/login", data={"email": email, "password": "pw"})
    return usuario


def test_ruta_nota_guarda_y_redirige(client, db):
    usuario = _login(client, db, "ruta_nota@t.es")
    resp = client.post("/planilla/dia/nota", data={
        "fecha": "2026-07-15",
        "texto": "Guardia larga",
        "anyo": 2026,
        "mes": 7,
    }, follow_redirects=False)
    assert resp.status_code == 302
    nota = NotaDia.query.filter_by(usuario_id=usuario.id, fecha=date(2026, 7, 15)).first()
    assert nota is not None
    assert nota.texto == "Guardia larga"


def test_ruta_nota_actualiza_existente(client, db):
    usuario = _login(client, db, "ruta_nota2@t.es")
    client.post("/planilla/dia/nota", data={
        "fecha": "2026-07-15", "texto": "Primera", "anyo": 2026, "mes": 7,
    })
    client.post("/planilla/dia/nota", data={
        "fecha": "2026-07-15", "texto": "Segunda", "anyo": 2026, "mes": 7,
    })
    assert NotaDia.query.filter_by(usuario_id=usuario.id).count() == 1
    nota = NotaDia.query.filter_by(usuario_id=usuario.id).first()
    assert nota.texto == "Segunda"


def test_ruta_nota_vacia_elimina(client, db):
    usuario = _login(client, db, "ruta_nota3@t.es")
    client.post("/planilla/dia/nota", data={
        "fecha": "2026-07-15", "texto": "Algo", "anyo": 2026, "mes": 7,
    })
    client.post("/planilla/dia/nota", data={
        "fecha": "2026-07-15", "texto": "", "anyo": 2026, "mes": 7,
    })
    assert NotaDia.query.filter_by(usuario_id=usuario.id).count() == 0
