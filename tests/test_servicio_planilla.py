from datetime import date, time
from app.models import (
    Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria,
    Usuario, TurnoPlanilla, PlanillaMes,
)
from app.services.planilla import (
    añadir_turno, eliminar_turno, publicar_mes, despublicar_mes,
    tiene_mes_publicado, get_turnos_mes, establecer_estado_dia, limpiar_dia,
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


# ── Tests de estados de día ───────────────────────────────────────────────────

def test_establecer_estado_libre(db):
    usuario, franja_m, _ = _setup(db, "libre@test.es")
    estado = establecer_estado_dia(usuario, date(2026, 7, 5), "libre")
    assert estado.tipo == "libre"


def test_establecer_estado_elimina_turnos_previos(db):
    from app.services.planilla import establecer_estado_dia
    usuario, franja_m, _ = _setup(db, "elim@test.es")
    añadir_turno(usuario, date(2026, 7, 5), franja_m.id)
    establecer_estado_dia(usuario, date(2026, 7, 5), "vacaciones")
    assert TurnoPlanilla.query.filter_by(usuario_id=usuario.id, fecha=date(2026, 7, 5)).count() == 0


def test_añadir_turno_elimina_estado_previo(db):
    from app.services.planilla import establecer_estado_dia
    from app.models import EstadoDiaPlanilla
    usuario, franja_m, _ = _setup(db, "turnoest@test.es")
    establecer_estado_dia(usuario, date(2026, 7, 5), "vacaciones")
    añadir_turno(usuario, date(2026, 7, 5), franja_m.id)
    assert EstadoDiaPlanilla.query.filter_by(usuario_id=usuario.id, fecha=date(2026, 7, 5)).first() is None


def test_limpiar_dia_elimina_todo(db):
    from app.services.planilla import establecer_estado_dia, limpiar_dia
    from app.models import EstadoDiaPlanilla
    usuario, franja_m, _ = _setup(db, "limpia@test.es")
    establecer_estado_dia(usuario, date(2026, 7, 5), "libre")
    limpiar_dia(usuario, date(2026, 7, 5))
    assert EstadoDiaPlanilla.query.filter_by(usuario_id=usuario.id, fecha=date(2026, 7, 5)).first() is None


def test_estado_invalido_lanza_error(db):
    import pytest
    from app.services.planilla import establecer_estado_dia
    usuario, _, _ = _setup(db, "inv@test.es")
    with pytest.raises(ValueError):
        establecer_estado_dia(usuario, date(2026, 7, 5), "tipo_inventado")


# ── Tests de SalienteDia ──────────────────────────────────────────────────────

def test_marcar_saliente_crea_registro(db):
    from app.services.planilla import marcar_saliente
    from app.models import SalienteDia
    usuario, _, _ = _setup(db, "sal1@test.es")
    marcar_saliente(usuario, date(2026, 7, 3))
    assert SalienteDia.query.filter_by(usuario_id=usuario.id, fecha=date(2026, 7, 3)).first() is not None


def test_marcar_saliente_es_idempotente(db):
    from app.services.planilla import marcar_saliente
    from app.models import SalienteDia
    usuario, _, _ = _setup(db, "sal2@test.es")
    marcar_saliente(usuario, date(2026, 7, 3))
    marcar_saliente(usuario, date(2026, 7, 3))
    assert SalienteDia.query.filter_by(usuario_id=usuario.id, fecha=date(2026, 7, 3)).count() == 1


def test_quitar_saliente_elimina_registro(db):
    from app.services.planilla import marcar_saliente, quitar_saliente
    from app.models import SalienteDia
    usuario, _, _ = _setup(db, "sal3@test.es")
    marcar_saliente(usuario, date(2026, 7, 3))
    resultado = quitar_saliente(usuario, date(2026, 7, 3))
    assert resultado is True
    assert SalienteDia.query.filter_by(usuario_id=usuario.id, fecha=date(2026, 7, 3)).first() is None


def test_quitar_saliente_inexistente_devuelve_false(db):
    from app.services.planilla import quitar_saliente
    usuario, _, _ = _setup(db, "sal4@test.es")
    assert quitar_saliente(usuario, date(2026, 7, 3)) is False


def test_saliente_coexiste_con_turno(db):
    from app.services.planilla import marcar_saliente, añadir_turno
    from app.models import SalienteDia, TurnoPlanilla
    usuario, _, franja_t = _setup(db, "sal5@test.es")
    añadir_turno(usuario, date(2026, 7, 3), franja_t.id)
    marcar_saliente(usuario, date(2026, 7, 3))
    assert TurnoPlanilla.query.filter_by(usuario_id=usuario.id, fecha=date(2026, 7, 3)).count() == 1
    assert SalienteDia.query.filter_by(usuario_id=usuario.id, fecha=date(2026, 7, 3)).first() is not None


def test_limpiar_dia_elimina_saliente(db):
    from app.services.planilla import marcar_saliente, limpiar_dia
    from app.models import SalienteDia
    usuario, _, _ = _setup(db, "sal6@test.es")
    marcar_saliente(usuario, date(2026, 7, 3))
    limpiar_dia(usuario, date(2026, 7, 3))
    assert SalienteDia.query.filter_by(usuario_id=usuario.id, fecha=date(2026, 7, 3)).first() is None


def test_get_salientes_mes(db):
    from app.services.planilla import marcar_saliente, get_salientes_mes
    usuario, _, _ = _setup(db, "sal7@test.es")
    marcar_saliente(usuario, date(2026, 7, 3))
    marcar_saliente(usuario, date(2026, 7, 15))
    salientes = get_salientes_mes(usuario, 2026, 7)
    assert date(2026, 7, 3) in salientes
    assert date(2026, 7, 15) in salientes
    assert date(2026, 7, 1) not in salientes
