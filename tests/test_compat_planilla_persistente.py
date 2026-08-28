"""
Tests para el servicio de compatibilidad persistente:
- calcular_y_guardar_compatibilidad
- actualizar_compat_tras_publicar_planilla
- dias_sin_cumplimentar
"""
from datetime import date, time, timedelta

import pytest

from app.models import (
    Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria,
    Usuario, CompatibilidadPlanilla,
)
from app.services.planilla import (
    añadir_turno, publicar_mes, establecer_estado_dia, dias_sin_cumplimentar,
)
from app.services.publicaciones import publicar_cambio
from app.services.compat_planilla_persistente import (
    calcular_y_guardar_compatibilidad,
    actualizar_compat_tras_publicar_planilla,
)


def _setup(db, suffix="A"):
    hospital = Hospital(nombre=f"H-{suffix}")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    unidad = Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo)
    categoria = Categoria(nombre=f"Cat-{suffix}")
    franja_m = FranjaHoraria(
        nombre="Mañana", hora_inicio=time(8), hora_fin=time(15),
        grupo_intercambio=grupo,
    )
    franja_t = FranjaHoraria(
        nombre="Tarde", hora_inicio=time(15), hora_fin=time(22),
        grupo_intercambio=grupo,
    )
    db.session.add_all([unidad, categoria, franja_m, franja_t])
    db.session.commit()

    def crear(email):
        u = Usuario(nombre=email.split("@")[0], email=email, unidad=unidad, categoria=categoria)
        u.set_password("pass")
        db.session.add(u)
        db.session.commit()
        return u

    return unidad, categoria, franja_m, franja_t, crear


# ── dias_sin_cumplimentar ─────────────────────────────────────────────────────

@pytest.mark.parametrize("dias_llenos,esperado_vacios", [
    (0, 31),   # mes vacío: julio tiene 31 días
    (10, 21),  # mes parcial: primeros 10 días cumplimentados
    (31, 0),   # mes completo
], ids=["vacio", "parcial", "completo"])
def test_dias_sin_cumplimentar_segun_dias_cumplimentados(db, dias_llenos, esperado_vacios):
    _, _, franja_m, _, crear = _setup(db, f"d{dias_llenos}")
    u = crear(f"u{dias_llenos}@t.es")
    for d in range(1, dias_llenos + 1):
        establecer_estado_dia(u, date(2026, 7, d), "libre")
    vacios = dias_sin_cumplimentar(u, 2026, 7)
    assert len(vacios) == esperado_vacios


def test_dias_sin_cumplimentar_cuenta_turnos_y_estados(db):
    _, _, franja_m, _, crear = _setup(db, "mixto")
    u = crear("mixto@t.es")
    añadir_turno(u, date(2026, 7, 1), franja_m.id)
    establecer_estado_dia(u, date(2026, 7, 2), "vacaciones")
    vacios = dias_sin_cumplimentar(u, 2026, 7)
    assert date(2026, 7, 1) not in vacios
    assert date(2026, 7, 2) not in vacios
    assert date(2026, 7, 3) in vacios


# ── calcular_y_guardar_compatibilidad ─────────────────────────────────────────

def _fecha_futura(days=30):
    return date.today() + timedelta(days=days)


@pytest.mark.parametrize("con_turno_companero,tipo_esperado", [
    (False, "libre"),
    (True, "compatible"),
], ids=["companero_libre", "companero_compatible"])
def test_guardar_compatibilidad_segun_disponibilidad_companero(db, con_turno_companero, tipo_esperado):
    _, _, franja_m, franja_t, crear = _setup(db, tipo_esperado)
    solicitante = crear(f"sol_{tipo_esperado}@t.es")
    companero   = crear(f"comp_{tipo_esperado}@t.es")

    fecha = _fecha_futura()
    publicar_mes(companero, fecha.year, fecha.month)
    publicar_mes(solicitante, fecha.year, fecha.month)
    if con_turno_companero:
        añadir_turno(companero, fecha, franja_t.id)  # turno tarde, no solapa con mañana

    pub = publicar_cambio(
        solicitante.id,
        [(fecha, franja_m.id)],
        [(fecha, franja_t.id)],
    )
    calcular_y_guardar_compatibilidad(pub)

    entries = CompatibilidadPlanilla.query.filter_by(publicacion_id=pub.id).all()
    assert len(entries) == 1
    assert entries[0].tipo == tipo_esperado
    if not con_turno_companero:
        assert entries[0].usuario_id == companero.id


def test_guardar_compatibilidad_sin_compañeros(db):
    _, _, franja_m, franja_t, crear = _setup(db, "solos")
    solicitante = crear("sol_solos@t.es")

    fecha = _fecha_futura()
    pub = publicar_cambio(
        solicitante.id,
        [(fecha, franja_m.id)],
        [(fecha, franja_t.id)],
    )
    calcular_y_guardar_compatibilidad(pub)

    assert CompatibilidadPlanilla.query.filter_by(publicacion_id=pub.id).count() == 0


def test_guardar_compatibilidad_idempotente(db):
    """Llamar dos veces reemplaza los datos, no los duplica."""
    _, _, franja_m, franja_t, crear = _setup(db, "idem")
    solicitante = crear("sol_idem@t.es")
    companero   = crear("comp_idem@t.es")

    fecha = _fecha_futura()
    publicar_mes(companero, fecha.year, fecha.month)

    pub = publicar_cambio(
        solicitante.id,
        [(fecha, franja_m.id)],
        [(fecha, franja_t.id)],
    )
    calcular_y_guardar_compatibilidad(pub)
    calcular_y_guardar_compatibilidad(pub)  # segunda llamada

    assert CompatibilidadPlanilla.query.filter_by(publicacion_id=pub.id).count() == 1


# ── actualizar_compat_tras_publicar_planilla ──────────────────────────────────

def test_publicar_planilla_dispara_recalculo(db):
    """Cuando Bruno publica su planilla, las publicaciones de Ana que piden esos días
    aparecen ahora con Bruno como compatible."""
    _, _, franja_m, franja_t, crear = _setup(db, "trigger")
    ana  = crear("ana_trigger@t.es")
    bruno = crear("bruno_trigger@t.es")

    fecha = _fecha_futura()

    # Ana publica un cambio (antes de que Bruno tenga planilla: sin compatibles)
    pub = publicar_cambio(ana.id, [(fecha, franja_m.id)], [(fecha, franja_t.id)])
    calcular_y_guardar_compatibilidad(pub)
    assert CompatibilidadPlanilla.query.filter_by(publicacion_id=pub.id).count() == 0

    # Bruno publica su planilla del mes
    publicar_mes(bruno, fecha.year, fecha.month)
    actualizar_compat_tras_publicar_planilla(ana, fecha.year, fecha.month)

    # Ahora la publicación de Ana debe tener a Bruno como libre
    entries = CompatibilidadPlanilla.query.filter_by(publicacion_id=pub.id).all()
    assert len(entries) == 1
    assert entries[0].usuario_id == bruno.id
