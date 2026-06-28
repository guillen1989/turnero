"""
Motor de compatibilidad de planilla.

Módulo puro: las funciones de cálculo no tocan la BD.
La función de consulta sí usa SQLAlchemy pero delega la lógica en las puras.
"""
from datetime import date, time
from dataclasses import dataclass

from app.extensions import db
from app.models.usuario import Usuario
from app.models.planilla import TurnoPlanilla, PlanillaMes, EstadoDiaPlanilla
from app.services.planilla import tiene_mes_publicado


@dataclass
class ResultadoCompatibilidad:
    libres: list          # usuarios libres ese día y disponibles para cambios
    compatibles: list     # usuarios con turno no solapante (posible doblaje)
    mostrar_nombres: bool  # False si el solicitante no tiene el mes publicado


def turnos_solapan(inicio_1: time, fin_1: time, inicio_2: time, fin_2: time) -> bool:
    """True si los dos intervalos de tiempo se solapan (exclusivo en los extremos)."""
    return inicio_1 < fin_2 and inicio_2 < fin_1


def compatibilidad_para_cedido(
    usuario_solicitante,
    fecha: date,
    hora_inicio: time,
    hora_fin: time,
) -> ResultadoCompatibilidad:
    """
    Para un turno cedido (fecha + horario), devuelve qué compañeros del mismo
    grupo y categoría están libres o tienen turno compatible (no solapante).

    Reglas:
    - Solo se consideran compañeros que hayan publicado su planilla para ese mes.
    - EstadoDiaPlanilla.tipo == 'libre' → libre y disponible (aparece en libres).
    - EstadoDiaPlanilla.tipo in ('vacaciones', 'no_disponible') → excluido.
    - Sin estado ni turnos → libre implícito (aparece en libres).
    - Con turnos → se comprueba solapamiento.
    - Si el solicitante no tiene el mes publicado, los nombres se ocultan.
    """
    mostrar_nombres = tiene_mes_publicado(usuario_solicitante, fecha)

    compañeros_con_planilla = (
        db.session.query(Usuario)
        .join(PlanillaMes, PlanillaMes.usuario_id == Usuario.id)
        .filter(
            Usuario.id != usuario_solicitante.id,
            Usuario.categoria_id == usuario_solicitante.categoria_id,
            PlanillaMes.anyo == fecha.year,
            PlanillaMes.mes == fecha.month,
            PlanillaMes.publicada == True,
        )
        .all()
    )

    grupo_solicitante = usuario_solicitante.grupo_intercambio
    compañeros_mismo_grupo = [
        u for u in compañeros_con_planilla
        if u.grupo_intercambio.id == grupo_solicitante.id
    ]

    libres = []
    compatibles = []

    for compañero in compañeros_mismo_grupo:
        estado = EstadoDiaPlanilla.query.filter_by(
            usuario_id=compañero.id, fecha=fecha
        ).first()

        if estado is not None:
            # Estado explícito: solo 'libre' cuenta; vacaciones y no_disponible se excluyen
            if estado.tipo == "libre":
                libres.append(compañero)
            continue  # vacaciones / no_disponible → ignorar

        turnos_dia = TurnoPlanilla.query.filter_by(
            usuario_id=compañero.id, fecha=fecha
        ).all()

        if not turnos_dia:
            libres.append(compañero)  # libre implícito
        else:
            tiene_solapamiento = any(
                turnos_solapan(
                    hora_inicio, hora_fin,
                    t.franja_horaria.hora_inicio, t.franja_horaria.hora_fin,
                )
                for t in turnos_dia
            )
            if not tiene_solapamiento:
                compatibles.append(compañero)

    return ResultadoCompatibilidad(
        libres=libres,
        compatibles=compatibles,
        mostrar_nombres=mostrar_nombres,
    )
