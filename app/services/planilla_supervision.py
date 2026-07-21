from datetime import date

from app.extensions import db
from app.models.documento_cambio import DocumentoCambio, ParticipanteDocumentoCambio
from app.models.planilla import EstadoDiaPlanilla, TurnoPlanilla
from app.models.usuario import Usuario


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


def get_cambios_autorizados_mes_unidad(
    unidad, anyo: int, mes: int
) -> dict[tuple[int, date], DocumentoCambio]:
    """Cambios ya autorizados (y no anulados) que afectan a la planilla de
    algún trabajador de la unidad este mes, agrupados por (usuario_id, fecha).
    Tanto el día cedido como el recibido cuentan como 'afectados' para ese
    participante -- la planilla ya refleja el estado final (ver
    volcar_documento_a_planillas), esto solo sirve para marcar en la matriz
    de la supervisora qué días vinieron de un cambio, con enlace al documento.
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
    resultado: dict[tuple[int, date], DocumentoCambio] = {}
    for p in participantes:
        for fecha in (p.turno_cede_fecha, p.turno_recibe_fecha):
            if fecha.year == anyo and fecha.month == mes:
                resultado[(p.usuario_id, fecha)] = p.documento
    return resultado
