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

def test_turnos_por_unidad_aislados(db):
    """Añadir/consultar/borrar turnos y franjas trabajadas se aísla por unidad."""
    usuario, uci, urg, f_m_uci, f_t_uci, f_m_urg = _crear_usuario_dos_unidades(db)

    añadir_turno(usuario, date(2026, 7, 1), f_m_uci.id, unidad=uci)
    añadir_turno(usuario, date(2026, 7, 2), f_t_uci.id, unidad=uci)
    añadir_turno(usuario, date(2026, 7, 1), f_m_urg.id, unidad=urg)

    turnos_uci_bd = (
        TurnoPlanilla.query
        .filter_by(usuario_id=usuario.id, fecha=date(2026, 7, 1), unidad_id=uci.id)
        .all()
    )
    assert len(turnos_uci_bd) == 1
    assert turnos_uci_bd[0].franja_horaria_id == f_m_uci.id

    turnos_uci = get_turnos_mes(usuario, 2026, 7, unidad=uci)
    turnos_urg = get_turnos_mes(usuario, 2026, 7, unidad=urg)
    assert {t.franja_horaria_id for t in turnos_uci} == {f_m_uci.id, f_t_uci.id}
    assert len(turnos_urg) == 1
    assert turnos_urg[0].franja_horaria_id == f_m_urg.id

    franjas_uci = franjas_trabajadas_en_fecha(usuario, date(2026, 7, 1), unidad=uci)
    franjas_urg = franjas_trabajadas_en_fecha(usuario, date(2026, 7, 1), unidad=urg)
    assert {f.id for f in franjas_uci} == {f_m_uci.id}
    assert {f.id for f in franjas_urg} == {f_m_urg.id}

    eliminar_turno(usuario, date(2026, 7, 1), f_m_urg.id)
    assert TurnoPlanilla.query.filter_by(
        usuario_id=usuario.id, fecha=date(2026, 7, 1),
    ).count() == 1
    assert TurnoPlanilla.query.filter_by(
        usuario_id=usuario.id, fecha=date(2026, 7, 1), unidad_id=uci.id,
    ).count() == 1


# --- EstadoDiaPlanilla por unidad ---

def test_estado_dia_por_unidad_aislado(db):
    """Establecer/consultar/limpiar un estado en una unidad no afecta a la otra."""
    usuario, uci, urg, f_m_uci, _, f_m_urg = _crear_usuario_dos_unidades(db)

    establecer_estado_dia(usuario, date(2026, 7, 1), "libre", unidad=uci)
    establecer_estado_dia(usuario, date(2026, 7, 2), "vacaciones", unidad=urg)

    estado_uci = EstadoDiaPlanilla.query.filter_by(
        usuario_id=usuario.id, fecha=date(2026, 7, 1), unidad_id=uci.id,
    ).first()
    assert estado_uci.tipo == "libre"

    estados_uci = get_estados_mes(usuario, 2026, 7, unidad=uci)
    estados_urg = get_estados_mes(usuario, 2026, 7, unidad=urg)
    assert date(2026, 7, 1) in estados_uci
    assert date(2026, 7, 1) not in estados_urg
    assert date(2026, 7, 2) in estados_urg

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

def test_saliente_por_unidad_aislado(db):
    """Marcar y consultar salientes se aísla por unidad."""
    usuario, uci, urg, _, _, _ = _crear_usuario_dos_unidades(db)

    marcar_saliente(usuario, date(2026, 7, 1), unidad=uci)
    marcar_saliente(usuario, date(2026, 7, 2), unidad=urg)

    s_uci = SalienteDia.query.filter_by(
        usuario_id=usuario.id, fecha=date(2026, 7, 1), unidad_id=uci.id,
    ).first()
    s_urg = SalienteDia.query.filter_by(
        usuario_id=usuario.id, fecha=date(2026, 7, 1), unidad_id=urg.id,
    ).first()
    assert s_uci is not None
    assert s_urg is None

    salientes_uci = get_salientes_mes(usuario, 2026, 7, unidad=uci)
    salientes_urg = get_salientes_mes(usuario, 2026, 7, unidad=urg)
    assert date(2026, 7, 1) in salientes_uci
    assert date(2026, 7, 2) in salientes_urg


# --- NotaDia por unidad ---

def test_nota_dia_por_unidad_aislada(db):
    """Guardar y consultar notas se aísla por unidad."""
    usuario, uci, urg, _, _, _ = _crear_usuario_dos_unidades(db)

    guardar_nota_dia(usuario, date(2026, 7, 1), "Nota UCI", unidad=uci)
    guardar_nota_dia(usuario, date(2026, 7, 2), "Nota URG", unidad=urg)

    n_uci = NotaDia.query.filter_by(
        usuario_id=usuario.id, fecha=date(2026, 7, 1), unidad_id=uci.id,
    ).first()
    assert n_uci.texto == "Nota UCI"

    notas_uci = get_notas_mes(usuario, 2026, 7, unidad=uci)
    notas_urg = get_notas_mes(usuario, 2026, 7, unidad=urg)
    assert date(2026, 7, 1) in notas_uci
    assert date(2026, 7, 2) in notas_urg


# --- PlanillaMes por unidad ---

def test_publicar_mes_por_unidad_aislado(db):
    """Publicar un mes en una unidad no afecta a la otra en publicación, días
    sin cumplimentar ni consulta de mes publicado."""
    usuario, uci, urg, f_m_uci, _, _ = _crear_usuario_dos_unidades(db)

    añadir_turno(usuario, date(2026, 7, 1), f_m_uci.id, unidad=uci)
    vacios_uci = dias_sin_cumplimentar(usuario, 2026, 7, unidad=uci)
    vacios_urg = dias_sin_cumplimentar(usuario, 2026, 7, unidad=urg)
    assert len(vacios_uci) == 30
    assert len(vacios_urg) == 31

    for d in range(2, 32):
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
