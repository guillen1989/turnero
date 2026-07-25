from datetime import date

from app.services.planilla_import import parsear_planilla_ilog

RUTA_FIXTURE = "tests/fixtures/planilla_ejemplo.xls"


def _leer_fixture():
    with open(RUTA_FIXTURE, encoding="latin-1") as f:
        return f.read()

def test_extrae_metadata_del_periodo():
    resultado = parsear_planilla_ilog(_leer_fixture())
    assert resultado.anyo == 2021
    assert resultado.mes == 12
    assert resultado.unidad_nombre == "GUSS DUE"

def test_extrae_todos_los_trabajadores_sin_duplicados():
    resultado = parsear_planilla_ilog(_leer_fixture())
    assert len(resultado.trabajadores) == 136

    nombres = [t.nombre_planilla for t in resultado.trabajadores]
    numeros = [t.numero_empleado for t in resultado.trabajadores]
    assert len(set(nombres)) == 136
    assert len(set(numeros)) == 136

    for t in resultado.trabajadores:
        assert "," in t.nombre_planilla
        assert t.numero_empleado.isdigit()
        assert len(t.numero_empleado) == 5

def test_turnos_del_primer_trabajador_coinciden_con_el_fixture():
    contenido = _leer_fixture()
    lineas = contenido.splitlines()
    primera_fila = lineas[13].split("\t")
    nombre_esperado = primera_fila[1]
    numero_esperado = primera_fila[2]
    turnos_esperados = {
        dia: codigo
        for dia, codigo in zip(range(1, 32), primera_fila[3:34])
        if codigo.strip()
    }

    resultado = parsear_planilla_ilog(contenido)
    trabajador = resultado.trabajadores[0]

    assert trabajador.nombre_planilla == nombre_esperado
    assert trabajador.numero_empleado == numero_esperado
    assert trabajador.turnos == {
        date(2021, 12, dia): codigo for dia, codigo in turnos_esperados.items()
    }

def test_todos_los_codigos_de_turno_son_conocidos():
    resultado = parsear_planilla_ilog(_leer_fixture())
    codigos = {
        codigo
        for t in resultado.trabajadores
        for codigo in t.turnos.values()
    }
    assert codigos <= {"M", "T", "N", "MC", "TC", "D1"}

def test_ignora_filas_sin_numero_de_empleado_valido():
    contenido = (
        "Informe\n"
        "\tFecha inicial:\t01/01/2024\t\n"
        "\tFecha final:\t31/01/2024\t\n"
        "\tUnidad:\tPRUEBA\n"
        "\tDias\t\t1\t2\n"
        "\t\n"
        "\tALGUIEN SIN NUMERO\t\tM\tT\n"
        "\t\n"
        "\tCON NUMERO, VALIDO\t11111\tM\t\n"
    )
    resultado = parsear_planilla_ilog(contenido)
    assert len(resultado.trabajadores) == 1
    assert resultado.trabajadores[0].nombre_planilla == "CON NUMERO, VALIDO"

def test_parsea_meses_de_distinta_longitud():
    contenido = (
        "Informe\n"
        "\tFecha inicial:\t01/02/2024\t\n"
        "\tFecha final:\t29/02/2024\t\n"
        "\tUnidad:\tPRUEBA\n"
        "\tDias\t\t1\t2\t3\n"
        "\t\n"
        "\tAPELLIDO, NOMBRE\t22222\tM\t\tN\n"
    )
    resultado = parsear_planilla_ilog(contenido)
    assert resultado.mes == 2
    assert resultado.trabajadores[0].turnos == {
        date(2024, 2, 1): "M",
        date(2024, 2, 3): "N",
    }
