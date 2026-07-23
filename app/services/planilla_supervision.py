from collections import namedtuple
from datetime import date

from flask_babel import gettext as _

from app.extensions import db
from app.models.documento_cambio import DocumentoCambio, ParticipanteDocumentoCambio
from app.models.planilla import AjustePlanillaSupervisora, EstadoDiaPlanilla, TurnoPlanilla
from app.models.usuario import Usuario

CambioDia = namedtuple("CambioDia", ["documento", "descripcion"])
from app.services.planilla import añadir_turno, establecer_estado_dia


def get_turnos_mes_unidad(unidad, anyo: int, mes: int) -> dict[tuple[int, date], list[TurnoPlanilla]]:
    """Todos los turnos del mes de todos los trabajadores de la unidad,
    agrupados por (usuario_id, fecha) en una sola consulta -- evita el N+1
    de pedir la planilla trabajador a trabajador al pintar la matriz de
    la supervisora.
    """
    turnos = (
        TurnoPlanilla.query
        .join(Usuario, TurnoPlanilla.usuario_id == Usuario.id)
        .filter(
            Usuario.unidad_id == unidad.id,
            db.func.extract("year", TurnoPlanilla.fecha) == anyo,
            db.func.extract("month", TurnoPlanilla.fecha) == mes,
        )
        .order_by(TurnoPlanilla.fecha)
        .all()
    )
    resultado: dict[tuple[int, date], list[TurnoPlanilla]] = {}
    for turno in turnos:
        resultado.setdefault((turno.usuario_id, turno.fecha), []).append(turno)
    return resultado


def get_conteos_presencia_mes_unidad(unidad, anyo: int, mes: int) -> dict[tuple[date, int], int]:
    """Cuántos trabajadores de la unidad tienen cada franja horaria asignada
    cada día del mes, agrupado por (fecha, franja_horaria_id) -- para pintar
    los contadores de presencia encima de las columnas de la matriz de la
    supervisora."""
    filas = (
        db.session.query(
            TurnoPlanilla.fecha,
            TurnoPlanilla.franja_horaria_id,
            db.func.count(TurnoPlanilla.id),
        )
        .join(Usuario, TurnoPlanilla.usuario_id == Usuario.id)
        .filter(
            Usuario.unidad_id == unidad.id,
            db.func.extract("year", TurnoPlanilla.fecha) == anyo,
            db.func.extract("month", TurnoPlanilla.fecha) == mes,
        )
        .group_by(TurnoPlanilla.fecha, TurnoPlanilla.franja_horaria_id)
        .all()
    )
    return {(fecha, franja_id): total for fecha, franja_id, total in filas}


def get_estados_mes_unidad(unidad, anyo: int, mes: int) -> dict[tuple[int, date], EstadoDiaPlanilla]:
    """Estados de día (libre/vacaciones/no_disponible) del mes de todos los
    trabajadores de la unidad, agrupados por (usuario_id, fecha)."""
    estados = (
        EstadoDiaPlanilla.query
        .join(Usuario, EstadoDiaPlanilla.usuario_id == Usuario.id)
        .filter(
            Usuario.unidad_id == unidad.id,
            db.func.extract("year", EstadoDiaPlanilla.fecha) == anyo,
            db.func.extract("month", EstadoDiaPlanilla.fecha) == mes,
        )
        .all()
    )
    return {(e.usuario_id, e.fecha): e for e in estados}


def _describir_cambio_dia(participante, fecha: date) -> str:
    """Describe un cambio autorizado desde el punto de vista de un
    participante concreto en un día concreto: con quién fue, qué turno y de
    qué fecha -- para que la supervisora no tenga que abrir el documento
    solo para saber de qué se trata al pasar el ratón por encima."""
    companeros = [
        p.usuario.nombre for p in participante.documento.participantes
        if p.usuario_id != participante.usuario_id
    ]
    companero = ", ".join(companeros) if companeros else "?"
    franja = (
        participante.turno_cede_franja if fecha == participante.turno_cede_fecha
        else participante.turno_recibe_franja
    )
    return _(
        "Cambio con %(companero)s (turno %(franja)s) del %(fecha)s",
        companero=companero, franja=franja.nombre, fecha=fecha.strftime("%d/%m/%Y"),
    )


def get_cambios_autorizados_mes_unidad(
    unidad, anyo: int, mes: int
) -> dict[tuple[int, date], CambioDia]:
    """Cambios ya autorizados (y no anulados) que afectan a la planilla de
    algún trabajador de la unidad este mes, agrupados por (usuario_id, fecha).
    Tanto el día cedido como el recibido cuentan como 'afectados' para ese
    participante -- la planilla ya refleja el estado final (ver
    volcar_documento_a_planillas), esto solo sirve para marcar en la matriz
    de la supervisora qué días vinieron de un cambio, con enlace al documento
    y una descripción de con quién/qué turno/qué fecha fue el cambio.
    """
    participantes = (
        ParticipanteDocumentoCambio.query
        .join(DocumentoCambio)
        .join(Usuario, ParticipanteDocumentoCambio.usuario_id == Usuario.id)
        .filter(
            Usuario.unidad_id == unidad.id,
            DocumentoCambio.decision_supervisora == "autorizado",
            DocumentoCambio.anulado.is_(False),
        )
        .all()
    )
    resultado: dict[tuple[int, date], CambioDia] = {}
    for p in participantes:
        for fecha in (p.turno_cede_fecha, p.turno_recibe_fecha):
            if fecha.year == anyo and fecha.month == mes:
                resultado[(p.usuario_id, fecha)] = CambioDia(
                    documento=p.documento,
                    descripcion=_describir_cambio_dia(p, fecha),
                )
    return resultado


def _describir_dia(trabajador, fecha: date) -> str:
    estado = EstadoDiaPlanilla.query.filter_by(usuario_id=trabajador.id, fecha=fecha).first()
    if estado:
        return estado.tipo
    turnos = TurnoPlanilla.query.filter_by(usuario_id=trabajador.id, fecha=fecha).all()
    if turnos:
        return ", ".join(t.franja_horaria.nombre for t in turnos)
    return "(vacío)"


def ajustar_turno_trabajador(
    supervisora, trabajador, fecha: date, tipo_estado: str | None = None,
    franja_id: int | None = None, motivo: str | None = None,
) -> AjustePlanillaSupervisora:
    """Sustituye el turno/estado del día de un trabajador por decisión
    unilateral de la supervisora (p. ej. asignarle un día libre) y deja
    un AjustePlanillaSupervisora con el antes/después para poder auditarlo.
    tipo_estado y franja_id son excluyentes; si ambos son None, el día
    queda sin turno ni estado.
    """
    descripcion_anterior = _describir_dia(trabajador, fecha)

    TurnoPlanilla.query.filter_by(usuario_id=trabajador.id, fecha=fecha).delete()
    EstadoDiaPlanilla.query.filter_by(usuario_id=trabajador.id, fecha=fecha).delete()
    db.session.commit()

    if tipo_estado:
        establecer_estado_dia(trabajador, fecha, tipo_estado)
    elif franja_id:
        añadir_turno(trabajador, fecha, franja_id)

    descripcion_nueva = _describir_dia(trabajador, fecha)

    ajuste = AjustePlanillaSupervisora(
        usuario=trabajador, realizado_por=supervisora, fecha=fecha,
        descripcion_anterior=descripcion_anterior, descripcion_nueva=descripcion_nueva,
        motivo=motivo,
    )
    db.session.add(ajuste)
    db.session.commit()
    return ajuste


def get_ajustes_mes_unidad(
    unidad, anyo: int, mes: int
) -> dict[tuple[int, date], AjustePlanillaSupervisora]:
    """Último ajuste unilateral de la supervisora sobre el turno/estado del
    día de cada trabajador de la unidad este mes, agrupados por
    (usuario_id, fecha) -- para señalar en la matriz qué días se tocaron
    a mano y poder ver el motivo.
    """
    ajustes = (
        AjustePlanillaSupervisora.query
        .join(Usuario, AjustePlanillaSupervisora.usuario_id == Usuario.id)
        .filter(
            Usuario.unidad_id == unidad.id,
            db.func.extract("year", AjustePlanillaSupervisora.fecha) == anyo,
            db.func.extract("month", AjustePlanillaSupervisora.fecha) == mes,
        )
        .order_by(AjustePlanillaSupervisora.fecha_creacion)
        .all()
    )
    resultado: dict[tuple[int, date], AjustePlanillaSupervisora] = {}
    for ajuste in ajustes:
        resultado[(ajuste.usuario_id, ajuste.fecha)] = ajuste
    return resultado
