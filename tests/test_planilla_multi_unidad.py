from datetime import date, time

from app.models import (
    Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria,
    Usuario, UsuarioUnidad, TurnoPlanilla, PlanillaMes,
    EstadoDiaPlanilla, SalienteDia, NotaDia,
)
from app.services.planilla import (
    añadir_turno, eliminar_turno,
    establecer_estado_dia, limpiar_dia,
    publicar_mes, despublicar_mes,
    get_turnos_mes, get_estados_mes,
    dias_sin_cumplimentar,
    get_notas_mes, guardar_nota_dia,
    marcar_saliente, quitar_saliente, get_salientes_mes,
    franjas_trabajadas_en_fecha,
    tiene_mes_publicado,
)


def _crear_usuario_dos_unidades(db):
    """Crea un usuario con 2 unidades (UCI y Urgencias) dentro del mismo grupo."""
    hospital = Hospital(nombre="Hospital Multi")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    unidad_uci = Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo)
    unidad_urg = Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo)
    cat_enfermeria = Categoria(nombre="Enfermería")
    franja_m_uci = FranjaHoraria(
        nombre="Mañana UCI", hora_inicio=time(8, 0), hora_fin=time(15, 0),
        grupo_intercambio=grupo,
    )
    franja_t_uci = FranjaHoraria(
        nombre="Tarde UCI", hora_inicio=time(15, 0), hora_fin=time(22, 0),
        grupo_intercambio=grupo,
    )
    franja_m_urg = FranjaHoraria(
        nombre="Mañana URG", hora_inicio=time(8, 0), hora_fin=time(15, 0),
        grupo_intercambio=grupo,
    )
    db.session.add_all([unidad_uci, unidad_urg, cat_enfermeria, franja_m_uci, franja_t_uci, franja_m_urg])
    db.session.commit()

    usuario = Usuario(
        nombre="Ana Multi", email="multi@test.es", unidad=unidad_uci, categoria=cat_enfermeria,
    )
    usuario.set_password("pass")
    db.session.add(usuario)
    db.session.commit()

    db.session.add(UsuarioUnidad(
        usuario_id=usuario.id, unidad_id=unidad_uci.id, categoria_id=cat_enfermeria.id,
    ))
    db.session.add(UsuarioUnidad(
        usuario_id=usuario.id, unidad_id=unidad_urg.id, categoria_id=cat_enfermeria.id,
    ))
    db.session.commit()

    return usuario, unidad_uci, unidad_urg, franja_m_uci, franja_t_uci, franja_m_urg


# --- TurnoPlanilla por unidad ---

def test_añadir_turno_con_unidad(db):
    """Un usuario con 2 unidades guarda un turno en cada una para el mismo dia."""
    usuario, uci, urg, f_m_uci, f_t_uci, f_m_urg = _crear_usuario_dos_unidades(db)

    añadir_turno(usuario, date(2026, 7, 1), f_m_uci.id, unidad=uci)
    añadir_turno(usuario, date(2026, 7, 1), f_m_urg.id, unidad=urg)

    turnos_uci = (
        TurnoPlanilla.query
        .filter_by(usuario_id=usuario.id, fecha=date(2026, 7, 1), unidad_id=uci.id)
        .all()
    )
    turnos_urg = (
        TurnoPlanilla.query
        .filter_by(usuario_id=usuario.id, fecha=date(2026, 7, 1), unidad_id=urg.id)
        .all()
    )

    assert len(turnos_uci) == 1
    assert turnos_uci[0].franja_horaria_id == f_m_uci.id
    assert len(turnos_urg) == 1
    assert turnos_urg[0].franja_horaria_id == f_m_urg.id


def test_get_turnos_mes_filtra_por_unidad(db):
    """get_turnos_mes solo devuelve los turnos de la unidad indicada."""
    usuario, uci, urg, f_m_uci, f_t_uci, f_m_urg = _crear_usuario_dos_unidades(db)

    añadir_turno(usuario, date(2026, 7, 1), f_m_uci.id, unidad=uci)
    añadir_turno(usuario, date(2026, 7, 2), f_t_uci.id, unidad=uci)
    añadir_turno(usuario, date(2026, 7, 1), f_m_urg.id, unidad=urg)

    turnos_uci = get_turnos_mes(usuario, 2026, 7, unidad=uci)
    turnos_urg = get_turnos_mes(usuario, 2026, 7, unidad=urg)

    assert len(turnos_uci) == 2
    assert {t.franja_horaria_id for t in turnos_uci} == {f_m_uci.id, f_t_uci.id}

    assert len(turnos_urg) == 1
    assert turnos_urg[0].franja_horaria_id == f_m_urg.id


def test_eliminar_turno_respeta_unidad(db):
    """Eliminar un turno en una unidad no afecta a la otra."""
    usuario, uci, urg, f_m_uci, _, f_m_urg = _crear_usuario_dos_unidades(db)

    añadir_turno(usuario, date(2026, 7, 1), f_m_uci.id, unidad=uci)
    añadir_turno(usuario, date(2026, 7, 1), f_m_urg.id, unidad=urg)

    eliminar_turno(usuario, date(2026, 7, 1), f_m_urg.id)

    assert TurnoPlanilla.query.filter_by(
        usuario_id=usuario.id, fecha=date(2026, 7, 1),
    ).count() == 1

    assert TurnoPlanilla.query.filter_by(
        usuario_id=usuario.id, fecha=date(2026, 7, 1), unidad_id=uci.id,
    ).count() == 1


def test_franjas_trabajadas_en_fecha_filtra_por_unidad(db):
    """Solo devuelve franjas de la unidad indicada."""
    usuario, uci, urg, f_m_uci, _, f_m_urg = _crear_usuario_dos_unidades(db)

    añadir_turno(usuario, date(2026, 7, 1), f_m_uci.id, unidad=uci)
    añadir_turno(usuario, date(2026, 7, 1), f_m_urg.id, unidad=urg)

    franjas_uci = franjas_trabajadas_en_fecha(usuario, date(2026, 7, 1), unidad=uci)
    franjas_urg = franjas_trabajadas_en_fecha(usuario, date(2026, 7, 1), unidad=urg)

    assert {f.id for f in franjas_uci} == {f_m_uci.id}
    assert {f.id for f in franjas_urg} == {f_m_urg.id}


# --- EstadoDiaPlanilla por unidad ---

def test_establecer_estado_dia_con_unidad(db):
    """Establecer un estado en una unidad no afecta a la otra."""
    usuario, uci, urg, f_m_uci, _, _ = _crear_usuario_dos_unidades(db)

    establecer_estado_dia(usuario, date(2026, 7, 1), "libre", unidad=uci)
    establecer_estado_dia(usuario, date(2026, 7, 1), "vacaciones", unidad=urg)

    estado_uci = EstadoDiaPlanilla.query.filter_by(
        usuario_id=usuario.id, fecha=date(2026, 7, 1), unidad_id=uci.id,
    ).first()
    estado_urg = EstadoDiaPlanilla.query.filter_by(
        usuario_id=usuario.id, fecha=date(2026, 7, 1), unidad_id=urg.id,
    ).first()

    assert estado_uci.tipo == "libre"
    assert estado_urg.tipo == "vacaciones"


def test_get_estados_mes_filtra_por_unidad(db):
    """get_estados_mes devuelve solo los estados de la unidad indicada."""
    usuario, uci, urg, f_m_uci, _, _ = _crear_usuario_dos_unidades(db)

    establecer_estado_dia(usuario, date(2026, 7, 1), "libre", unidad=uci)
    establecer_estado_dia(usuario, date(2026, 7, 2), "vacaciones", unidad=urg)

    estados_uci = get_estados_mes(usuario, 2026, 7, unidad=uci)
    estados_urg = get_estados_mes(usuario, 2026, 7, unidad=urg)

    assert len(estados_uci) == 1
    assert date(2026, 7, 1) in estados_uci

    assert len(estados_urg) == 1
    assert date(2026, 7, 2) in estados_urg


def test_limpiar_dia_respeta_unidad(db):
    """Limpiar un dia en una unidad no borra datos de la otra."""
    usuario, uci, urg, f_m_uci, _, f_m_urg = _crear_usuario_dos_unidades(db)

    añadir_turno(usuario, date(2026, 7, 1), f_m_uci.id, unidad=uci)
    añadir_turno(usuario, date(2026, 7, 1), f_m_urg.id, unidad=urg)

    limpiar_dia(usuario, date(2026, 7, 1), unidad=uci)

    assert TurnoPlanilla.query.filter_by(
        usuario_id=usuario.id, fecha=date(2026, 7, 1), unidad_id=uci.id,
    ).count() == 0

    assert TurnoPlanilla.query.filter_by(
        usuario_id=usuario.id, fecha=date(2026, 7, 1), unidad_id=urg.id,
    ).count() == 1


# --- SalienteDia por unidad ---

def test_marcar_saliente_con_unidad(db):
    """Marcar un dia como saliente en una unidad no afecta a la otra."""
    usuario, uci, urg, _, _, _ = _crear_usuario_dos_unidades(db)

    marcar_saliente(usuario, date(2026, 7, 1), unidad=uci)

    s_uci = SalienteDia.query.filter_by(
        usuario_id=usuario.id, fecha=date(2026, 7, 1), unidad_id=uci.id,
    ).first()
    s_urg = SalienteDia.query.filter_by(
        usuario_id=usuario.id, fecha=date(2026, 7, 1), unidad_id=urg.id,
    ).first()

    assert s_uci is not None
    assert s_urg is None


def test_get_salientes_mes_filtra_por_unidad(db):
    """get_salientes_mes devuelve solo salientes de la unidad indicada."""
    usuario, uci, urg, _, _, _ = _crear_usuario_dos_unidades(db)

    marcar_saliente(usuario, date(2026, 7, 1), unidad=uci)
    marcar_saliente(usuario, date(2026, 7, 2), unidad=urg)

    s_uci = get_salientes_mes(usuario, 2026, 7, unidad=uci)
    s_urg = get_salientes_mes(usuario, 2026, 7, unidad=urg)

    assert len(s_uci) == 1
    assert date(2026, 7, 1) in s_uci
    assert len(s_urg) == 1
    assert date(2026, 7, 2) in s_urg


# --- NotaDia por unidad ---

def test_guardar_nota_dia_con_unidad(db):
    """Guardar una nota en una unidad no se ve en la otra."""
    usuario, uci, urg, _, _, _ = _crear_usuario_dos_unidades(db)

    guardar_nota_dia(usuario, date(2026, 7, 1), "Nota UCI", unidad=uci)
    guardar_nota_dia(usuario, date(2026, 7, 1), "Nota URG", unidad=urg)

    n_uci = NotaDia.query.filter_by(
        usuario_id=usuario.id, fecha=date(2026, 7, 1), unidad_id=uci.id,
    ).first()
    n_urg = NotaDia.query.filter_by(
        usuario_id=usuario.id, fecha=date(2026, 7, 1), unidad_id=urg.id,
    ).first()

    assert n_uci.texto == "Nota UCI"
    assert n_urg.texto == "Nota URG"


def test_get_notas_mes_filtra_por_unidad(db):
    """get_notas_mes devuelve solo las notas de la unidad indicada."""
    usuario, uci, urg, _, _, _ = _crear_usuario_dos_unidades(db)

    guardar_nota_dia(usuario, date(2026, 7, 1), "Nota UCI", unidad=uci)
    guardar_nota_dia(usuario, date(2026, 7, 2), "Nota URG", unidad=urg)

    notas_uci = get_notas_mes(usuario, 2026, 7, unidad=uci)
    notas_urg = get_notas_mes(usuario, 2026, 7, unidad=urg)

    assert len(notas_uci) == 1
    assert date(2026, 7, 1) in notas_uci
    assert len(notas_urg) == 1
    assert date(2026, 7, 2) in notas_urg


# --- PlanillaMes por unidad ---

def test_publicar_mes_con_unidad(db):
    """Publicar un mes en una unidad no publica el mismo mes en la otra."""
    usuario, uci, urg, f_m_uci, _, _ = _crear_usuario_dos_unidades(db)

    for d in range(1, 32):
        añadir_turno(usuario, date(2026, 7, d), f_m_uci.id, unidad=uci)

    publicar_mes(usuario, 2026, 7, unidad=uci)

    pm_uci = PlanillaMes.query.filter_by(
        usuario_id=usuario.id, anyo=2026, mes=7, unidad_id=uci.id,
    ).first()
    pm_urg = PlanillaMes.query.filter_by(
        usuario_id=usuario.id, anyo=2026, mes=7, unidad_id=urg.id,
    ).first()

    assert pm_uci is not None
    assert pm_uci.publicada
    assert pm_urg is None


def test_dias_sin_cumplimentar_filtra_por_unidad(db):
    """Dias sin cumplimentar se calcula por separado para cada unidad."""
    usuario, uci, urg, f_m_uci, _, _ = _crear_usuario_dos_unidades(db)

    añadir_turno(usuario, date(2026, 7, 1), f_m_uci.id, unidad=uci)

    vacios_uci = dias_sin_cumplimentar(usuario, 2026, 7, unidad=uci)
    vacios_urg = dias_sin_cumplimentar(usuario, 2026, 7, unidad=urg)

    assert len(vacios_uci) == 30
    assert len(vacios_urg) == 31


def test_tiene_mes_publicado_por_unidad(db):
    """tiene_mes_publicado comprueba por unidad separadamente."""
    usuario, uci, urg, f_m_uci, _, _ = _crear_usuario_dos_unidades(db)

    for d in range(1, 32):
        añadir_turno(usuario, date(2026, 7, d), f_m_uci.id, unidad=uci)

    publicar_mes(usuario, 2026, 7, unidad=uci)

    assert tiene_mes_publicado(usuario, date(2026, 7, 15), unidad=uci)
    assert not tiene_mes_publicado(usuario, date(2026, 7, 15), unidad=urg)


def test_planilla_mes_unico_por_usuario_y_unidad(db):
    """No puede haber dos PlanillaMes del mismo mes y usuario en la misma unidad."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    usuario, uci, urg, _, _, _ = _crear_usuario_dos_unidades(db)

    publicar_mes(usuario, 2026, 7, unidad=uci)

    pm2 = PlanillaMes(usuario=usuario, anyo=2026, mes=7, publicada=False, unidad_id=uci.id)
    db.session.add(pm2)
    with pytest.raises(IntegrityError):
        db.session.commit()
