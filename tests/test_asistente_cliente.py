from datetime import date
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app.services.asistente.cliente import ErrorAsistente, extraer_propuesta
from app.services.asistente.schema import PropuestaPublicacion

_CONTEXTO = {
    "franjas": [
        {"nombre": "Mañana", "hora_inicio": "08:00", "hora_fin": "15:00"},
        {"nombre": "Tarde", "hora_inicio": "15:00", "hora_fin": "22:00"},
    ],
    "tipos_validos": ["cambio", "regalo", "peticion", "junte", "cambio_dia"],
    "hoy": date(2026, 8, 27),
}


class _ClienteFalso:
    def __init__(self, respuesta=None, excepcion=None):
        self._respuesta = respuesta
        self._excepcion = excepcion
        self.kwargs_recibidos = None
        self.messages = SimpleNamespace(parse=self._parse)

    def _parse(self, **kwargs):
        self.kwargs_recibidos = kwargs
        if self._excepcion:
            raise self._excepcion
        return self._respuesta


def _propuesta_esperada():
    return PropuestaPublicacion(
        tipo="cambio",
        cedidos=[{"fecha": "2026-08-28", "franja": "Mañana"}],
        aceptados=[{"fecha": "2026-08-29", "franja": "Tarde"}],
    )


def test_extraer_propuesta_con_cliente_falso_devuelve_la_propuesta_parseada():
    propuesta = _propuesta_esperada()
    cliente = _ClienteFalso(respuesta=SimpleNamespace(parsed_output=propuesta))

    resultado = extraer_propuesta("cambio mi mañana del 28 por tu tarde del 29", _CONTEXTO, client=cliente)

    assert resultado is propuesta
    assert cliente.kwargs_recibidos["output_format"] is PropuestaPublicacion


def test_error_de_la_api_lanza_excepcion_controlada_del_dominio():
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    excepcion = anthropic.APIConnectionError(request=request)
    cliente = _ClienteFalso(excepcion=excepcion)

    with pytest.raises(ErrorAsistente):
        extraer_propuesta("texto cualquiera", _CONTEXTO, client=cliente)


def test_timeout_lanza_excepcion_controlada_del_dominio():
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    excepcion = anthropic.APITimeoutError(request=request)
    cliente = _ClienteFalso(excepcion=excepcion)

    with pytest.raises(ErrorAsistente):
        extraer_propuesta("texto cualquiera", _CONTEXTO, client=cliente)


def test_el_prompt_de_sistema_no_incluye_la_fecha_de_hoy():
    cliente = _ClienteFalso(respuesta=SimpleNamespace(parsed_output=_propuesta_esperada()))

    extraer_propuesta("texto", _CONTEXTO, client=cliente)

    bloque_sistema = cliente.kwargs_recibidos["system"][0]["text"]
    assert "2026" not in bloque_sistema
    assert bloque_sistema.count("Mañana") >= 1


def test_el_prompt_distingue_peticion_de_cambio_y_de_regalo():
    """Fase 5B — el fallo dominante del dev set (20/60) era confundir tipos que
    el prompt nunca definía, solo los nombraba. Sin esta distinción, el modelo
    no puede diferenciar 'me cambian X por Y' (cambio) de 'que me cubran X, ya
    veremos' (peticion, sin aceptados concretos)."""
    cliente = _ClienteFalso(respuesta=SimpleNamespace(parsed_output=_propuesta_esperada()))

    extraer_propuesta("texto", _CONTEXTO, client=cliente)

    bloque_sistema = cliente.kwargs_recibidos["system"][0]["text"]
    assert "aceptados" in bloque_sistema and "cedidos" in bloque_sistema
    assert "mismo día" in bloque_sistema



def test_el_mensaje_de_error_incluye_el_detalle_original_para_diagnostico():
    """El route solo loguea str(exc); si perdemos el detalle aquí, en producción
    no hay forma de saber si un fallo fue timeout, rate limit o auth sin
    reproducirlo a mano."""
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    excepcion = anthropic.APITimeoutError(request=request)
    cliente = _ClienteFalso(excepcion=excepcion)

    with pytest.raises(ErrorAsistente) as exc_info:
        extraer_propuesta("texto cualquiera", _CONTEXTO, client=cliente)

    assert "timed out" in str(exc_info.value).lower()
