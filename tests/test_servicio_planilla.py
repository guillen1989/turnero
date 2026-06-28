from datetime import date, time
from app.models import (
    Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria,
    Usuario, TurnoPlanilla, PlanillaMes,
)
from app.services.planilla import (
    añadir_turno, eliminar_turno, publicar_mes, despublicar_mes,
    tiene_mes_publicado, get_turnos_mes,
)


def _setup(db, email="u@test.es"):
    hospital = Hospital(nombre=f"H-{email}")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    unidad = Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo)
    categoria = Categoria(nombre=f"Cat-{email}")
    franja_m = FranjaHoraria(
        nombre="Mañana", hora_inicio=time(8, 0), hora_fin=time(15, 0),
        grupo_intercambio=grupo,
    )
    franja_t = FranjaHoraria(
        nombre="Tarde", hora_inicio=time(15, 0), hora_fin=time(22, 0),
        grupo_intercambio=grupo,
    )
    db.session.add_all([unidad, categoria, franja_m, franja_t])
    db.session.commit()

    usuario = Usuario(nombre="Ana", email=email, unidad=unidad, categoria=categoria)
    usuario.set_password("pass")
    db.session.add(usuario)
    db.session.commit()
    return usuario, franja_m, franja_t


def test_añadir_turno_crea_registro(db):
    usuario, franja_m, _ = _setup(db)
    turno = añadir_turno(usuario, date(2026, 7, 1), franja_m.id)
    assert turno.id is not None
    assert turno.fecha == date(2026, 7, 1)


def test_añadir_turno_crea_planilla_mes_borrador(db):
    usuario, franja_m, _ = _setup(db, "mes@test.es")
    añadir_turno(usuario, date(2026, 7, 1), franja_m.id)
    planilla = PlanillaMes.query.filter_by(usuario_id=usuario.id, anyo=2026, mes=7).first()
    assert planilla is not None
    assert not planilla.publicada


def test_añadir_turno_idempotente(db):
    usuario, franja_m, _ = _setup(db, "idem@test.es")
    t1 = añadir_turno(usuario, date(2026, 7, 1), franja_m.id)
    t2 = añadir_turno(usuario, date(2026, 7, 1), franja_m.id)
    assert t1.id == t2.id
    assert TurnoPlanilla.query.filter_by(usuario_id=usuario.id, fecha=date(2026, 7, 1)).count() == 1


def test_añadir_turno_doblaje(db):
    usuario, franja_m, franja_t = _setup(db, "dob@test.es")
    añadir_turno(usuario, date(2026, 7, 1), franja_m.id)
    añadir_turno(usuario, date(2026, 7, 1), franja_t.id)
    assert TurnoPlanilla.query.filter_by(usuario_id=usuario.id, fecha=date(2026, 7, 1)).count() == 2


def test_eliminar_turno_existente(db):
    usuario, franja_m, _ = _setup(db, "del@test.es")
    añadir_turno(usuario, date(2026, 7, 1), franja_m.id)
    resultado = eliminar_turno(usuario, date(2026, 7, 1), franja_m.id)
    assert resultado is True
    assert TurnoPlanilla.query.filter_by(usuario_id=usuario.id, fecha=date(2026, 7, 1)).count() == 0


def test_eliminar_turno_inexistente_devuelve_false(db):
    usuario, franja_m, _ = _setup(db, "nodel@test.es")
    resultado = eliminar_turno(usuario, date(2026, 7, 1), franja_m.id)
    assert resultado is False


def test_publicar_mes(db):
    usuario, franja_m, _ = _setup(db, "pub@test.es")
    añadir_turno(usuario, date(2026, 7, 1), franja_m.id)
    planilla = publicar_mes(usuario, 2026, 7)
    assert planilla.publicada


def test_publicar_mes_sin_turnos_previos(db):
    usuario, _, _ = _setup(db, "pubsin@test.es")
    planilla = publicar_mes(usuario, 2026, 7)
    assert planilla.publicada


def test_despublicar_mes(db):
    usuario, _, _ = _setup(db, "despub@test.es")
    publicar_mes(usuario, 2026, 7)
    planilla = despublicar_mes(usuario, 2026, 7)
    assert not planilla.publicada


def test_tiene_mes_publicado_true(db):
    usuario, _, _ = _setup(db, "tiene@test.es")
    publicar_mes(usuario, 2026, 7)
    assert tiene_mes_publicado(usuario, date(2026, 7, 15))


def test_tiene_mes_publicado_false_sin_registro(db):
    usuario, _, _ = _setup(db, "notiene@test.es")
    assert not tiene_mes_publicado(usuario, date(2026, 7, 15))


def test_tiene_mes_publicado_false_borrador(db):
    usuario, franja_m, _ = _setup(db, "borra@test.es")
    añadir_turno(usuario, date(2026, 7, 1), franja_m.id)
    assert not tiene_mes_publicado(usuario, date(2026, 7, 15))


def test_get_turnos_mes(db):
    usuario, franja_m, franja_t = _setup(db, "get@test.es")
    añadir_turno(usuario, date(2026, 7, 3), franja_t.id)
    añadir_turno(usuario, date(2026, 7, 1), franja_m.id)
    añadir_turno(usuario, date(2026, 8, 1), franja_m.id)  # otro mes, no debe aparecer

    turnos = get_turnos_mes(usuario, 2026, 7)
    assert len(turnos) == 2
    assert turnos[0].fecha == date(2026, 7, 1)
    assert turnos[1].fecha == date(2026, 7, 3)
