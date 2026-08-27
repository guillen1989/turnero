import importlib.util
import pathlib

import pytest

RUTA_SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "anadir_fecha_mensaje.py"
_spec = importlib.util.spec_from_file_location("anadir_fecha_mensaje", RUTA_SCRIPT)
anadir_fecha_mensaje = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(anadir_fecha_mensaje)

fusionar_fecha_mensaje = anadir_fecha_mensaje.fusionar_fecha_mensaje


def test_anade_fecha_mensaje_por_id_sin_tocar_otros_campos():
    mensajes = [
        {"id": "w001", "texto": "otro mensaje", "fecha_mensaje": "2026-08-26"},
        {"id": "w002", "texto": "texto anonimizado", "fecha_mensaje": "2026-08-27"},
    ]
    entradas = [
        {
            "id": "w002",
            "texto": "texto ya anotado a mano",
            "esperado": {"tipo": "cambio", "cedidos": [["2026-09-11", "Tarde"]], "aceptados": []},
        }
    ]
    resultado = fusionar_fecha_mensaje(mensajes, entradas)
    assert resultado == [
        {
            "id": "w002",
            "texto": "texto ya anotado a mano",
            "fecha_mensaje": "2026-08-27",
            "esperado": {"tipo": "cambio", "cedidos": [["2026-09-11", "Tarde"]], "aceptados": []},
        }
    ]


def test_no_toca_el_esperado_null():
    mensajes = [{"id": "w001", "texto": "x", "fecha_mensaje": "2026-08-26"}]
    entradas = [{"id": "w001", "texto": "x", "esperado": None}]
    resultado = fusionar_fecha_mensaje(mensajes, entradas)
    assert resultado[0]["esperado"] is None
    assert resultado[0]["fecha_mensaje"] == "2026-08-26"


def test_lanza_error_si_no_encuentra_el_id():
    mensajes = [{"id": "w001", "texto": "x", "fecha_mensaje": "2026-08-26"}]
    entradas = [{"id": "w999", "texto": "y", "esperado": None}]
    with pytest.raises(ValueError, match="w999"):
        fusionar_fecha_mensaje(mensajes, entradas)
