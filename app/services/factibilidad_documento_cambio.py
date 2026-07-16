"""
Comprobación de factibilidad de una hoja de cambio contra las planillas
subidas: para cada participante, verifica que de verdad trabaja el turno
que dice ceder y que está libre para el turno que dice recibir.

Reutiliza las mismas reglas que el motor de compatibilidad de planilla
(app/services/compatibilidad_planilla.py) en vez de reinventarlas.
"""
from app.models import TurnoPlanilla, EstadoDiaPlanilla
from app.services.planilla import tiene_mes_publicado
from app.services.compatibilidad_planilla import turnos_solapan


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
      lo que dice ceder o no está libre para lo que dice recibir.
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

    return "factible"
