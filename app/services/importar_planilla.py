"""
Orquestador de la carga masiva de planilla: une el parser puro
(app/services/planilla_import.py), la resolución de mapeos persistentes
(app/services/planilla_matching.py) y la escritura real en TurnoPlanilla
(app/services/planilla.py).

Todo o nada respecto a los códigos de turno: si falta el mapeo de algún
código a FranjaHoraria para el grupo de la unidad, no escribe nada y lo
reporta, en vez de importar unos turnos sí y otros no silenciosamente.

Los trabajadores sin Usuario vinculado no bloquean la importación: se
registran (o actualizan) como pendientes para que la supervisora los
revise, y sus turnos no se escriben hasta que se vinculen.
"""
from dataclasses import dataclass, field

from app.services.planilla_import import parsear_planilla_ilog
from app.services.planilla_matching import resolver_franja, resolver_o_crear_trabajador
from app.services.planilla import añadir_turno, publicar_mes, limpiar_mes_usuario
from app.services.compat_planilla_persistente import actualizar_compat_tras_importar_mes


@dataclass
class ResultadoImportacionPlanilla:
    codigos_sin_mapear: set = field(default_factory=set)
    trabajadores_actualizados: list = field(default_factory=list)
    trabajadores_pendientes: list = field(default_factory=list)


def importar_planilla(contenido: str, unidad) -> ResultadoImportacionPlanilla:
    planilla = parsear_planilla_ilog(contenido)
    grupo = unidad.grupo_intercambio

    codigos_usados = {
        codigo
        for trabajador in planilla.trabajadores
        for codigo in trabajador.turnos.values()
    }
    franja_por_codigo = {codigo: resolver_franja(grupo, codigo) for codigo in codigos_usados}
    codigos_sin_mapear = {c for c, franja in franja_por_codigo.items() if franja is None}
    if codigos_sin_mapear:
        return ResultadoImportacionPlanilla(codigos_sin_mapear=codigos_sin_mapear)

    resultado = ResultadoImportacionPlanilla()

    for trabajador in planilla.trabajadores:
        mapeo = resolver_o_crear_trabajador(
            unidad, trabajador.numero_empleado, trabajador.nombre_planilla
        )
        if mapeo.usuario_id is None:
            resultado.trabajadores_pendientes.append(mapeo)
            continue

        usuario = mapeo.usuario
        limpiar_mes_usuario(usuario, planilla.anyo, planilla.mes)
        for fecha, codigo in trabajador.turnos.items():
            franja = franja_por_codigo[codigo]
            añadir_turno(usuario, fecha, franja.id)
        publicar_mes(usuario, planilla.anyo, planilla.mes)
        resultado.trabajadores_actualizados.append(usuario)

    if resultado.trabajadores_actualizados:
        actualizar_compat_tras_importar_mes(grupo, planilla.anyo, planilla.mes)

    return resultado
