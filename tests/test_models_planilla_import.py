import pytest
from app.models import Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria, Usuario
from app.models.planilla_import import MapeoCodigoTurno, MapeoTrabajadorPlanilla


def _crear_contexto(db):
    hospital = Hospital(nombre="Hospital Test")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    unidad = Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo)
    categoria = Categoria(nombre="Enfermería")
    db.session.add_all([unidad, categoria])
    db.session.commit()

    franja = FranjaHoraria(
        nombre="Mañana", hora_inicio="08:00", hora_fin="15:00", grupo_intercambio=grupo
    )
    db.session.add(franja)
    db.session.commit()

    return grupo, unidad, categoria, franja


def test_crear_mapeo_codigo_turno(db):
    grupo, unidad, categoria, franja = _crear_contexto(db)

    mapeo = MapeoCodigoTurno(grupo_intercambio=grupo, codigo="M", franja_horaria=franja)
    db.session.add(mapeo)
    db.session.commit()

    recuperado = db.session.get(MapeoCodigoTurno, mapeo.id)
    assert recuperado.codigo == "M"
    assert recuperado.franja_horaria_id == franja.id


def test_codigo_turno_unico_por_grupo(db):
    grupo, unidad, categoria, franja = _crear_contexto(db)

    db.session.add(MapeoCodigoTurno(grupo_intercambio=grupo, codigo="M", franja_horaria=franja))
    db.session.commit()

    db.session.add(MapeoCodigoTurno(grupo_intercambio=grupo, codigo="M", franja_horaria=franja))
    with pytest.raises(Exception):
        db.session.commit()


def test_mismo_codigo_en_grupos_distintos_es_valido(db):
    grupo, unidad, categoria, franja = _crear_contexto(db)
    otro_grupo = GrupoIntercambio()
    db.session.add(otro_grupo)
    db.session.commit()
    otra_franja = FranjaHoraria(
        nombre="Mañana", hora_inicio="08:00", hora_fin="15:00", grupo_intercambio=otro_grupo
    )
    db.session.add(otra_franja)
    db.session.commit()

    db.session.add(MapeoCodigoTurno(grupo_intercambio=grupo, codigo="M", franja_horaria=franja))
    db.session.add(MapeoCodigoTurno(grupo_intercambio=otro_grupo, codigo="M", franja_horaria=otra_franja))
    db.session.commit()

    assert MapeoCodigoTurno.query.filter_by(codigo="M").count() == 2


def test_crear_mapeo_trabajador_sin_vincular(db):
    grupo, unidad, categoria, franja = _crear_contexto(db)

    mapeo = MapeoTrabajadorPlanilla(
        unidad=unidad, numero_empleado="12345", nombre_planilla="PÉREZ, ANA"
    )
    db.session.add(mapeo)
    db.session.commit()

    recuperado = db.session.get(MapeoTrabajadorPlanilla, mapeo.id)
    assert recuperado.usuario_id is None
    assert recuperado.nombre_planilla == "PÉREZ, ANA"


def test_vincular_mapeo_trabajador_a_usuario(db):
    grupo, unidad, categoria, franja = _crear_contexto(db)
    usuario = Usuario(nombre="Ana Pérez", email="ana@hospital.es", unidad=unidad, categoria=categoria)
    usuario.set_password("segura123")
    db.session.add(usuario)
    db.session.commit()

    mapeo = MapeoTrabajadorPlanilla(
        unidad=unidad, numero_empleado="12345", nombre_planilla="PÉREZ, ANA", usuario=usuario
    )
    db.session.add(mapeo)
    db.session.commit()

    recuperado = db.session.get(MapeoTrabajadorPlanilla, mapeo.id)
    assert recuperado.usuario_id == usuario.id


def test_numero_empleado_unico_por_unidad(db):
    grupo, unidad, categoria, franja = _crear_contexto(db)

    db.session.add(MapeoTrabajadorPlanilla(unidad=unidad, numero_empleado="12345", nombre_planilla="PÉREZ, ANA"))
    db.session.commit()

    db.session.add(MapeoTrabajadorPlanilla(unidad=unidad, numero_empleado="12345", nombre_planilla="OTRO, NOMBRE"))
    with pytest.raises(Exception):
        db.session.commit()


def test_mismo_numero_empleado_en_unidades_distintas_es_valido(db):
    grupo, unidad, categoria, franja = _crear_contexto(db)
    hospital2 = Hospital(nombre="Hospital Test 2")
    db.session.add(hospital2)
    db.session.commit()
    otra_unidad = Unidad(nombre="Cardiología", hospital=hospital2, grupo_intercambio=grupo)
    db.session.add(otra_unidad)
    db.session.commit()

    db.session.add(MapeoTrabajadorPlanilla(unidad=unidad, numero_empleado="12345", nombre_planilla="PÉREZ, ANA"))
    db.session.add(MapeoTrabajadorPlanilla(unidad=otra_unidad, numero_empleado="12345", nombre_planilla="OTRO, NOMBRE"))
    db.session.commit()

    assert MapeoTrabajadorPlanilla.query.filter_by(numero_empleado="12345").count() == 2
