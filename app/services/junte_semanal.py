"""Distribución semanal de una publicación tipo 'junte' (junte de noches):
qué días de la semana se trabajarían/librarían tras el intercambio, y a qué
lunes pertenece la semana del junte.

Módulo puro: solo lee los turnos ya cargados en la publicación, no hace
consultas propias. Compartido entre el resumen de /cambios y /dashboard
(app/routes/main.py) y el calendario visual, modo 'juntes'
(app/services/calendario_mercado.py).
"""
from datetime import timedelta

DIAS_ES = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
DIAS_CORTOS = ("L", "M", "X", "J", "V", "S", "D")

_LMVD = frozenset([0, 2, 4, 6])
_MJS = frozenset([1, 3, 5])


def lista_es(items):
    """Une una lista de textos al estilo español: 'a, b y c'."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " y " + items[-1]


def calcular_distribucion(pub):
    """Para una publicación tipo 'junte', devuelve (lunes_semana, trabaja, libra,
    num_noches):

    - lunes_semana: el lunes de la semana natural del junte (date), o None si
      la publicación no tiene turnos.
    - trabaja/libra: frozenset de weekday (0=lunes..6=domingo) que la persona
      trabajaría/libraría tras el junte. Cualquier fecha del junte (cedida o
      aceptada) cae en la misma semana natural, así que da igual cuál se use
      para hallar el lunes.
    - num_noches: tamaño de la cadencia original (LMVD=4 o MJS=3) que sigue
      la persona antes del junte. No siempre coincide con len(trabaja) — en
      un junte parcial (se cede/recibe menos noches que toda la cadencia)
      trabaja/libra pueden tener otro tamaño.
    """
    cedidos_wd = frozenset(tc.fecha.weekday() for tc in pub.turnos_cedidos)
    aceptados_wd = frozenset(ta.fecha.weekday() for ta in pub.turnos_aceptados)

    cadencia = _LMVD if (cedidos_wd & _LMVD) else _MJS
    partner = frozenset(range(7)) - cadencia

    trabaja = (cadencia - cedidos_wd) | aceptados_wd
    libra = cedidos_wd | (partner - aceptados_wd)

    fechas = [tc.fecha for tc in pub.turnos_cedidos] + [ta.fecha for ta in pub.turnos_aceptados]
    if not fechas:
        return None, trabaja, libra, len(cadencia)

    referencia = min(fechas)
    lunes_semana = referencia - timedelta(days=referencia.weekday())
    return lunes_semana, trabaja, libra, len(cadencia)


def resumen_textual(trabaja, libra):
    """(trabaja_str, libra_str): los weekday de trabaja/libra como texto en
    español, ordenados de lunes a domingo."""
    trabaja_str = lista_es([DIAS_ES[d] for d in sorted(trabaja)])
    libra_str = lista_es([DIAS_ES[d] for d in sorted(libra)])
    return trabaja_str, libra_str
