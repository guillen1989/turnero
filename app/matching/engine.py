"""
Motor de matching puro: sin dependencias de Flask ni SQLAlchemy.

Los turnos se representan como conjuntos de tuplas (fecha, franja_horaria_id).
Esto permite extender el algoritmo a cadenas de N bandas en el futuro
sin modificar esta capa.
"""


def detectar_match_regalo(aceptados_regalo, cedidos_peticion):
    """
    Devuelve True si una publicación 'regalo' cubre una 'peticion'.

    Condición: al menos un turno que el regalo ofrece trabajar coincide
    con algún turno que la petición quiere librar.

    aceptados_regalo / cedidos_peticion: iterables de (fecha: date, franja_horaria_id: int).
    """
    return bool(frozenset(aceptados_regalo) & frozenset(cedidos_peticion))


def detectar_match_directo(cedidos_a, aceptados_a, cedidos_b, aceptados_b):
    """
    Devuelve True si las publicaciones A y B forman un match directo.

    Condición (especificación, regla 2):
      - Al menos un turno cedido por A está en los aceptados por B, Y
      - Al menos un turno cedido por B está en los aceptados por A.

    cedidos_* / aceptados_*: iterables de (fecha: date, franja_horaria_id: int).
    """
    cedidos_a = frozenset(cedidos_a)
    aceptados_a = frozenset(aceptados_a)
    cedidos_b = frozenset(cedidos_b)
    aceptados_b = frozenset(aceptados_b)

    return bool(cedidos_a & aceptados_b) and bool(cedidos_b & aceptados_a)
