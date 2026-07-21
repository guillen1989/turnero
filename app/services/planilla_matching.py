"""
Resolución persistente de los dos mapeos que necesita la carga masiva de
planilla: código de turno -> FranjaHoraria (por grupo de intercambio) y
trabajador de planilla -> Usuario (por unidad, identificado por su número de
empleado, estable entre cargas mensuales).
"""
from app.extensions import db
from app.models.planilla_import import MapeoCodigoTurno, MapeoTrabajadorPlanilla
from app.models.usuario import Usuario


def resolver_franja(grupo_intercambio, codigo: str):
    """Devuelve la FranjaHoraria mapeada para ese código en ese grupo, o None
    si todavía no se ha configurado."""
    mapeo = MapeoCodigoTurno.query.filter_by(
        grupo_intercambio_id=grupo_intercambio.id, codigo=codigo
    ).first()
    return mapeo.franja_horaria if mapeo else None


def establecer_mapeo_codigo(grupo_intercambio, codigo: str, franja_horaria) -> MapeoCodigoTurno:
    """Crea o reconfigura el mapeo código -> franja para ese grupo. Idempotente."""
    mapeo = MapeoCodigoTurno.query.filter_by(
        grupo_intercambio_id=grupo_intercambio.id, codigo=codigo
    ).first()
    if mapeo is None:
        mapeo = MapeoCodigoTurno(
            grupo_intercambio=grupo_intercambio, codigo=codigo, franja_horaria=franja_horaria
        )
        db.session.add(mapeo)
    else:
        mapeo.franja_horaria = franja_horaria
    db.session.commit()
    return mapeo


def resolver_o_crear_trabajador(unidad, numero_empleado: str, nombre_planilla: str) -> MapeoTrabajadorPlanilla:
    """Recupera el mapeo persistente de ese trabajador en esa unidad (por
    número de empleado) o lo crea sin vincular si es la primera vez que
    aparece. Si ya existía, actualiza el nombre por si cambió en la nueva
    carga, pero conserva el usuario_id ya vinculado.
    """
    trabajador = MapeoTrabajadorPlanilla.query.filter_by(
        unidad_id=unidad.id, numero_empleado=numero_empleado
    ).first()
    if trabajador is None:
        trabajador = MapeoTrabajadorPlanilla(
            unidad=unidad, numero_empleado=numero_empleado, nombre_planilla=nombre_planilla
        )
        db.session.add(trabajador)
    else:
        trabajador.nombre_planilla = nombre_planilla
    db.session.commit()
    return trabajador


def vincular_usuario(trabajador: MapeoTrabajadorPlanilla, usuario) -> MapeoTrabajadorPlanilla:
    """Asocia definitivamente ese mapeo de planilla a un Usuario real."""
    trabajador.usuario = usuario
    db.session.commit()
    return trabajador


def trabajadores_sin_vincular(unidad) -> list[MapeoTrabajadorPlanilla]:
    """Trabajadores de esa unidad que ya aparecieron en alguna planilla
    importada pero todavía no tienen Usuario asociado. Para que la
    supervisora los revise."""
    return MapeoTrabajadorPlanilla.query.filter_by(
        unidad_id=unidad.id, usuario_id=None
    ).all()


def usuarios_disponibles_para_vincular(unidad) -> list:
    """Usuarios de esa unidad que todavía no están vinculados a ningún
    MapeoTrabajadorPlanilla, para ofrecerlos como opciones al confirmar
    manualmente un vínculo."""
    ya_vinculados = {
        m.usuario_id
        for m in MapeoTrabajadorPlanilla.query.filter(
            MapeoTrabajadorPlanilla.unidad_id == unidad.id,
            MapeoTrabajadorPlanilla.usuario_id.isnot(None),
        ).all()
    }
    return [
        u for u in Usuario.query.filter_by(unidad_id=unidad.id).all()
        if u.id not in ya_vinculados
    ]
