from datetime import date

from app.models import (
    Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria, Usuario,
    TurnoPlanilla,
)
from app.models.planilla_import import MapeoTrabajadorPlanilla
from app.services.planilla_matching import (
    establecer_mapeo_codigo, resolver_o_crear_trabajador, vincular_usuario,
)
from app.services.planilla import tiene_mes_publicado
from app.services.importar_planilla import importar_planilla
from app.extensions import db

CONTENIDO = (
    "Informe\n"
    "\tFecha inicial:\t01/01/2024\t\n"
    "\tFecha final:\t31/01/2024\t\n"
    "\tUnidad:\tPRUEBA\n"
    "\tDias\t\t1\t2\n"
    "\t\n"
    "\tPEREZ, ANA\t11111\tM\tT\n"
)

CONTENIDO_FEBRERO = (
    "Informe\n"
    "\tFecha inicial:\t01/02/2024\t\n"
    "\tFecha final:\t29/02/2024\t\n"
    "\tUnidad:\tPRUEBA\n"
    "\tDias\t\t1\t2\n"
    "\t\n"
    "\tPEREZ, ANA\t11111\tN\t\n"
)


def _crear_contexto(bd):
    hospital = Hospital(nombre="Hospital Test")
    grupo = GrupoIntercambio()
    bd.session.add_all([hospital, grupo])
    bd.session.commit()

    unidad = Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo)
    categoria = Categoria(nombre="Enfermería")
    bd.session.add_all([unidad, categoria])
    bd.session.commit()

    manyana = FranjaHoraria(nombre="Mañana", hora_inicio="08:00", hora_fin="15:00", grupo_intercambio=grupo)
    tarde = FranjaHoraria(nombre="Tarde", hora_inicio="15:00", hora_fin="22:00", grupo_intercambio=grupo)
    noche = FranjaHoraria(nombre="Noche", hora_inicio="22:00", hora_fin="08:00", grupo_intercambio=grupo)
    bd.session.add_all([manyana, tarde, noche])
    bd.session.commit()

    return grupo, unidad, categoria, manyana, tarde, noche


def test_importar_planilla_falla_si_faltan_codigos_sin_mapear(db):
    grupo, unidad, categoria, manyana, tarde, noche = _crear_contexto(db)

    resultado = importar_planilla(CONTENIDO, unidad)

    assert resultado.codigos_sin_mapear == {"M", "T"}
    assert TurnoPlanilla.query.count() == 0
    assert MapeoTrabajadorPlanilla.query.count() == 0


def test_importar_planilla_deja_pendiente_a_trabajador_sin_usuario(db):
    grupo, unidad, categoria, manyana, tarde, noche = _crear_contexto(db)
    establecer_mapeo_codigo(grupo, "M", manyana)
    establecer_mapeo_codigo(grupo, "T", tarde)

    resultado = importar_planilla(CONTENIDO, unidad)

    assert resultado.codigos_sin_mapear == set()
    assert len(resultado.trabajadores_pendientes) == 1
    assert resultado.trabajadores_pendientes[0].nombre_planilla == "PEREZ, ANA"
    assert resultado.trabajadores_actualizados == []
    assert TurnoPlanilla.query.count() == 0
    assert MapeoTrabajadorPlanilla.query.count() == 1


def test_importar_planilla_escribe_turnos_para_trabajador_vinculado(db):
    grupo, unidad, categoria, manyana, tarde, noche = _crear_contexto(db)
    establecer_mapeo_codigo(grupo, "M", manyana)
    establecer_mapeo_codigo(grupo, "T", tarde)

    usuario = Usuario(nombre="Ana Pérez", email="ana@hospital.es", unidad=unidad, categoria=categoria)
    usuario.set_password("segura123")
    db.session.add(usuario)
    db.session.commit()
    trabajador = resolver_o_crear_trabajador(unidad, "11111", "PEREZ, ANA")
    vincular_usuario(trabajador, usuario)

    resultado = importar_planilla(CONTENIDO, unidad)

    assert resultado.trabajadores_pendientes == []
    assert resultado.trabajadores_actualizados == [usuario]

    turnos = TurnoPlanilla.query.filter_by(usuario_id=usuario.id).all()
    turnos_por_fecha = {t.fecha: t.franja_horaria_id for t in turnos}
    assert turnos_por_fecha == {
        date(2024, 1, 1): manyana.id,
        date(2024, 1, 2): tarde.id,
    }
    assert tiene_mes_publicado(usuario, date(2024, 1, 1))


def test_importar_planilla_reutiliza_vinculo_en_carga_del_mes_siguiente(db):
    grupo, unidad, categoria, manyana, tarde, noche = _crear_contexto(db)
    establecer_mapeo_codigo(grupo, "M", manyana)
    establecer_mapeo_codigo(grupo, "T", tarde)
    establecer_mapeo_codigo(grupo, "N", noche)

    usuario = Usuario(nombre="Ana Pérez", email="ana@hospital.es", unidad=unidad, categoria=categoria)
    usuario.set_password("segura123")
    db.session.add(usuario)
    db.session.commit()
    trabajador = resolver_o_crear_trabajador(unidad, "11111", "PEREZ, ANA")
    vincular_usuario(trabajador, usuario)

    importar_planilla(CONTENIDO, unidad)
    resultado_febrero = importar_planilla(CONTENIDO_FEBRERO, unidad)

    assert resultado_febrero.trabajadores_actualizados == [usuario]
    assert MapeoTrabajadorPlanilla.query.count() == 1

    turno_febrero = TurnoPlanilla.query.filter_by(
        usuario_id=usuario.id, fecha=date(2024, 2, 1)
    ).first()
    assert turno_febrero.franja_horaria_id == noche.id
    assert tiene_mes_publicado(usuario, date(2024, 2, 1))
