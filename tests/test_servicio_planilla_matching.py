from app.models import Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria, Usuario
from app.models.planilla_import import MapeoCodigoTurno, MapeoTrabajadorPlanilla
from app.services.planilla_matching import (
    resolver_franja,
    establecer_mapeo_codigo,
    resolver_o_crear_trabajador,
    vincular_usuario,
    trabajadores_sin_vincular,
)
from app.extensions import db


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
    bd.session.add_all([manyana, tarde])
    bd.session.commit()

    return grupo, unidad, categoria, manyana, tarde


def test_resolver_franja_devuelve_none_si_no_hay_mapeo(db):
    grupo, unidad, categoria, manyana, tarde = _crear_contexto(db)
    assert resolver_franja(grupo, "M") is None


def test_establecer_mapeo_codigo_crea_el_mapeo(db):
    grupo, unidad, categoria, manyana, tarde = _crear_contexto(db)
    establecer_mapeo_codigo(grupo, "M", manyana)
    assert resolver_franja(grupo, "M") == manyana


def test_establecer_mapeo_codigo_es_idempotente(db):
    grupo, unidad, categoria, manyana, tarde = _crear_contexto(db)
    establecer_mapeo_codigo(grupo, "M", manyana)
    establecer_mapeo_codigo(grupo, "M", manyana)
    assert MapeoCodigoTurno.query.filter_by(grupo_intercambio_id=grupo.id, codigo="M").count() == 1


def test_establecer_mapeo_codigo_permite_reconfigurar_la_franja(db):
    grupo, unidad, categoria, manyana, tarde = _crear_contexto(db)
    establecer_mapeo_codigo(grupo, "MC", manyana)
    establecer_mapeo_codigo(grupo, "MC", tarde)
    assert resolver_franja(grupo, "MC") == tarde


def test_resolver_o_crear_trabajador_crea_nuevo_sin_vincular(db):
    grupo, unidad, categoria, manyana, tarde = _crear_contexto(db)
    trabajador = resolver_o_crear_trabajador(unidad, "12345", "PÉREZ, ANA")
    assert trabajador.usuario_id is None
    assert trabajador.nombre_planilla == "PÉREZ, ANA"
    assert MapeoTrabajadorPlanilla.query.count() == 1


def test_resolver_o_crear_trabajador_reutiliza_el_existente(db):
    grupo, unidad, categoria, manyana, tarde = _crear_contexto(db)
    primero = resolver_o_crear_trabajador(unidad, "12345", "PÉREZ, ANA")
    segundo = resolver_o_crear_trabajador(unidad, "12345", "PÉREZ, ANA")
    assert primero.id == segundo.id
    assert MapeoTrabajadorPlanilla.query.count() == 1


def test_resolver_o_crear_trabajador_actualiza_nombre_pero_conserva_vinculo(db):
    grupo, unidad, categoria, manyana, tarde = _crear_contexto(db)
    usuario = Usuario(nombre="Ana Pérez", email="ana@hospital.es", unidad=unidad, categoria=categoria)
    usuario.set_password("segura123")
    db.session.add(usuario)
    db.session.commit()

    trabajador = resolver_o_crear_trabajador(unidad, "12345", "PEREZ, ANA")
    vincular_usuario(trabajador, usuario)

    actualizado = resolver_o_crear_trabajador(unidad, "12345", "PÉREZ, ANA MARÍA")
    assert actualizado.id == trabajador.id
    assert actualizado.nombre_planilla == "PÉREZ, ANA MARÍA"
    assert actualizado.usuario_id == usuario.id


def test_vincular_usuario(db):
    grupo, unidad, categoria, manyana, tarde = _crear_contexto(db)
    usuario = Usuario(nombre="Ana Pérez", email="ana@hospital.es", unidad=unidad, categoria=categoria)
    usuario.set_password("segura123")
    db.session.add(usuario)
    db.session.commit()

    trabajador = resolver_o_crear_trabajador(unidad, "12345", "PÉREZ, ANA")
    vincular_usuario(trabajador, usuario)

    recuperado = db.session.get(MapeoTrabajadorPlanilla, trabajador.id)
    assert recuperado.usuario_id == usuario.id


def test_trabajadores_sin_vincular_excluye_los_ya_vinculados(db):
    grupo, unidad, categoria, manyana, tarde = _crear_contexto(db)
    usuario = Usuario(nombre="Ana Pérez", email="ana@hospital.es", unidad=unidad, categoria=categoria)
    usuario.set_password("segura123")
    db.session.add(usuario)
    db.session.commit()

    vinculado = resolver_o_crear_trabajador(unidad, "12345", "PÉREZ, ANA")
    vincular_usuario(vinculado, usuario)
    sin_vincular = resolver_o_crear_trabajador(unidad, "99999", "GÓMEZ, LUIS")

    pendientes = trabajadores_sin_vincular(unidad)
    assert pendientes == [sin_vincular]


def test_usuarios_disponibles_para_vincular_excluye_ya_vinculados(db):
    grupo, unidad, categoria, manyana, tarde = _crear_contexto(db)
    ana = Usuario(nombre="Ana Pérez", email="ana@hospital.es", unidad=unidad, categoria=categoria)
    ana.set_password("segura123")
    luis = Usuario(nombre="Luis Gómez", email="luis@hospital.es", unidad=unidad, categoria=categoria)
    luis.set_password("segura123")
    db.session.add_all([ana, luis])
    db.session.commit()

    trabajador = resolver_o_crear_trabajador(unidad, "12345", "PÉREZ, ANA")
    vincular_usuario(trabajador, ana)

    from app.services.planilla_matching import usuarios_disponibles_para_vincular
    disponibles = usuarios_disponibles_para_vincular(unidad)
    assert disponibles == [luis]


def test_sugerir_trabajador_planilla_encuentra_coincidencia_con_orden_distinto(db):
    grupo, unidad, categoria, manyana, tarde = _crear_contexto(db)
    pendiente = resolver_o_crear_trabajador(unidad, "12345", "PÉREZ, ANA")

    from app.services.planilla_matching import sugerir_trabajador_planilla
    sugerencia = sugerir_trabajador_planilla(unidad, "Ana Pérez")
    assert sugerencia.id == pendiente.id


def test_sugerir_trabajador_planilla_ignora_mayusculas_y_acentos(db):
    grupo, unidad, categoria, manyana, tarde = _crear_contexto(db)
    pendiente = resolver_o_crear_trabajador(unidad, "12345", "GÓMEZ RUIZ, LUIS")

    from app.services.planilla_matching import sugerir_trabajador_planilla
    sugerencia = sugerir_trabajador_planilla(unidad, "luis gomez ruiz")
    assert sugerencia.id == pendiente.id


def test_sugerir_trabajador_planilla_devuelve_none_si_no_coincide(db):
    grupo, unidad, categoria, manyana, tarde = _crear_contexto(db)
    resolver_o_crear_trabajador(unidad, "12345", "PÉREZ, ANA")

    from app.services.planilla_matching import sugerir_trabajador_planilla
    assert sugerir_trabajador_planilla(unidad, "Luis Gómez") is None


def test_sugerir_trabajador_planilla_ignora_los_ya_vinculados(db):
    grupo, unidad, categoria, manyana, tarde = _crear_contexto(db)
    usuario = Usuario(nombre="Ana Pérez", email="ana@hospital.es", unidad=unidad, categoria=categoria)
    usuario.set_password("segura123")
    db.session.add(usuario)
    db.session.commit()

    vinculado = resolver_o_crear_trabajador(unidad, "12345", "PÉREZ, ANA")
    vincular_usuario(vinculado, usuario)

    from app.services.planilla_matching import sugerir_trabajador_planilla
    assert sugerir_trabajador_planilla(unidad, "Ana Pérez") is None


def test_sugerir_trabajador_planilla_no_sugiere_coincidencia_parcial(db):
    grupo, unidad, categoria, manyana, tarde = _crear_contexto(db)
    resolver_o_crear_trabajador(unidad, "12345", "PÉREZ GÓMEZ, ANA MARÍA")

    from app.services.planilla_matching import sugerir_trabajador_planilla
    assert sugerir_trabajador_planilla(unidad, "Ana Pérez") is None
