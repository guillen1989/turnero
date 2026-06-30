"""Tests para el comando flask rematch.

Verifica que el comando detecta matches perdidos (publicaciones compatibles
creadas sin pasar por la ruta /publicar) y los crea correctamente.
"""
from datetime import date, time

import pytest

from app.extensions import db
from app.models import (
    Categoria,
    FranjaHoraria,
    MatchCambio,
    PublicacionCambio,
    TurnoCedido,
    TurnoAceptado,
    insertar_categorias_semilla,
)
from app.services.registro import registrar_usuario


def _categoria():
    insertar_categorias_semilla()
    return Categoria.query.filter_by(nombre="Enfermería").first()


def _usuario(nombre, email):
    cat = _categoria()
    return registrar_usuario(nombre, email, "pw", "HospitalX", "UrgenciasX", cat.id)


def _franja(grupo_id):
    f = FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id, nombre="Mañana").first()
    if f:
        return f
    f = FranjaHoraria(
        nombre="Mañana",
        hora_inicio=time(8, 0),
        hora_fin=time(15, 0),
        grupo_intercambio_id=grupo_id,
    )
    db.session.add(f)
    db.session.commit()
    return f


def _pub_sin_matching(usuario, fecha_cede, fecha_acepta, franja):
    """Crea una publicación directamente en BD, sin disparar el motor de matching."""
    pub = PublicacionCambio(usuario_id=usuario.id, tipo="cambio")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(
        publicacion_id=pub.id, fecha=fecha_cede, franja_horaria_id=franja.id
    ))
    db.session.add(TurnoAceptado(
        publicacion_id=pub.id, fecha=fecha_acepta, franja_horaria_id=franja.id
    ))
    db.session.commit()
    return pub


def test_rematch_crea_match_perdido(app):
    """Dos pubs compatibles creadas sin matching → rematch las empareja."""
    ana = _usuario("Ana", "ana@rematch.es")
    pedro = _usuario("Pedro", "pedro@rematch.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)

    _pub_sin_matching(ana,   fecha_cede=date(2027, 1, 10), fecha_acepta=date(2027, 1, 11), franja=franja)
    _pub_sin_matching(pedro, fecha_cede=date(2027, 1, 11), fecha_acepta=date(2027, 1, 10), franja=franja)

    assert MatchCambio.query.count() == 0

    runner = app.test_cli_runner()
    result = runner.invoke(args=["rematch"])

    assert result.exit_code == 0, result.output
    assert MatchCambio.query.count() == 1
    assert "Matches directos nuevos:   1" in result.output


def test_rematch_no_duplica_match_existente(app):
    """Si ya existe un match activo entre dos pubs, rematch no crea otro."""
    from app.matching.service import crear_match_directo

    ana = _usuario("Ana", "ana2@rematch.es")
    pedro = _usuario("Pedro", "pedro2@rematch.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_a = _pub_sin_matching(ana,   fecha_cede=date(2027, 2, 5), fecha_acepta=date(2027, 2, 6), franja=franja)
    pub_b = _pub_sin_matching(pedro, fecha_cede=date(2027, 2, 6), fecha_acepta=date(2027, 2, 5), franja=franja)
    crear_match_directo(pub_a, pub_b)

    assert MatchCambio.query.count() == 1

    runner = app.test_cli_runner()
    result = runner.invoke(args=["rematch"])

    assert result.exit_code == 0, result.output
    assert MatchCambio.query.count() == 1
    assert "Matches directos nuevos:   0" in result.output


def test_rematch_dry_run_no_guarda(app):
    """Con --dry-run el comando reporta matches posibles pero no los crea."""
    ana = _usuario("Ana", "ana3@rematch.es")
    pedro = _usuario("Pedro", "pedro3@rematch.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)

    _pub_sin_matching(ana,   fecha_cede=date(2027, 3, 1), fecha_acepta=date(2027, 3, 2), franja=franja)
    _pub_sin_matching(pedro, fecha_cede=date(2027, 3, 2), fecha_acepta=date(2027, 3, 1), franja=franja)

    runner = app.test_cli_runner()
    result = runner.invoke(args=["rematch", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "[dry-run]" in result.output
    assert MatchCambio.query.count() == 0
