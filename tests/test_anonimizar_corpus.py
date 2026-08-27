import importlib.util
import pathlib

RUTA_SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "anonimizar_corpus.py"
_spec = importlib.util.spec_from_file_location("anonimizar_corpus", RUTA_SCRIPT)
anonimizar_corpus = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(anonimizar_corpus)

anonimizar_lineas = anonimizar_corpus.anonimizar_lineas


def test_anonimiza_formato_corchetes_sin_ano():
    lineas = ["[26/8, 11:26] Daniela Ordoñez DUE GUSS: Alguien me puede hacer la T del 18\n"]
    salida = anonimizar_lineas(lineas)
    assert salida == ["[26/8, 11:26] [NOMBRE1]: Alguien me puede hacer la T del 18\n"]


def test_mismo_remitente_recibe_mismo_pseudonimo():
    lineas = [
        "[26/8, 11:26] Daniela Ordoñez DUE GUSS: mensaje uno\n",
        "[26/8, 12:00] Daniela Ordoñez DUE GUSS: mensaje dos\n",
    ]
    salida = anonimizar_lineas(lineas)
    assert "[NOMBRE1]" in salida[0]
    assert "[NOMBRE1]" in salida[1]


def test_remitentes_distintos_reciben_pseudonimos_distintos():
    lineas = [
        "[26/8, 11:26] Daniela Ordoñez DUE GUSS: mensaje uno\n",
        "[26/8, 12:00] Marin DUE GUSS: mensaje dos\n",
    ]
    salida = anonimizar_lineas(lineas)
    assert "[NOMBRE1]" in salida[0]
    assert "[NOMBRE2]" in salida[1]


def test_anonimiza_mensaje_reenviado_con_envoltura_anidada():
    linea = "[27/8/26 9:30] Guillén Del Barrio Blanco: [26/8, 10:58] Eva Bermejo DUE GUSS: Xfiii alguien me puede hacer la tarde\n"
    salida = anonimizar_lineas([linea])
    assert salida == [
        "[27/8/26 9:30] [NOMBRE1]: [26/8, 10:58] [NOMBRE2]: Xfiii alguien me puede hacer la tarde\n"
    ]


def test_enmascara_telefono_en_remitente() -> None:
    linea = "[26/8, 14:25] +34 638 44 56 31: Hago la M o T del 25 de septiembre\n"
    salida = anonimizar_lineas([linea])
    assert salida == ["[26/8, 14:25] [TELEFONO]: Hago la M o T del 25 de septiembre\n"]


def test_linea_de_continuacion_sin_cabecera_no_se_toca():
    lineas = [
        "[26/8, 13:35] Teresa Martínez DUE GUSS: Necesito librar la T12 de septiembre.\n",
        "Puedo hacer M1, M3 y M5 de septiembre.\n",
    ]
    salida = anonimizar_lineas(lineas)
    assert salida[1] == "Puedo hacer M1, M3 y M5 de septiembre.\n"


def test_enmascara_telefono_en_linea_de_continuacion():
    salida = anonimizar_lineas(["Llámame al 638 44 56 31 porfa\n"])
    assert salida == ["Llámame al [TELEFONO] porfa\n"]
