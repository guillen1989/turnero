from datetime import date
from app.extensions import db
from app.models.planilla import TurnoPlanilla, PlanillaMes


def _get_o_crear_planilla_mes(usuario, anyo, mes):
    planilla = PlanillaMes.query.filter_by(
        usuario_id=usuario.id, anyo=anyo, mes=mes
    ).first()
    if planilla is None:
        planilla = PlanillaMes(usuario=usuario, anyo=anyo, mes=mes, publicada=False)
        db.session.add(planilla)
    return planilla


def añadir_turno(usuario, fecha: date, franja_horaria_id: int) -> TurnoPlanilla:
    """Añade un turno a la planilla. Idempotente: no falla si ya existe."""
    existente = TurnoPlanilla.query.filter_by(
        usuario_id=usuario.id, fecha=fecha, franja_horaria_id=franja_horaria_id
    ).first()
    if existente:
        return existente

    _get_o_crear_planilla_mes(usuario, fecha.year, fecha.month)
    turno = TurnoPlanilla(usuario=usuario, fecha=fecha, franja_horaria_id=franja_horaria_id)
    db.session.add(turno)
    db.session.commit()
    return turno


def eliminar_turno(usuario, fecha: date, franja_horaria_id: int) -> bool:
    """Elimina un turno de la planilla. Devuelve True si existía."""
    turno = TurnoPlanilla.query.filter_by(
        usuario_id=usuario.id, fecha=fecha, franja_horaria_id=franja_horaria_id
    ).first()
    if turno is None:
        return False
    db.session.delete(turno)
    db.session.commit()
    return True


def publicar_mes(usuario, anyo: int, mes: int) -> PlanillaMes:
    """Marca el mes como publicado, creando el registro si no existe."""
    planilla = _get_o_crear_planilla_mes(usuario, anyo, mes)
    planilla.publicada = True
    db.session.commit()
    return planilla


def despublicar_mes(usuario, anyo: int, mes: int) -> PlanillaMes | None:
    """Vuelve el mes a borrador. No hace nada si no existe el registro."""
    planilla = PlanillaMes.query.filter_by(
        usuario_id=usuario.id, anyo=anyo, mes=mes
    ).first()
    if planilla:
        planilla.publicada = False
        db.session.commit()
    return planilla


def tiene_mes_publicado(usuario, fecha: date) -> bool:
    """True si el usuario tiene la planilla del mes de esa fecha publicada."""
    planilla = PlanillaMes.query.filter_by(
        usuario_id=usuario.id, anyo=fecha.year, mes=fecha.month
    ).first()
    return planilla is not None and planilla.publicada


def get_turnos_mes(usuario, anyo: int, mes: int) -> list[TurnoPlanilla]:
    """Devuelve todos los turnos del mes ordenados por fecha."""
    return (
        TurnoPlanilla.query
        .filter_by(usuario_id=usuario.id)
        .filter(
            db.func.extract("year", TurnoPlanilla.fecha) == anyo,
            db.func.extract("month", TurnoPlanilla.fecha) == mes,
        )
        .order_by(TurnoPlanilla.fecha)
        .all()
    )
