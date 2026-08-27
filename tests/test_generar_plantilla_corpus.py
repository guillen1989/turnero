import importlib.util
import pathlib

RUTA_SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "generar_plantilla_corpus.py"
_spec = importlib.util.spec_from_file_location("generar_plantilla_corpus", RUTA_SCRIPT)
generar_plantilla_corpus = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generar_plantilla_corpus)

extraer_mensajes = generar_plantilla_corpus.extraer_mensajes


def test_extrae_un_mensaje_de_una_sola_linea():
    lineas = ["[26/8, 11:26] [NOMBRE1]: Alguien me puede hacer la T del 18\n"]
    mensajes = extraer_mensajes(lineas)
    assert mensajes == [{"id": "w001", "texto": "Alguien me puede hacer la T del 18"}]


def test_asigna_ids_correlativos_con_padding():
    lineas = [
        "[26/8, 11:26] [NOMBRE1]: mensaje uno\n",
        "[26/8, 11:27] [NOMBRE2]: mensaje dos\n",
    ]
    mensajes = extraer_mensajes(lineas)
    assert [m["id"] for m in mensajes] == ["w001", "w002"]


def test_agrupa_lineas_de_continuacion_en_el_mismo_mensaje():
    lineas = [
        "[26/8, 11:26] [NOMBRE1]: Ofrezco\n",
        "Tardes: 15,17,20\n",
        "Mañana: 19,20\n",
        "[26/8, 11:27] [NOMBRE2]: otro mensaje\n",
    ]
    mensajes = extraer_mensajes(lineas)
    assert mensajes == [
        {"id": "w001", "texto": "Ofrezco\nTardes: 15,17,20\nMañana: 19,20"},
        {"id": "w002", "texto": "otro mensaje"},
    ]


def test_ignora_mensajes_vacios():
    lineas = [
        "[26/8, 11:26] [NOMBRE1]: \n",
        "[26/8, 11:27] [NOMBRE2]: mensaje real\n",
    ]
    mensajes = extraer_mensajes(lineas)
    assert mensajes == [{"id": "w001", "texto": "mensaje real"}]
