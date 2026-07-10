"""Tests unitarios del motor de matching (Fase 4, paso 1).

El motor es una función pura: no toca la base de datos ni Flask.
Los turnos se representan como frozensets de (fecha, franja_horaria_id).
"""
from datetime import date

from app.matching.engine import detectar_match_directo, detectar_match_regalo

# --- UAT-3.1: match directo 1 a 1 ---

def test_match_directo_basico():
    """Ana cede mañana_25 y acepta tarde_26; Pedro cede tarde_26 y acepta mañana_25."""
    mañana_25 = (date(2026, 6, 25), 1)
    tarde_26 = (date(2026, 6, 26), 2)

    assert detectar_match_directo(
        cedidos_a={mañana_25},
        aceptados_a={tarde_26},
        cedidos_b={tarde_26},
        aceptados_b={mañana_25},
    )


# --- UAT-3.2: sin match si solo un sentido coincide ---

def test_no_match_si_solo_un_sentido_coincide():
    """Pedro acepta lo que Ana cede, pero Ana no acepta lo que Pedro cede."""
    mañana_25 = (date(2026, 6, 25), 1)
    tarde_26 = (date(2026, 6, 26), 2)
    noche_27 = (date(2026, 6, 27), 3)

    assert not detectar_match_directo(
        cedidos_a={mañana_25},
        aceptados_a={tarde_26},
        cedidos_b={noche_27},
        aceptados_b={mañana_25},
    )


def test_no_match_si_el_otro_sentido_tampoco_coincide():
    """Ninguna de las dos partes acepta lo que la otra cede."""
    mañana_25 = (date(2026, 6, 25), 1)
    tarde_26 = (date(2026, 6, 26), 2)
    noche_27 = (date(2026, 6, 27), 3)
    noche_28 = (date(2026, 6, 28), 3)

    assert not detectar_match_directo(
        cedidos_a={mañana_25},
        aceptados_a={tarde_26},
        cedidos_b={noche_27},
        aceptados_b={noche_28},
    )


# --- UAT-3.3: match con varias opciones por lado ---

def test_match_con_multiples_opciones_en_aceptados():
    """Ana acepta tarde_26 O noche_28; Pedro cede tarde_26 — basta con una coincidencia."""
    mañana_25 = (date(2026, 6, 25), 1)
    tarde_26 = (date(2026, 6, 26), 2)
    noche_28 = (date(2026, 6, 28), 3)

    assert detectar_match_directo(
        cedidos_a={mañana_25},
        aceptados_a={tarde_26, noche_28},
        cedidos_b={tarde_26},
        aceptados_b={mañana_25},
    )


def test_match_con_multiples_cedidos():
    """A cede dos turnos; el que B acepta es el segundo de los cedidos."""
    mañana_25 = (date(2026, 6, 25), 1)
    tarde_26 = (date(2026, 6, 26), 2)
    noche_27 = (date(2026, 6, 27), 3)

    assert detectar_match_directo(
        cedidos_a={mañana_25, tarde_26},
        aceptados_a={noche_27},
        cedidos_b={noche_27},
        aceptados_b={tarde_26},
    )


# --- Casos límite ---

def test_no_match_con_cedidos_vacios():
    """Sin turnos a ceder no puede haber match."""
    tarde_26 = (date(2026, 6, 26), 2)

    assert not detectar_match_directo(
        cedidos_a=set(),
        aceptados_a={tarde_26},
        cedidos_b={tarde_26},
        aceptados_b=set(),
    )


def test_no_match_con_todo_vacio():
    assert not detectar_match_directo(
        cedidos_a=set(),
        aceptados_a=set(),
        cedidos_b=set(),
        aceptados_b=set(),
    )


# --- Matching regalo ↔ petición ---

def test_match_regalo_detecta_cuando_aceptado_cubre_cedido():
    """Un regalo (ofrece tarde_26) hace match con una petición que quiere librar tarde_26."""
    tarde_26 = (date(2026, 6, 26), 2)
    assert detectar_match_regalo(
        aceptados_regalo={tarde_26},
        cedidos_peticion={tarde_26},
    )


def test_match_regalo_no_detecta_cuando_no_hay_interseccion():
    """Un regalo (ofrece tarde_26) no hace match con una petición que quiere librar mañana_25."""
    tarde_26 = (date(2026, 6, 26), 2)
    mañana_25 = (date(2026, 6, 25), 1)
    assert not detectar_match_regalo(
        aceptados_regalo={tarde_26},
        cedidos_peticion={mañana_25},
    )


def test_match_regalo_con_multiples_opciones():
    """Regalo con varios aceptados hace match si al menos uno coincide con el cedido."""
    mañana_25 = (date(2026, 6, 25), 1)
    tarde_26 = (date(2026, 6, 26), 2)
    noche_27 = (date(2026, 6, 27), 3)
    assert detectar_match_regalo(
        aceptados_regalo={mañana_25, tarde_26},
        cedidos_peticion={noche_27, tarde_26},
    )


def test_match_regalo_con_conjuntos_vacios():
    assert not detectar_match_regalo(aceptados_regalo=set(), cedidos_peticion={(date(2026, 6, 26), 2)})
    assert not detectar_match_regalo(aceptados_regalo={(date(2026, 6, 26), 2)}, cedidos_peticion=set())


def test_no_match_cuando_ambos_ceden_lo_mismo_pero_no_se_cruzan():
    """A y B ceden el mismo turno, pero ninguno acepta lo que el otro da."""
    mañana_25 = (date(2026, 6, 25), 1)
    tarde_26 = (date(2026, 6, 26), 2)
    noche_27 = (date(2026, 6, 27), 3)

    assert not detectar_match_directo(
        cedidos_a={mañana_25},
        aceptados_a={tarde_26},
        cedidos_b={mañana_25},
        aceptados_b={noche_27},
    )


# --- Matching a 3 bandas ---

from app.matching.engine import detectar_cadena_3


def test_cadena_3_ciclo_completo():
    """A cede X (B acepta X), B cede Y (C acepta Y), C cede Z (A acepta Z)."""
    X = (date(2026, 7, 1), 1)
    Y = (date(2026, 7, 2), 2)
    Z = (date(2026, 7, 3), 3)

    assert detectar_cadena_3(
        cedidos_a={X}, aceptados_a={Z},
        cedidos_b={Y}, aceptados_b={X},
        cedidos_c={Z}, aceptados_c={Y},
    )


def test_cadena_3_falla_si_ultimo_eslabon_roto():
    """El ciclo no se cierra porque C ofrece algo que A no acepta."""
    X = (date(2026, 7, 1), 1)
    Y = (date(2026, 7, 2), 2)
    Z = (date(2026, 7, 3), 3)
    W = (date(2026, 7, 4), 1)

    assert not detectar_cadena_3(
        cedidos_a={X}, aceptados_a={Z},
        cedidos_b={Y}, aceptados_b={X},
        cedidos_c={W}, aceptados_c={Y},  # C cede W, A acepta Z — ciclo roto
    )


def test_cadena_3_falla_si_primer_eslabon_roto():
    """A→B no se satisface porque B no acepta lo que A cede."""
    X = (date(2026, 7, 1), 1)
    Y = (date(2026, 7, 2), 2)
    Z = (date(2026, 7, 3), 3)
    W = (date(2026, 7, 4), 1)

    assert not detectar_cadena_3(
        cedidos_a={X}, aceptados_a={Z},
        cedidos_b={Y}, aceptados_b={W},  # B acepta W, no X
        cedidos_c={Z}, aceptados_c={Y},
    )


def test_cadena_3_match_directo_no_es_cadena():
    """Un match directo A↔B no constituye cadena de 3."""
    X = (date(2026, 7, 1), 1)
    Y = (date(2026, 7, 2), 2)

    assert not detectar_cadena_3(
        cedidos_a={X}, aceptados_a={Y},
        cedidos_b={Y}, aceptados_b={X},
        cedidos_c=set(), aceptados_c=set(),
    )


def test_cadena_3_con_multiples_turnos():
    """La cadena se detecta aunque haya más turnos por publicación."""
    X = (date(2026, 7, 1), 1)
    X2 = (date(2026, 7, 5), 1)
    Y = (date(2026, 7, 2), 2)
    Z = (date(2026, 7, 3), 3)

    assert detectar_cadena_3(
        cedidos_a={X, X2}, aceptados_a={Z},
        cedidos_b={Y}, aceptados_b={X},
        cedidos_c={Z}, aceptados_c={Y},
    )


# --- Matching a 4 bandas ---

from app.matching.engine import detectar_cadena_4


def test_cadena_4_ciclo_completo():
    """A cede W (B acepta), B cede X (C acepta), C cede Y (D acepta), D cede Z (A acepta)."""
    W = (date(2026, 7, 1), 1)
    X = (date(2026, 7, 2), 2)
    Y = (date(2026, 7, 3), 3)
    Z = (date(2026, 7, 4), 1)

    assert detectar_cadena_4(
        cedidos_a={W}, aceptados_a={Z},
        cedidos_b={X}, aceptados_b={W},
        cedidos_c={Y}, aceptados_c={X},
        cedidos_d={Z}, aceptados_d={Y},
    )


def test_cadena_4_falla_si_ultimo_eslabon_roto():
    """El ciclo no se cierra porque D ofrece algo que A no acepta."""
    W = (date(2026, 7, 1), 1)
    X = (date(2026, 7, 2), 2)
    Y = (date(2026, 7, 3), 3)
    Z = (date(2026, 7, 4), 1)
    V = (date(2026, 7, 5), 1)

    assert not detectar_cadena_4(
        cedidos_a={W}, aceptados_a={Z},
        cedidos_b={X}, aceptados_b={W},
        cedidos_c={Y}, aceptados_c={X},
        cedidos_d={V}, aceptados_d={Y},  # D cede V, A acepta Z — ciclo roto
    )


def test_cadena_4_falla_si_eslabon_intermedio_roto():
    """B→C no se satisface porque C no acepta lo que B cede."""
    W = (date(2026, 7, 1), 1)
    X = (date(2026, 7, 2), 2)
    Y = (date(2026, 7, 3), 3)
    Z = (date(2026, 7, 4), 1)
    V = (date(2026, 7, 5), 1)

    assert not detectar_cadena_4(
        cedidos_a={W}, aceptados_a={Z},
        cedidos_b={X}, aceptados_b={W},
        cedidos_c={Y}, aceptados_c={V},  # C acepta V, no X
        cedidos_d={Z}, aceptados_d={Y},
    )


def test_cadena_4_falla_si_primer_eslabon_roto():
    """A→B no se satisface porque B no acepta lo que A cede."""
    W = (date(2026, 7, 1), 1)
    X = (date(2026, 7, 2), 2)
    Y = (date(2026, 7, 3), 3)
    Z = (date(2026, 7, 4), 1)
    V = (date(2026, 7, 5), 1)

    assert not detectar_cadena_4(
        cedidos_a={W}, aceptados_a={Z},
        cedidos_b={X}, aceptados_b={V},  # B acepta V, no W
        cedidos_c={Y}, aceptados_c={X},
        cedidos_d={Z}, aceptados_d={Y},
    )


def test_cadena_4_no_confunde_cadena_3_con_cadena_4():
    """Un ciclo cerrado de 3 (C→A directo) no constituye cadena de 4."""
    W = (date(2026, 7, 1), 1)
    X = (date(2026, 7, 2), 2)
    Z = (date(2026, 7, 4), 1)

    assert not detectar_cadena_4(
        cedidos_a={W}, aceptados_a={Z},
        cedidos_b={X}, aceptados_b={W},
        cedidos_c={Z}, aceptados_c={X},  # C→A ya cierra un ciclo de 3
        cedidos_d=set(), aceptados_d=set(),
    )


def test_cadena_4_con_multiples_turnos():
    """La cadena se detecta aunque haya más turnos por publicación."""
    W = (date(2026, 7, 1), 1)
    W2 = (date(2026, 7, 6), 1)
    X = (date(2026, 7, 2), 2)
    Y = (date(2026, 7, 3), 3)
    Z = (date(2026, 7, 4), 1)

    assert detectar_cadena_4(
        cedidos_a={W, W2}, aceptados_a={Z},
        cedidos_b={X}, aceptados_b={W},
        cedidos_c={Y}, aceptados_c={X},
        cedidos_d={Z}, aceptados_d={Y},
    )
