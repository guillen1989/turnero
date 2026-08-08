from __future__ import annotations

import calendar as _calendar
from datetime import date
from app.extensions import db
from app.models.planilla import TurnoPlanilla, PlanillaMes, EstadoDiaPlanilla, NotaDia, SalienteDia, TIPOS_ESTADO_DIA


def _get_o_crear_planilla_mes(usuario, anyo, mes, unidad=None):
    if unidad is None:
        unidad = usuario.unidad
    planilla = PlanillaMes.query.filter_by(
        usuario_id=usuario.id, anyo=anyo, mes=mes, unidad_id=unidad.id,
    ).first()
    if planilla is None:
        planilla = PlanillaMes(usuario=usuario, anyo=anyo, mes=mes, publicada=False, unidad_id=unidad.id)
        db.session.add(planilla)
    return planilla


def _limpiar_estado_dia_sin_commit(usuario, fecha: date, unidad=None):
    """Elimina el EstadoDiaPlanilla del día si existe (sin commit)."""
    if unidad is None:
        unidad = usuario.unidad
    EstadoDiaPlanilla.query.filter_by(
        usuario_id=usuario.id, fecha=fecha, unidad_id=unidad.id,
    ).delete()


def _limpiar_turnos_dia_sin_commit(usuario, fecha: date, unidad=None):
    """Elimina todos los TurnoPlanilla del día si existen (sin commit)."""
    if unidad is None:
        unidad = usuario.unidad
    TurnoPlanilla.query.filter_by(
        usuario_id=usuario.id, fecha=fecha, unidad_id=unidad.id,
    ).delete()


def añadir_turno(usuario, fecha: date, franja_horaria_id: int, unidad=None, commit=True) -> TurnoPlanilla:
    """Añade un turno de trabajo. Limpia el estado especial del día si lo había.
    Idempotente: no falla si el mismo turno ya existe.

    Si commit=False, el caller es responsable de hacer db.session.commit()
    (útil para operaciones batch que procesan varios días con un solo commit).
    """
    if unidad is None:
        unidad = usuario.unidad
    existente = TurnoPlanilla.query.filter_by(
        usuario_id=usuario.id, fecha=fecha, franja_horaria_id=franja_horaria_id, unidad_id=unidad.id,
    ).first()
    if existente:
        return existente

    _limpiar_estado_dia_sin_commit(usuario, fecha, unidad)
    _get_o_crear_planilla_mes(usuario, fecha.year, fecha.month, unidad)
    turno = TurnoPlanilla(usuario=usuario, fecha=fecha, franja_horaria_id=franja_horaria_id, unidad_id=unidad.id)
    db.session.add(turno)
    if commit:
        db.session.commit()
    return turno


def eliminar_turno(usuario, fecha: date, franja_horaria_id: int) -> bool:
    """Elimina un turno de la planilla. Devuelve True si existía."""
    turno = TurnoPlanilla.query.filter_by(
        usuario_id=usuario.id, fecha=fecha, franja_horaria_id=franja_horaria_id,
    ).first()
    if turno is None:
        return False
    db.session.delete(turno)
    db.session.commit()
    return True


def establecer_estado_dia(usuario, fecha: date, tipo: str, unidad=None, commit=True) -> EstadoDiaPlanilla:
    """Marca el día como libre / vacaciones / no_disponible.
    Elimina los turnos de trabajo del día si los hubiera (son mutuamente excluyentes).

    Si commit=False, el caller es responsable de hacer db.session.commit()
    (útil para operaciones batch que procesan varios días con un solo commit).
    """
    if unidad is None:
        unidad = usuario.unidad
    if tipo not in TIPOS_ESTADO_DIA:
        raise ValueError(f"Tipo inválido: {tipo}")

    _limpiar_turnos_dia_sin_commit(usuario, fecha, unidad)

    estado = EstadoDiaPlanilla.query.filter_by(
        usuario_id=usuario.id, fecha=fecha, unidad_id=unidad.id,
    ).first()
    if estado is None:
        estado = EstadoDiaPlanilla(usuario=usuario, fecha=fecha, tipo=tipo, unidad_id=unidad.id)
        db.session.add(estado)
    else:
        estado.tipo = tipo

    _get_o_crear_planilla_mes(usuario, fecha.year, fecha.month, unidad)
    if commit:
        db.session.commit()
    return estado


def limpiar_dia(usuario, fecha: date, unidad=None):
    """Elimina toda la información del día (turnos, estado especial y saliente)."""
    if unidad is None:
        unidad = usuario.unidad
    _limpiar_turnos_dia_sin_commit(usuario, fecha, unidad)
    _limpiar_estado_dia_sin_commit(usuario, fecha, unidad)
    SalienteDia.query.filter_by(usuario_id=usuario.id, fecha=fecha, unidad_id=unidad.id).delete()
    db.session.commit()


def publicar_mes(usuario, anyo: int, mes: int, unidad=None) -> PlanillaMes:
    """Marca el mes como publicado, creando el registro si no existe."""
    if unidad is None:
        unidad = usuario.unidad
    planilla = _get_o_crear_planilla_mes(usuario, anyo, mes, unidad)
    planilla.publicada = True
    db.session.commit()
    return planilla


def despublicar_mes(usuario, anyo: int, mes: int, unidad=None) -> PlanillaMes | None:
    """Vuelve el mes a borrador. No hace nada si no existe el registro."""
    if unidad is None:
        unidad = usuario.unidad
    planilla = PlanillaMes.query.filter_by(
        usuario_id=usuario.id, anyo=anyo, mes=mes, unidad_id=unidad.id,
    ).first()
    if planilla:
        planilla.publicada = False
        db.session.commit()
    return planilla


def tiene_mes_publicado(usuario, fecha: date, unidad=None) -> bool:
    """True si el usuario tiene la planilla del mes de esa fecha publicada."""
    if unidad is None:
        unidad = usuario.unidad
    planilla = PlanillaMes.query.filter_by(
        usuario_id=usuario.id, anyo=fecha.year, mes=fecha.month, unidad_id=unidad.id,
    ).first()
    return planilla is not None and planilla.publicada


def get_turnos_mes(usuario, anyo: int, mes: int, unidad=None) -> list[TurnoPlanilla]:
    """Devuelve todos los turnos del mes ordenados por fecha."""
    if unidad is None:
        unidad = usuario.unidad
    return (
        TurnoPlanilla.query
        .filter_by(usuario_id=usuario.id, unidad_id=unidad.id)
        .filter(
            db.func.extract("year", TurnoPlanilla.fecha) == anyo,
            db.func.extract("month", TurnoPlanilla.fecha) == mes,
        )
        .order_by(TurnoPlanilla.fecha)
        .all()
    )


def franjas_trabajadas_en_fecha(usuario, fecha: date, unidad=None):
    """Devuelve las FranjaHoraria que el usuario trabaja ese día (vacío si
    está libre, de vacaciones o no tiene ningún turno asignado)."""
    if unidad is None:
        unidad = usuario.unidad
    turnos = TurnoPlanilla.query.filter_by(
        usuario_id=usuario.id, fecha=fecha, unidad_id=unidad.id,
    ).all()
    return [t.franja_horaria for t in turnos]


def dias_sin_cumplimentar(usuario, anyo: int, mes: int, unidad=None) -> list[date]:
    """Devuelve los días del mes que no tienen ningún TurnoPlanilla ni EstadoDiaPlanilla."""
    if unidad is None:
        unidad = usuario.unidad
    _, num_dias = _calendar.monthrange(anyo, mes)

    fechas_con_turno = {
        r.fecha for r in (
            TurnoPlanilla.query
            .filter_by(usuario_id=usuario.id, unidad_id=unidad.id)
            .filter(
                db.func.extract("year",  TurnoPlanilla.fecha) == anyo,
                db.func.extract("month", TurnoPlanilla.fecha) == mes,
            )
            .with_entities(TurnoPlanilla.fecha)
            .distinct()
            .all()
        )
    }
    fechas_con_estado = {
        r.fecha for r in (
            EstadoDiaPlanilla.query
            .filter_by(usuario_id=usuario.id, unidad_id=unidad.id)
            .filter(
                db.func.extract("year",  EstadoDiaPlanilla.fecha) == anyo,
                db.func.extract("month", EstadoDiaPlanilla.fecha) == mes,
            )
            .with_entities(EstadoDiaPlanilla.fecha)
            .all()
        )
    }
    dias_ok = fechas_con_turno | fechas_con_estado
    return [
        date(anyo, mes, d)
        for d in range(1, num_dias + 1)
        if date(anyo, mes, d) not in dias_ok
    ]


def get_estados_mes(usuario, anyo: int, mes: int, unidad=None) -> dict[date, EstadoDiaPlanilla]:
    """Devuelve un dict {fecha: EstadoDiaPlanilla} para el mes."""
    if unidad is None:
        unidad = usuario.unidad
    estados = (
        EstadoDiaPlanilla.query
        .filter_by(usuario_id=usuario.id, unidad_id=unidad.id)
        .filter(
            db.func.extract("year", EstadoDiaPlanilla.fecha) == anyo,
            db.func.extract("month", EstadoDiaPlanilla.fecha) == mes,
        )
        .all()
    )
    return {e.fecha: e for e in estados}


def limpiar_mes_usuario(usuario, anyo: int, mes: int, unidad=None):
    """Elimina todos los TurnoPlanilla, EstadoDiaPlanilla y SalienteDia
    del usuario para el mes indicado, sin commit."""
    if unidad is None:
        unidad = usuario.unidad
    TurnoPlanilla.query.filter_by(usuario_id=usuario.id, unidad_id=unidad.id).filter(
        db.func.extract("year", TurnoPlanilla.fecha) == anyo,
        db.func.extract("month", TurnoPlanilla.fecha) == mes,
    ).delete()
    EstadoDiaPlanilla.query.filter_by(usuario_id=usuario.id, unidad_id=unidad.id).filter(
        db.func.extract("year", EstadoDiaPlanilla.fecha) == anyo,
        db.func.extract("month", EstadoDiaPlanilla.fecha) == mes,
    ).delete()
    SalienteDia.query.filter_by(usuario_id=usuario.id, unidad_id=unidad.id).filter(
        db.func.extract("year", SalienteDia.fecha) == anyo,
        db.func.extract("month", SalienteDia.fecha) == mes,
    ).delete()


def get_notas_mes(usuario, anyo: int, mes: int, unidad=None) -> dict[date, NotaDia]:
    """Devuelve un dict {fecha: NotaDia} con las notas del mes."""
    if unidad is None:
        unidad = usuario.unidad
    notas = (
        NotaDia.query
        .filter_by(usuario_id=usuario.id, unidad_id=unidad.id)
        .filter(
            db.func.extract("year", NotaDia.fecha) == anyo,
            db.func.extract("month", NotaDia.fecha) == mes,
        )
        .all()
    )
    return {n.fecha: n for n in notas}


def marcar_saliente(usuario, fecha: date, unidad=None) -> SalienteDia:
    """Marca el día como saliente (post-guardia). Idempotente. No afecta a turnos ni EstadoDia."""
    if unidad is None:
        unidad = usuario.unidad
    existente = SalienteDia.query.filter_by(
        usuario_id=usuario.id, fecha=fecha, unidad_id=unidad.id,
    ).first()
    if existente:
        return existente
    _get_o_crear_planilla_mes(usuario, fecha.year, fecha.month, unidad)
    saliente = SalienteDia(usuario=usuario, fecha=fecha, unidad_id=unidad.id)
    db.session.add(saliente)
    db.session.commit()
    return saliente


def quitar_saliente(usuario, fecha: date) -> bool:
    """Elimina la marca de saliente del día. Devuelve True si existía."""
    saliente = SalienteDia.query.filter_by(usuario_id=usuario.id, fecha=fecha).first()
    if saliente is None:
        return False
    db.session.delete(saliente)
    db.session.commit()
    return True


def get_salientes_mes(usuario, anyo: int, mes: int, unidad=None) -> dict[date, bool]:
    """Devuelve un dict {fecha: True} para los días salientes del mes."""
    if unidad is None:
        unidad = usuario.unidad
    salientes = (
        SalienteDia.query
        .filter_by(usuario_id=usuario.id, unidad_id=unidad.id)
        .filter(
            db.func.extract("year", SalienteDia.fecha) == anyo,
            db.func.extract("month", SalienteDia.fecha) == mes,
        )
        .all()
    )
    return {s.fecha: True for s in salientes}


def guardar_nota_dia(usuario, fecha: date, texto: str, unidad=None) -> NotaDia | None:
    """Upsert de la nota del día. Si el texto queda vacío, elimina la nota."""
    if unidad is None:
        unidad = usuario.unidad
    texto = texto.strip()
    nota = NotaDia.query.filter_by(
        usuario_id=usuario.id, fecha=fecha, unidad_id=unidad.id,
    ).first()
    if not texto:
        if nota:
            db.session.delete(nota)
            db.session.commit()
        return None
    if nota is None:
        nota = NotaDia(usuario=usuario, fecha=fecha, texto=texto, unidad_id=unidad.id)
        db.session.add(nota)
    else:
        nota.texto = texto
    db.session.commit()
    return nota
