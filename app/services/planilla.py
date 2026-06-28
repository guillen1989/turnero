import calendar as _calendar
from datetime import date
from app.extensions import db
from app.models.planilla import TurnoPlanilla, PlanillaMes, EstadoDiaPlanilla, NotaDia, SalienteDia, TIPOS_ESTADO_DIA


def _get_o_crear_planilla_mes(usuario, anyo, mes):
    planilla = PlanillaMes.query.filter_by(
        usuario_id=usuario.id, anyo=anyo, mes=mes
    ).first()
    if planilla is None:
        planilla = PlanillaMes(usuario=usuario, anyo=anyo, mes=mes, publicada=False)
        db.session.add(planilla)
    return planilla


def _limpiar_estado_dia_sin_commit(usuario, fecha: date):
    """Elimina el EstadoDiaPlanilla del día si existe (sin commit)."""
    EstadoDiaPlanilla.query.filter_by(
        usuario_id=usuario.id, fecha=fecha
    ).delete()


def _limpiar_turnos_dia_sin_commit(usuario, fecha: date):
    """Elimina todos los TurnoPlanilla del día si existen (sin commit)."""
    TurnoPlanilla.query.filter_by(
        usuario_id=usuario.id, fecha=fecha
    ).delete()


def añadir_turno(usuario, fecha: date, franja_horaria_id: int) -> TurnoPlanilla:
    """Añade un turno de trabajo. Limpia el estado especial del día si lo había.
    Idempotente: no falla si el mismo turno ya existe.
    """
    existente = TurnoPlanilla.query.filter_by(
        usuario_id=usuario.id, fecha=fecha, franja_horaria_id=franja_horaria_id
    ).first()
    if existente:
        return existente

    _limpiar_estado_dia_sin_commit(usuario, fecha)
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


def establecer_estado_dia(usuario, fecha: date, tipo: str) -> EstadoDiaPlanilla:
    """Marca el día como libre / vacaciones / no_disponible.
    Elimina los turnos de trabajo del día si los hubiera (son mutuamente excluyentes).
    """
    if tipo not in TIPOS_ESTADO_DIA:
        raise ValueError(f"Tipo inválido: {tipo}")

    _limpiar_turnos_dia_sin_commit(usuario, fecha)

    estado = EstadoDiaPlanilla.query.filter_by(
        usuario_id=usuario.id, fecha=fecha
    ).first()
    if estado is None:
        estado = EstadoDiaPlanilla(usuario=usuario, fecha=fecha, tipo=tipo)
        db.session.add(estado)
    else:
        estado.tipo = tipo

    _get_o_crear_planilla_mes(usuario, fecha.year, fecha.month)
    db.session.commit()
    return estado


def limpiar_dia(usuario, fecha: date):
    """Elimina toda la información del día (turnos, estado especial y saliente)."""
    _limpiar_turnos_dia_sin_commit(usuario, fecha)
    _limpiar_estado_dia_sin_commit(usuario, fecha)
    SalienteDia.query.filter_by(usuario_id=usuario.id, fecha=fecha).delete()
    db.session.commit()


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


def dias_sin_cumplimentar(usuario, anyo: int, mes: int) -> list[date]:
    """Devuelve los días del mes que no tienen ningún TurnoPlanilla ni EstadoDiaPlanilla."""
    _, num_dias = _calendar.monthrange(anyo, mes)

    fechas_con_turno = {
        r.fecha for r in (
            TurnoPlanilla.query
            .filter_by(usuario_id=usuario.id)
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
            .filter_by(usuario_id=usuario.id)
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


def get_estados_mes(usuario, anyo: int, mes: int) -> dict[date, EstadoDiaPlanilla]:
    """Devuelve un dict {fecha: EstadoDiaPlanilla} para el mes."""
    estados = (
        EstadoDiaPlanilla.query
        .filter_by(usuario_id=usuario.id)
        .filter(
            db.func.extract("year", EstadoDiaPlanilla.fecha) == anyo,
            db.func.extract("month", EstadoDiaPlanilla.fecha) == mes,
        )
        .all()
    )
    return {e.fecha: e for e in estados}


def get_notas_mes(usuario, anyo: int, mes: int) -> dict[date, NotaDia]:
    """Devuelve un dict {fecha: NotaDia} con las notas del mes."""
    notas = (
        NotaDia.query
        .filter_by(usuario_id=usuario.id)
        .filter(
            db.func.extract("year", NotaDia.fecha) == anyo,
            db.func.extract("month", NotaDia.fecha) == mes,
        )
        .all()
    )
    return {n.fecha: n for n in notas}


def marcar_saliente(usuario, fecha: date) -> SalienteDia:
    """Marca el día como saliente (post-guardia). Idempotente. No afecta a turnos ni EstadoDia."""
    existente = SalienteDia.query.filter_by(usuario_id=usuario.id, fecha=fecha).first()
    if existente:
        return existente
    _get_o_crear_planilla_mes(usuario, fecha.year, fecha.month)
    saliente = SalienteDia(usuario=usuario, fecha=fecha)
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


def get_salientes_mes(usuario, anyo: int, mes: int) -> dict[date, bool]:
    """Devuelve un dict {fecha: True} para los días salientes del mes."""
    salientes = (
        SalienteDia.query
        .filter_by(usuario_id=usuario.id)
        .filter(
            db.func.extract("year", SalienteDia.fecha) == anyo,
            db.func.extract("month", SalienteDia.fecha) == mes,
        )
        .all()
    )
    return {s.fecha: True for s in salientes}


def guardar_nota_dia(usuario, fecha: date, texto: str) -> NotaDia | None:
    """Upsert de la nota del día. Si el texto queda vacío, elimina la nota."""
    texto = texto.strip()
    nota = NotaDia.query.filter_by(usuario_id=usuario.id, fecha=fecha).first()
    if not texto:
        if nota:
            db.session.delete(nota)
            db.session.commit()
        return None
    if nota is None:
        nota = NotaDia(usuario=usuario, fecha=fecha, texto=texto)
        db.session.add(nota)
    else:
        nota.texto = texto
    db.session.commit()
    return nota
