"""Script de un solo uso: genera un fixture anonimizado a partir de planilla_ilog.xls.
No se versiona el resultado con datos reales; solo el fixture de salida.
"""
import itertools
import random
import re

ORIGEN = "planilla_ilog.xls"
DESTINO = "tests/fixtures/planilla_ejemplo.xls"

# Nombres reales de la seed local de staging (scripts/seed_staging.py), excluyendo
# cuentas de rol (admin/supervisora) que no representan personal de planilla.
NOMBRES_STAGING = [
    "Claudia Pérez", "Juan Rodríguez", "Ana García", "Bruno López", "Carlos Ruiz",
    "Diana Martín", "Elena Sanz", "Fran Molina", "Gloria Pardo", "Héctor Vega",
    "Irene Blanco", "Javier Mora", "Ana Demo", "Carlos Demo", "Elena Demo",
    "María García", "Javier López", "Sofía Ruiz", "Pedro Martín", "Laura Fernández",
    "Marta Sánchez", "Diego Torres", "Lucía Romero", "Alejandro Díaz", "Carmen Molina",
    "Raúl Ortega", "Isabel Navarro", "Daniel Castro", "Paula Iglesias", "Sergio Vega",
    "Cristina Herrera", "Miguel Ramos", "Beatriz Gil", "Alberto Serrano", "Nuria Campos",
]

NOMBRES_PILA_EXTRA = [
    "Lorena", "Rubén", "Marina", "Óscar", "Silvia", "Iván", "Rocío", "Adrián",
    "Patricia", "Fernando", "Noelia", "Álvaro", "Sara", "Pablo", "Eva", "Víctor",
    "Yolanda", "Ignacio", "Vanesa", "Rodrigo", "Alicia", "Marcos", "Teresa", "Gonzalo",
    "Susana", "Emilio", "Natalia", "Andrés", "Rebeca", "Jorge", "Verónica", "Aitor",
    "Mónica", "Xavier", "Inés", "Tomás", "Julia", "Ricardo", "Celia", "Mateo",
    "Olga", "Enrique", "Amparo", "Nicolás", "Rosa", "Federico", "Elisa", "Rafael",
    "Marisol", "Guillermo",
]
APELLIDOS_EXTRA = [
    "Delgado", "Cano", "Cabrera", "Bravo", "Reyes", "Suárez", "Peña", "Cortés",
    "Prieto", "Nieto", "Carmona", "Vidal", "Soto", "Lozano", "Rubio", "Márquez",
    "Cuesta", "Domínguez", "Aguilar", "Salazar", "Guerrero", "Montero", "Ibáñez",
    "Pastor", "Crespo", "Vázquez", "Benítez", "Escobar", "Cid", "Solís", "Trujillo",
    "Anguita", "Pizarro", "Ochoa", "Zamora", "Riera", "Camacho", "Sáez", "Bermejo",
    "Osuna", "Falcón", "Robledo", "Andrade", "Montes", "Casares", "Espejo", "Quirós",
    "Villalba", "Cepeda", "Serra",
]


def a_formato_planilla(nombre_completo: str) -> str:
    partes = nombre_completo.split()
    pila, apellidos = partes[0], " ".join(partes[1:])
    return f"{apellidos.upper()}, {pila.upper()}"


def generar_pool(n: int) -> list[str]:
    pool = [a_formato_planilla(n) for n in NOMBRES_STAGING]
    vistos = set(pool)
    faltan = n - len(pool)
    combinaciones = list(itertools.product(
        NOMBRES_PILA_EXTRA, APELLIDOS_EXTRA, APELLIDOS_EXTRA
    ))
    random.shuffle(combinaciones)
    for pila, apellido1, apellido2 in combinaciones:
        if len(pool) >= n:
            break
        if apellido1 == apellido2:
            continue
        candidato = f"{apellido1.upper()} {apellido2.upper()}, {pila.upper()}"
        if candidato not in vistos:
            vistos.add(candidato)
            pool.append(candidato)
    assert len(pool) >= n, "pool de nombres inventados insuficiente"
    random.shuffle(pool)
    return pool


def generar_numeros(n: int) -> list[str]:
    return [str(x) for x in random.sample(range(10000, 100000), n)]


def main():
    random.seed(42)  # reproducible entre ejecuciones

    with open(ORIGEN, encoding="latin-1", newline="") as f:
        lineas = f.readlines()

    # Localiza filas de trabajador: celda de nombre "APELLIDOS, NOMBRE" seguida
    # de celda de número de empleado (5 dígitos).
    patron_num = re.compile(r"^\d{5}$")
    filas_trabajador = []  # (indice_linea, indice_celda_nombre, indice_celda_numero)
    for idx, linea in enumerate(lineas):
        celdas = linea.rstrip("\r\n").split("\t")
        for i, celda in enumerate(celdas):
            if i > 0 and patron_num.match(celda.strip()) and "," in celdas[i - 1]:
                filas_trabajador.append((idx, i - 1, i))
                break

    n = len(filas_trabajador)
    nombres_nuevos = generar_pool(n)
    numeros_nuevos = generar_numeros(n)

    for (idx, i_nombre, i_num), nombre_nuevo, numero_nuevo in zip(
        filas_trabajador, nombres_nuevos, numeros_nuevos
    ):
        celdas = lineas[idx].rstrip("\r\n").split("\t")
        celdas[i_nombre] = nombre_nuevo
        celdas[i_num] = numero_nuevo
        lineas[idx] = "\t".join(celdas) + "\r\n"

    with open(DESTINO, "w", encoding="latin-1", newline="") as f:
        f.writelines(lineas)

    print(f"{n} trabajadores anonimizados -> {DESTINO}")
    print(f"Nombres de staging reutilizados: {len(NOMBRES_STAGING)} / {n}")


if __name__ == "__main__":
    main()
