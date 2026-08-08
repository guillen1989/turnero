"""
Paso 4 del plan de latencia (docs/cambio.md): las funciones de creación de
matches no deben hacer más de un `db.session.commit()` por llamada — cada
commit es un round-trip extra a Postgres en Railway.
"""
from datetime import date

import pytest
from sqlalchemy.orm import Session as OrmSession

from app.extensions import db
from app.matching.service import (
    crear_match_directo,
    crear_match_cadena_3,
    crear_match_cadena_4,
    crear_pub_sintetica,
)
from app.models import Categoria, FranjaHoraria, PublicacionCambio, TurnoCedido, TurnoAceptado, insertar_categorias_semilla
from app.services.registro import registrar_usuario


def _usuario(nombre, email, hospital="H1", unidad="Urgencias"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario(nombre, email, "password123", hospital, unidad, cat.id)


def _franja(grupo_id, nombre="Mañana"):
    return FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id, nombre=nombre).first()


def _pub(usuario, fecha_cede, franja_cede, fecha_acepta, franja_acepta, tipo="cambio"):
    pub = PublicacionCambio(usuario_id=usuario.id, tipo=tipo)
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=fecha_cede, franja_horaria_id=franja_cede.id))
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=fecha_acepta, franja_horaria_id=franja_acepta.id))
    db.session.commit()
    return pub


@pytest.fixture
def commit_counter(monkeypatch):
    llamadas = []
    original_commit = OrmSession.commit

    def fake_commit(self, *args, **kwargs):
        llamadas.append(1)
        return original_commit(self, *args, **kwargs)

    monkeypatch.setattr(OrmSession, "commit", fake_commit)
    return llamadas


def test_crear_match_directo_hace_un_solo_commit(db, commit_counter):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = ana.unidad.grupo_intercambio_id
    fr = _franja(gid)

    pub_ana = _pub(ana, date(2026, 7, 1), fr, date(2026, 7, 2), fr)
    pub_pedro = _pub(pedro, date(2026, 7, 2), fr, date(2026, 7, 1), fr)

    commit_counter.clear()
    match = crear_match_directo(pub_ana, pub_pedro)

    assert match is not None
    assert len(commit_counter) == 1


def test_crear_match_cadena_3_hace_un_solo_commit(db, commit_counter):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    maria = _usuario("María", "maria@test.es")

    gid = ana.unidad.grupo_intercambio_id
    fr_m = _franja(gid, "Mañana")
    fr_t = _franja(gid, "Tarde")
    fr_n = _franja(gid, "Noche")

    pub_ana = _pub(ana, date(2026, 7, 1), fr_m, date(2026, 7, 3), fr_n)
    pub_pedro = _pub(pedro, date(2026, 7, 2), fr_t, date(2026, 7, 1), fr_m)
    pub_maria = _pub(maria, date(2026, 7, 3), fr_n, date(2026, 7, 2), fr_t)

    commit_counter.clear()
    match = crear_match_cadena_3(pub_ana, pub_pedro, pub_maria)

    assert match is not None
    assert len(commit_counter) == 1


def test_crear_match_cadena_4_hace_un_solo_commit(db, commit_counter):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    maria = _usuario("María", "maria@test.es")
    luis = _usuario("Luis", "luis@test.es")

    gid = ana.unidad.grupo_intercambio_id
    fr_m = _franja(gid, "Mañana")
    fr_t = _franja(gid, "Tarde")
    fr_n = _franja(gid, "Noche")

    pub_ana = _pub(ana, date(2026, 7, 1), fr_m, date(2026, 7, 4), fr_m)
    pub_pedro = _pub(pedro, date(2026, 7, 2), fr_t, date(2026, 7, 1), fr_m)
    pub_maria = _pub(maria, date(2026, 7, 3), fr_n, date(2026, 7, 2), fr_t)
    pub_luis = _pub(luis, date(2026, 7, 4), fr_m, date(2026, 7, 3), fr_n)

    commit_counter.clear()
    match = crear_match_cadena_4(pub_ana, pub_pedro, pub_maria, pub_luis)

    assert match is not None
    assert len(commit_counter) == 1


def test_crear_pub_sintetica_hace_un_solo_commit(db, commit_counter):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")

    gid = ana.unidad.grupo_intercambio_id
    fr = _franja(gid)

    pub_ana = _pub(ana, date(2026, 7, 1), fr, date(2026, 7, 2), fr)
    pub_pedro = _pub(pedro, date(2026, 7, 2), fr, date(2026, 7, 3), fr)

    commit_counter.clear()
    sint = crear_pub_sintetica(pub_ana, pub_pedro)

    assert sint is not None
    assert len(commit_counter) == 1
