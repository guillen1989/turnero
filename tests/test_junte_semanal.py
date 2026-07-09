"""Tests del servicio puro de distribución semanal de un junte de noches:
qué días de la semana se trabajarían/librarían tras el junte, y a qué lunes
pertenece. Compartido entre el resumen de /cambios y /dashboard (main.py) y
el calendario visual (modo 'juntes')."""
from datetime import date, timedelta

from app.services.junte_semanal import (
    DIAS_CORTOS,
    calcular_distribucion,
    lista_es,
    resumen_textual,
)


class _TurnoFake:
    def __init__(self, fecha):
        self.fecha = fecha


class _PubFake:
    def __init__(self, cedidos, aceptados):
        self.turnos_cedidos = [_TurnoFake(f) for f in cedidos]
        self.turnos_aceptados = [_TurnoFake(f) for f in aceptados]


# --- calcular_distribucion ---

def test_calcula_lunes_semana_trabaja_y_libra_cadencia_lmvd():
    lunes = date(2026, 8, 3)  # lunes
    # LMVD: cede viernes(+4) y domingo(+6); recibe martes(+1) y jueves(+3)
    pub = _PubFake(
        cedidos=[lunes + timedelta(days=4), lunes + timedelta(days=6)],
        aceptados=[lunes + timedelta(days=1), lunes + timedelta(days=3)],
    )
    lunes_semana, trabaja, libra, num_noches = calcular_distribucion(pub)

    assert lunes_semana == lunes
    # trabaja: lunes(0) y miércoles(2) que conserva de LMVD + martes(1) y jueves(3) que recibe
    assert trabaja == frozenset([0, 1, 2, 3])
    # libra: viernes(4) y domingo(6) cedidos + sábado(5) (MJS no recibido)
    assert libra == frozenset([4, 5, 6])
    assert num_noches == 4


def test_calcula_distribucion_cadencia_mjs():
    lunes = date(2026, 8, 3)
    # MJS: cede martes(+1) y sábado(+5); recibe lunes(+0) y viernes(+4)
    pub = _PubFake(
        cedidos=[lunes + timedelta(days=1), lunes + timedelta(days=5)],
        aceptados=[lunes + timedelta(days=0), lunes + timedelta(days=4)],
    )
    lunes_semana, trabaja, libra, num_noches = calcular_distribucion(pub)

    assert lunes_semana == lunes
    assert trabaja == frozenset([0, 3, 4])
    assert libra == frozenset([1, 2, 5, 6])
    assert num_noches == 3


def test_lunes_semana_es_independiente_de_que_fecha_se_use_para_calcularlo():
    """El lunes de la semana debe ser el mismo tanto si se calcula a partir de
    un turno cedido como de uno aceptado (todas las fechas del junte caen en
    la misma semana natural)."""
    lunes = date(2026, 8, 3)
    pub = _PubFake(
        cedidos=[lunes + timedelta(days=6)],  # domingo, el más tardío
        aceptados=[lunes + timedelta(days=1)],  # martes, el más temprano
    )
    lunes_semana, _, _, _ = calcular_distribucion(pub)
    assert lunes_semana == lunes


def test_sin_turnos_devuelve_lunes_none():
    pub = _PubFake(cedidos=[], aceptados=[])
    lunes_semana, trabaja, libra, num_noches = calcular_distribucion(pub)
    assert lunes_semana is None


# --- lista_es ---

def test_lista_es_un_elemento():
    assert lista_es(["lunes"]) == "lunes"


def test_lista_es_varios_elementos():
    assert lista_es(["lunes", "martes", "miércoles"]) == "lunes, martes y miércoles"


def test_lista_es_vacio():
    assert lista_es([]) == ""


# --- resumen_textual ---

def test_resumen_textual_formatea_dias_en_espanol():
    trabaja_str, libra_str = resumen_textual(frozenset([0, 1]), frozenset([4, 5, 6]))
    assert trabaja_str == "lunes y martes"
    assert libra_str == "viernes, sábado y domingo"


# --- DIAS_CORTOS ---

def test_dias_cortos_orden_lunes_a_domingo():
    assert DIAS_CORTOS == ("L", "M", "X", "J", "V", "S", "D")
