"""Tests para el generador de rota (planillas jul-sep) de scripts/seed_staging.py.

Verifica las tres reglas de negocio pedidas para la rota de UCO·La Paz·Enfermería:
- cobertura diaria: cada día, al menos un trabajador en cada una de las 5 franjas.
- descanso obligatorio el día siguiente a un turno de Noche o Nocturno 12h.
- cada trabajador tiene dos días libres por semana (semanas ISO completas dentro
  del rango; las semanas parciales de los bordes no son exigibles).
"""
from datetime import date, timedelta
from collections import defaultdict

import pytest

from app.models import (
    Categoria, EstadoDiaPlanilla, FranjaHoraria, SalienteDia, TurnoPlanilla,
    Unidad, Usuario, insertar_categorias_semilla,
)
from app.services.registro import (
    encontrar_o_crear_ciudad, encontrar_o_crear_hospital, encontrar_o_crear_pais,
    encontrar_o_crear_provincia, encontrar_o_crear_unidad,
)
from scripts.seed_staging import generar_rota

FECHA_INICIO = date(2026, 7, 1)
FECHA_FIN = date(2026, 9, 30)
FRANJAS_NOMBRES = ("Mañana", "Tarde", "Noche", "Diurno 12h", "Nocturno 12h")
FRANJAS_NOCTURNAS = ("Noche", "Nocturno 12h")


@pytest.fixture
def unidad_y_franjas(db):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    pais = encontrar_o_crear_pais("País Test")
    provincia = encontrar_o_crear_provincia("Provincia Test", pais)
    ciudad = encontrar_o_crear_ciudad("Ciudad Test", provincia)
    hospital = encontrar_o_crear_hospital("Hospital Test", ciudad)
    unidad, _ = encontrar_o_crear_unidad("Unidad Test", hospital, cat)
    db.session.flush()
    franjas = {
        "man": FranjaHoraria.query.filter_by(grupo_intercambio_id=unidad.grupo_intercambio_id, nombre="Mañana").first(),
        "tar": FranjaHoraria.query.filter_by(grupo_intercambio_id=unidad.grupo_intercambio_id, nombre="Tarde").first(),
        "noch": FranjaHoraria.query.filter_by(grupo_intercambio_id=unidad.grupo_intercambio_id, nombre="Noche").first(),
        "d12": FranjaHoraria.query.filter_by(grupo_intercambio_id=unidad.grupo_intercambio_id, nombre="Diurno 12h").first(),
        "n12": FranjaHoraria.query.filter_by(grupo_intercambio_id=unidad.grupo_intercambio_id, nombre="Nocturno 12h").first(),
    }
    return unidad, cat, franjas


def _crear_usuarios(db, unidad, cat, n):
    usuarios = []
    for i in range(n):
        u = Usuario(nombre=f"Trabajador {i}", email=f"trabajador{i}@rota-test.es",
                    unidad=unidad, categoria=cat)
        u.set_password("x")
        db.session.add(u)
        usuarios.append(u)
    db.session.flush()
    return usuarios


def _semanas_completas(fecha_inicio, fecha_fin):
    """Devuelve la lista de lunes de cada semana ISO totalmente contenida en el rango."""
    lunes = fecha_inicio - timedelta(days=fecha_inicio.weekday())
    semanas = []
    while lunes + timedelta(days=6) <= fecha_fin:
        if lunes >= fecha_inicio:
            semanas.append(lunes)
        lunes += timedelta(days=7)
    return semanas


def test_genera_un_turno_o_estado_libre_por_dia_y_usuario(db, unidad_y_franjas):
    unidad, cat, franjas = unidad_y_franjas
    usuarios = _crear_usuarios(db, unidad, cat, 16)
    turnos, estados, salientes = generar_rota(usuarios, franjas, FECHA_INICIO, FECHA_FIN)
    n_dias = (FECHA_FIN - FECHA_INICIO).days + 1
    dias_cubiertos = defaultdict(set)
    for t in turnos:
        dias_cubiertos[t.usuario].add(t.fecha)
    for e in estados:
        dias_cubiertos[e.usuario].add(e.fecha)
    for u in usuarios:
        assert len(dias_cubiertos[u]) == n_dias, f"{u.nombre} no tiene los {n_dias} días cubiertos"


def test_cobertura_diaria_las_5_franjas(db, unidad_y_franjas):
    unidad, cat, franjas = unidad_y_franjas
    usuarios = _crear_usuarios(db, unidad, cat, 16)
    turnos, estados, salientes = generar_rota(usuarios, franjas, FECHA_INICIO, FECHA_FIN)

    franjas_por_dia = defaultdict(set)
    for t in turnos:
        franjas_por_dia[t.fecha].add(t.franja_horaria.nombre)

    dia = FECHA_INICIO
    while dia <= FECHA_FIN:
        for nombre_franja in FRANJAS_NOMBRES:
            assert nombre_franja in franjas_por_dia[dia], (
                f"{dia}: nadie trabaja {nombre_franja}"
            )
        dia += timedelta(days=1)


def test_descanso_obligatorio_tras_turno_nocturno(db, unidad_y_franjas):
    unidad, cat, franjas = unidad_y_franjas
    usuarios = _crear_usuarios(db, unidad, cat, 16)
    turnos, estados, salientes = generar_rota(usuarios, franjas, FECHA_INICIO, FECHA_FIN)

    turnos_por_usuario = defaultdict(dict)
    for t in turnos:
        turnos_por_usuario[t.usuario][t.fecha] = t.franja_horaria.nombre
    estados_por_usuario = defaultdict(dict)
    for e in estados:
        estados_por_usuario[e.usuario][e.fecha] = e.tipo

    for u in usuarios:
        for fecha, nombre_franja in turnos_por_usuario[u].items():
            if nombre_franja in FRANJAS_NOCTURNAS:
                dia_siguiente = fecha + timedelta(days=1)
                if dia_siguiente > FECHA_FIN:
                    continue
                assert dia_siguiente not in turnos_por_usuario[u], (
                    f"{u.nombre} trabaja el día siguiente a un turno nocturno ({fecha})"
                )
                assert estados_por_usuario[u].get(dia_siguiente) == "libre", (
                    f"{u.nombre} no tiene libre el día siguiente a un turno nocturno ({fecha})"
                )


def test_dos_dias_libres_por_semana(db, unidad_y_franjas):
    unidad, cat, franjas = unidad_y_franjas
    usuarios = _crear_usuarios(db, unidad, cat, 16)
    turnos, estados, salientes = generar_rota(usuarios, franjas, FECHA_INICIO, FECHA_FIN)

    estados_por_usuario = defaultdict(dict)
    for e in estados:
        estados_por_usuario[e.usuario][e.fecha] = e.tipo

    semanas = _semanas_completas(FECHA_INICIO, FECHA_FIN)
    assert len(semanas) >= 10, "sanity check: deberían caber al menos 10 semanas completas en jul-sep"

    for u in usuarios:
        for lunes in semanas:
            libres_semana = sum(
                1 for i in range(7)
                if estados_por_usuario[u].get(lunes + timedelta(days=i)) == "libre"
            )
            assert libres_semana == 2, (
                f"{u.nombre} tiene {libres_semana} días libres en la semana del {lunes}"
            )


def test_saliente_marcado_el_dia_de_descanso_tras_noche(db, unidad_y_franjas):
    """SalienteDia (concepto ya existente en el dominio) se marca en el día de
    descanso forzoso tras una Noche/Nocturno 12h, para que el motor de
    matching lo trate igual que a un saliente real."""
    unidad, cat, franjas = unidad_y_franjas
    usuarios = _crear_usuarios(db, unidad, cat, 16)
    turnos, estados, salientes = generar_rota(usuarios, franjas, FECHA_INICIO, FECHA_FIN)
    assert len(salientes) > 0

    turnos_por_usuario = defaultdict(dict)
    for t in turnos:
        turnos_por_usuario[t.usuario][t.fecha] = t.franja_horaria.nombre
    salientes_por_usuario = defaultdict(set)
    for s in salientes:
        salientes_por_usuario[s.usuario].add(s.fecha)

    for u in usuarios:
        for fecha, nombre_franja in turnos_por_usuario[u].items():
            if nombre_franja in FRANJAS_NOCTURNAS:
                dia_siguiente = fecha + timedelta(days=1)
                if dia_siguiente > FECHA_FIN:
                    continue
                assert dia_siguiente in salientes_por_usuario[u]


def test_39_usuarios_tambien_cumple_cobertura(db, unidad_y_franjas):
    """El número real de trabajadores de UCO·La Paz·Enfermería (16 reales + 23
    sintéticos = 39) también debe cumplir cobertura diaria completa."""
    unidad, cat, franjas = unidad_y_franjas
    usuarios = _crear_usuarios(db, unidad, cat, 39)
    turnos, estados, salientes = generar_rota(usuarios, franjas, FECHA_INICIO, FECHA_FIN)

    franjas_por_dia = defaultdict(set)
    for t in turnos:
        franjas_por_dia[t.fecha].add(t.franja_horaria.nombre)
    dia = FECHA_INICIO
    while dia <= FECHA_FIN:
        for nombre_franja in FRANJAS_NOMBRES:
            assert nombre_franja in franjas_por_dia[dia]
        dia += timedelta(days=1)
