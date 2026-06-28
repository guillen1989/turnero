from datetime import date, time
from app.models import (
    Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria,
    Usuario, TurnoPlanilla, PlanillaMes,
)


def _crear_usuario(db, email="ana@test.es"):
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


def test_turno_planilla_dia_trabajo(db):
    usuario, franja_m, _ = _crear_usuario(db)
    turno = TurnoPlanilla(usuario=usuario, fecha=date(2026, 7, 1), franja_horaria=franja_m)
    db.session.add(turno)
    db.session.commit()

    recuperado = db.session.get(TurnoPlanilla, turno.id)
    assert recuperado.fecha == date(2026, 7, 1)
    assert recuperado.franja_horaria_id == franja_m.id


def test_turno_planilla_doblaje(db):
    usuario, franja_m, franja_t = _crear_usuario(db, "doblaje@test.es")
    t1 = TurnoPlanilla(usuario=usuario, fecha=date(2026, 7, 1), franja_horaria=franja_m)
    t2 = TurnoPlanilla(usuario=usuario, fecha=date(2026, 7, 1), franja_horaria=franja_t)
    db.session.add_all([t1, t2])
    db.session.commit()

    turnos_del_dia = (
        db.session.query(TurnoPlanilla)
        .filter_by(usuario_id=usuario.id, fecha=date(2026, 7, 1))
        .all()
    )
    assert len(turnos_del_dia) == 2


def test_turno_planilla_no_duplica_misma_franja(db):
    import pytest
    from sqlalchemy.exc import IntegrityError

    usuario, franja_m, _ = _crear_usuario(db, "dup@test.es")
    t1 = TurnoPlanilla(usuario=usuario, fecha=date(2026, 7, 1), franja_horaria=franja_m)
    t2 = TurnoPlanilla(usuario=usuario, fecha=date(2026, 7, 1), franja_horaria=franja_m)
    db.session.add_all([t1, t2])
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_planilla_mes_empieza_como_borrador(db):
    usuario, _, _ = _crear_usuario(db, "mes@test.es")
    planilla = PlanillaMes(usuario=usuario, anyo=2026, mes=7)
    db.session.add(planilla)
    db.session.commit()

    recuperada = db.session.get(PlanillaMes, planilla.id)
    assert not recuperada.publicada


def test_planilla_mes_se_puede_publicar(db):
    usuario, _, _ = _crear_usuario(db, "pub@test.es")
    planilla = PlanillaMes(usuario=usuario, anyo=2026, mes=7)
    db.session.add(planilla)
    db.session.commit()

    planilla.publicada = True
    db.session.commit()

    assert db.session.get(PlanillaMes, planilla.id).publicada


def test_planilla_mes_unico_por_usuario(db):
    import pytest
    from sqlalchemy.exc import IntegrityError

    usuario, _, _ = _crear_usuario(db, "mesdup@test.es")
    p1 = PlanillaMes(usuario=usuario, anyo=2026, mes=7)
    p2 = PlanillaMes(usuario=usuario, anyo=2026, mes=7)
    db.session.add_all([p1, p2])
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
