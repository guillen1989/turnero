"""
Comprobación de factibilidad de una hoja de cambio contra las planillas
subidas: para cada participante, verifica que de verdad trabaja el turno
que dice ceder y que está libre para el turno que dice recibir.

Reutiliza las mismas reglas que el motor de compatibilidad de planilla
(app/services/compatibilidad_planilla.py) en vez de reinventarlas.
"""
from datetime import time, timedelta

from app.models import TurnoPlanilla, EstadoDiaPlanilla
from app.services.planilla import tiene_mes_publicado
from app.services.compatibilidad_planilla import turnos_solapan


def _cubre_periodo_nocturno(franja) -> bool:
    """True si el horario de la franja incluye algún instante entre las
    0:00 y las 6:00 (turnos de noche/nocturno de 12h que cruzan la
    medianoche, almacenados con hora_inicio > hora_fin)."""
    if franja.hora_inicio > franja.hora_fin:
        return franja.hora_fin > time(0, 0)
    return franja.hora_inicio < time(6, 0)


def _viola_descanso_nocturno(usuario, fecha, franja, fecha_cedida) -> bool:
    """Regla de descanso: ningún turno puede empezar antes de las 14:00 el
    día siguiente a un turno que cubra el periodo 0:00-6:00.

    `fecha_cedida` es el día que este mismo usuario cede en el mismo
    documento: si coincide con el día anterior o siguiente, ese turno deja
    de ser suyo con este cambio y no cuenta para la regla."""
    dia_anterior = fecha - timedelta(days=1)
    turnos_dia_anterior = [] if dia_anterior == fecha_cedida else TurnoPlanilla.query.filter_by(
        usuario_id=usuario.id, fecha=dia_anterior
    ).all()
    if franja.hora_inicio < time(14, 0) and any(
        _cubre_periodo_nocturno(t.franja_horaria) for t in turnos_dia_anterior
    ):
        return True

    if _cubre_periodo_nocturno(franja):
        dia_siguiente = fecha + timedelta(days=1)
        turnos_dia_siguiente = [] if dia_siguiente == fecha_cedida else TurnoPlanilla.query.filter_by(
            usuario_id=usuario.id, fecha=dia_siguiente
        ).all()
        if any(t.franja_horaria.hora_inicio < time(14, 0) for t in turnos_dia_siguiente):
            return True

    return False


def _trabaja_el_dia(usuario, fecha, fecha_hipotetica, fecha_cedida) -> bool:
    if fecha == fecha_hipotetica:
        return True
    if fecha == fecha_cedida:
        return False
    if EstadoDiaPlanilla.query.filter_by(usuario_id=usuario.id, fecha=fecha).first() is not None:
        return False
    return TurnoPlanilla.query.filter_by(usuario_id=usuario.id, fecha=fecha).first() is not None


def _contar_dias_consecutivos_trabajados(usuario, fecha, fecha_cedida) -> int:
    """Cuenta la racha de días seguidos trabajados que incluiría `fecha`,
    contando hacia atrás y hacia delante a partir de los turnos/estados ya
    persistidos, asumiendo que `fecha` se trabajaría (turno recibido).

    `fecha_cedida` es el día que este mismo usuario cede en el mismo
    documento: aunque las planillas publicadas todavía lo marquen como
    trabajado, deja de serlo con este cambio, así que no debe contar."""
    total = 1
    cursor = fecha - timedelta(days=1)
    while _trabaja_el_dia(usuario, cursor, fecha, fecha_cedida):
        total += 1
        cursor -= timedelta(days=1)
    cursor = fecha + timedelta(days=1)
    while _trabaja_el_dia(usuario, cursor, fecha, fecha_cedida):
        total += 1
        cursor += timedelta(days=1)
    return total


def _viola_limite_dias_consecutivos(usuario, fecha, fecha_cedida) -> bool:
    limite = usuario.grupo_intercambio.limite_dias_consecutivos
    return _contar_dias_consecutivos_trabajados(usuario, fecha, fecha_cedida) > limite


def _trabaja_turno(usuario, fecha, franja) -> bool:
    return TurnoPlanilla.query.filter_by(
        usuario_id=usuario.id, fecha=fecha, franja_horaria_id=franja.id
    ).first() is not None


def _libre_para_turno(usuario, fecha, franja) -> bool:
    estado = EstadoDiaPlanilla.query.filter_by(usuario_id=usuario.id, fecha=fecha).first()
    if estado is not None:
        return estado.tipo == "libre"

    turnos_dia = TurnoPlanilla.query.filter_by(usuario_id=usuario.id, fecha=fecha).all()
    if not turnos_dia:
        return True  # libre implícito

    return not any(
        turnos_solapan(
            franja.hora_inicio, franja.hora_fin,
            t.franja_horaria.hora_inicio, t.franja_horaria.hora_fin,
        )
        for t in turnos_dia
    )


def comprobar_factibilidad(documento) -> str:
    """
    Devuelve uno de ESTADOS_FACTIBILIDAD:
    - 'no_verificado': falta la planilla publicada de algún participante
      para alguno de los meses implicados (no se puede comprobar).
    - 'no_factible': hay planilla de todos, pero alguna parte no trabaja
      lo que dice ceder, no está libre para lo que dice recibir, o recibirlo
      violaría el límite de días consecutivos o el descanso tras una noche
      (reglas de comprobación de la supervisora).
    - 'factible': cuadra todo.
    """
    for p in documento.participantes:
        if not tiene_mes_publicado(p.usuario, p.turno_cede_fecha):
            return "no_verificado"
        if not tiene_mes_publicado(p.usuario, p.turno_recibe_fecha):
            return "no_verificado"

    for p in documento.participantes:
        if not _trabaja_turno(p.usuario, p.turno_cede_fecha, p.turno_cede_franja):
            return "no_factible"
        if not _libre_para_turno(p.usuario, p.turno_recibe_fecha, p.turno_recibe_franja):
            return "no_factible"
        if _viola_limite_dias_consecutivos(p.usuario, p.turno_recibe_fecha, p.turno_cede_fecha):
            return "no_factible"
        if _viola_descanso_nocturno(
            p.usuario, p.turno_recibe_fecha, p.turno_recibe_franja, p.turno_cede_fecha
        ):
            return "no_factible"

    return "factible"
