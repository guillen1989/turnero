from datetime import date, time
from app.models import (
    Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria,
    Usuario, TurnoPlanilla, PlanillaMes,
)
from app.services.planilla import añadir_turno, publicar_mes
from app.services.compatibilidad_planilla import (
    turnos_solapan, compatibilidad_para_cedido,
)


# ── Tests puros de turnos_solapan ─────────────────────────────────────────────

def test_solapan_totalmente():
    assert turnos_solapan(time(8), time(15), time(8), time(15))

def test_solapan_parcialmente_inicio():
    assert turnos_solapan(time(8), time(15), time(6), time(10))

def test_solapan_parcialmente_fin():
    assert turnos_solapan(time(8), time(15), time(12), time(20))

def test_solapan_uno_dentro_de_otro():
    assert turnos_solapan(time(8), time(20), time(10), time(14))

def test_no_solapan_consecutivos():
    # 8-15 y 15-22: comparten el extremo pero no se solapan
    assert not turnos_solapan(time(8), time(15), time(15), time(22))

def test_no_solapan_separados():
    assert not turnos_solapan(time(8), time(15), time(16), time(22))

def test_no_solapan_orden_inverso():
    assert not turnos_solapan(time(15), time(22), time(8), time(15))

def test_solapan_12h_diurno_con_manyana():
    # 12h diurno 8-20 solapa con mañana 8-15
    assert turnos_solapan(time(8), time(15), time(8), time(20))


# ── Tests de integración de compatibilidad_para_cedido ───────────────────────

def _crear_usuario(db, email, grupo, unidad, categoria):
    u = Usuario(nombre=email, email=email, unidad=unidad, categoria=categoria)
    u.set_password("pass")
    db.session.add(u)
    db.session.commit()
    return u


def _setup_base(db):
    hospital = Hospital(nombre="H-Test")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    unidad = Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo)
    categoria = Categoria(nombre="Enfermería")
    franja_m = FranjaHoraria(nombre="Mañana", hora_inicio=time(8), hora_fin=time(15), grupo_intercambio=grupo)
    franja_t = FranjaHoraria(nombre="Tarde", hora_inicio=time(15), hora_fin=time(22), grupo_intercambio=grupo)
    franja_12 = FranjaHoraria(nombre="12h", hora_inicio=time(8), hora_fin=time(20), grupo_intercambio=grupo)
    db.session.add_all([unidad, categoria, franja_m, franja_t, franja_12])
    db.session.commit()

    return unidad, categoria, franja_m, franja_t, franja_12


def test_compañero_libre_aparece_en_libres(db):
    unidad, cat, franja_m, franja_t, _ = _setup_base(db)
    solicitante = _crear_usuario(db, "sol@t.es", None, unidad, cat)
    compañero = _crear_usuario(db, "comp@t.es", None, unidad, cat)

    publicar_mes(solicitante, 2026, 7)
    publicar_mes(compañero, 2026, 7)
    # compañero no tiene turno el día 1 → está libre

    resultado = compatibilidad_para_cedido(solicitante, date(2026, 7, 1), time(8), time(15))

    assert compañero in resultado.libres
    assert compañero not in resultado.compatibles


def test_compañero_con_turno_no_solapante_aparece_en_compatibles(db):
    unidad, cat, franja_m, franja_t, _ = _setup_base(db)
    solicitante = _crear_usuario(db, "sol2@t.es", None, unidad, cat)
    compañero = _crear_usuario(db, "comp2@t.es", None, unidad, cat)

    publicar_mes(solicitante, 2026, 7)
    publicar_mes(compañero, 2026, 7)
    añadir_turno(compañero, date(2026, 7, 1), franja_t.id)  # tarde 15-22, no solapa con mañana

    resultado = compatibilidad_para_cedido(solicitante, date(2026, 7, 1), time(8), time(15))

    assert compañero in resultado.compatibles
    assert compañero not in resultado.libres


def test_compañero_con_turno_solapante_no_aparece(db):
    unidad, cat, franja_m, franja_t, franja_12 = _setup_base(db)
    solicitante = _crear_usuario(db, "sol3@t.es", None, unidad, cat)
    compañero = _crear_usuario(db, "comp3@t.es", None, unidad, cat)

    publicar_mes(solicitante, 2026, 7)
    publicar_mes(compañero, 2026, 7)
    añadir_turno(compañero, date(2026, 7, 1), franja_12.id)  # 12h diurno, solapa con mañana

    resultado = compatibilidad_para_cedido(solicitante, date(2026, 7, 1), time(8), time(15))

    assert compañero not in resultado.libres
    assert compañero not in resultado.compatibles


def test_compañero_sin_planilla_publicada_no_aparece(db):
    unidad, cat, franja_m, franja_t, _ = _setup_base(db)
    solicitante = _crear_usuario(db, "sol4@t.es", None, unidad, cat)
    compañero = _crear_usuario(db, "comp4@t.es", None, unidad, cat)

    publicar_mes(solicitante, 2026, 7)
    # compañero NO publica su planilla

    resultado = compatibilidad_para_cedido(solicitante, date(2026, 7, 1), time(8), time(15))

    assert compañero not in resultado.libres
    assert compañero not in resultado.compatibles


def test_mostrar_nombres_true_si_solicitante_tiene_mes_publicado(db):
    unidad, cat, franja_m, _, _ = _setup_base(db)
    solicitante = _crear_usuario(db, "sol5@t.es", None, unidad, cat)
    publicar_mes(solicitante, 2026, 7)

    resultado = compatibilidad_para_cedido(solicitante, date(2026, 7, 1), time(8), time(15))
    assert resultado.mostrar_nombres


def test_mostrar_nombres_false_si_solicitante_no_tiene_mes_publicado(db):
    unidad, cat, franja_m, _, _ = _setup_base(db)
    solicitante = _crear_usuario(db, "sol6@t.es", None, unidad, cat)
    # solicitante NO publica

    resultado = compatibilidad_para_cedido(solicitante, date(2026, 7, 1), time(8), time(15))
    assert not resultado.mostrar_nombres


def test_doblaje_solapante_excluye_compañero(db):
    unidad, cat, franja_m, franja_t, franja_12 = _setup_base(db)
    solicitante = _crear_usuario(db, "sol7@t.es", None, unidad, cat)
    compañero = _crear_usuario(db, "comp7@t.es", None, unidad, cat)

    publicar_mes(solicitante, 2026, 7)
    publicar_mes(compañero, 2026, 7)
    # doblaje: tarde (ok) + 12h que solapa → debe excluirse
    añadir_turno(compañero, date(2026, 7, 1), franja_t.id)
    añadir_turno(compañero, date(2026, 7, 1), franja_12.id)

    resultado = compatibilidad_para_cedido(solicitante, date(2026, 7, 1), time(8), time(15))

    assert compañero not in resultado.compatibles
    assert compañero not in resultado.libres
