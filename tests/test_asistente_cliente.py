import json
from datetime import date
from types import SimpleNamespace

import anthropic
import groq
import httpx
import pytest

from app.services.asistente.cliente import (
    ErrorAsistente,
    _extraer_propuesta_anthropic,
    extraer_propuesta,
)
from app.services.asistente.schema import PropuestaPublicacion

_CONTEXTO = {
    "franjas": [
        {"nombre": "Mañana", "hora_inicio": "08:00", "hora_fin": "15:00"},
        {"nombre": "Tarde", "hora_inicio": "15:00", "hora_fin": "22:00"},
    ],
    "tipos_validos": ["cambio", "regalo", "peticion", "junte", "cambio_dia"],
    "hoy": date(2026, 8, 27),
}


def _propuesta_esperada():
    return PropuestaPublicacion(
        tipo="cambio",
        cedidos=[{"fecha": "2026-08-28", "franja": "Mañana"}],
        aceptados=[{"fecha": "2026-08-29", "franja": "Tarde"}],
    )


def _propuesta_esperada_json():
    return _propuesta_esperada().model_dump_json()


class _ClienteGroqFalso:
    """Doble del cliente Groq: imita `client.chat.completions.create(**kwargs)`."""

    def __init__(self, contenido=None, excepcion=None):
        self._contenido = contenido
        self._excepcion = excepcion
        self.kwargs_recibidos = None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.kwargs_recibidos = kwargs
        if self._excepcion:
            raise self._excepcion
        mensaje = SimpleNamespace(content=self._contenido)
        return SimpleNamespace(choices=[SimpleNamespace(message=mensaje)])


class _ClienteAnthropicFalso:
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


# --- extraer_propuesta (motor activo: Groq / Llama 3.1 8B) ---
# Ver decisión 2026-08-28 en docs/crear_parser.md: se sustituye Claude Haiku
# por Groq (más barato y más rápido); la lógica de Anthropic se conserva
# desactivada más abajo, sin que nada la invoque.

def test_extraer_propuesta_con_cliente_falso_devuelve_la_propuesta_parseada():
    cliente = _ClienteGroqFalso(contenido=_propuesta_esperada_json())

    resultado = extraer_propuesta("cambio mi mañana del 28 por tu tarde del 29", _CONTEXTO, client=cliente)

    assert resultado == _propuesta_esperada()


def test_usa_el_modelo_gpt_oss_120b_via_groq():
    """llama-3.1-8b-instant y llama-3.3-70b-versatile devolvían 404
    model_not_found en producción: Groq los pasó a nivel Enterprise en su
    ola de deprecaciones de junio 2026."""
    cliente = _ClienteGroqFalso(contenido=_propuesta_esperada_json())

    extraer_propuesta("texto", _CONTEXTO, client=cliente)

    assert cliente.kwargs_recibidos["model"] == "openai/gpt-oss-120b"


def test_error_de_la_api_lanza_excepcion_controlada_del_dominio():
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    excepcion = groq.APIConnectionError(request=request)
    cliente = _ClienteGroqFalso(excepcion=excepcion)

    with pytest.raises(ErrorAsistente):
        extraer_propuesta("texto cualquiera", _CONTEXTO, client=cliente)


def test_timeout_lanza_excepcion_controlada_del_dominio():
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    excepcion = groq.APITimeoutError(request=request)
    cliente = _ClienteGroqFalso(excepcion=excepcion)

    with pytest.raises(ErrorAsistente):
        extraer_propuesta("texto cualquiera", _CONTEXTO, client=cliente)


def test_respuesta_que_no_cumple_el_esquema_lanza_excepcion_controlada():
    """Un modelo pequeño como Llama 3.1 8B no garantiza el esquema como el
    `output_format` de Anthropic: hay que validar y convertir el fallo en un
    error de dominio, nunca dejar escapar una excepción de pydantic cruda."""
    cliente = _ClienteGroqFalso(contenido=json.dumps({"tipo": "no_existe"}))

    with pytest.raises(ErrorAsistente):
        extraer_propuesta("texto cualquiera", _CONTEXTO, client=cliente)


def test_el_prompt_de_sistema_no_incluye_la_fecha_de_hoy():
    cliente = _ClienteGroqFalso(contenido=_propuesta_esperada_json())

    extraer_propuesta("texto", _CONTEXTO, client=cliente)

    bloque_sistema = cliente.kwargs_recibidos["messages"][0]["content"]
    assert "2026" not in bloque_sistema
    assert bloque_sistema.count("Mañana") >= 1


def test_el_prompt_distingue_peticion_de_cambio_y_de_regalo():
    """Fase 5B — el fallo dominante del dev set (20/60) era confundir tipos que
    el prompt nunca definía, solo los nombraba. Sin esta distinción, el modelo
    no puede diferenciar 'me cambian X por Y' (cambio) de 'que me cubran X, ya
    veremos' (peticion, sin aceptados concretos)."""
    cliente = _ClienteGroqFalso(contenido=_propuesta_esperada_json())

    extraer_propuesta("texto", _CONTEXTO, client=cliente)

    bloque_sistema = cliente.kwargs_recibidos["messages"][0]["content"]
    assert "aceptados" in bloque_sistema and "cedidos" in bloque_sistema
    assert "mismo día" in bloque_sistema


def test_el_prompt_aclara_que_hago_por_invierte_la_direccion_de_cambio_por():
    """Bug real (2026-08-28): 'Hago M2,3 sept por M 9 sept' se interpretaba
    igual que 'Cambio M2,3 sept por M 9 sept', cuando es al revés: en 'Hago X
    por Y' quien escribe se ofrece a trabajar X (aceptados) a cambio de que
    le cubran Y (cedidos)."""
    cliente = _ClienteGroqFalso(contenido=_propuesta_esperada_json())

    extraer_propuesta("texto", _CONTEXTO, client=cliente)

    bloque_sistema = cliente.kwargs_recibidos["messages"][0]["content"]
    assert "Hago" in bloque_sistema
    assert "al revés" in bloque_sistema


def test_el_prompt_infiere_franja_de_fechas_ofrecidas_sin_franja_propia():
    """Bug real (2026-08-28): 'Necesito librar las T del 9 y 11...\nPuedo
    hacer: 31 agosto, 1, 4 u 8 septiembre' — sin esta regla el modelo trataba
    las fechas ofrecidas como si aceptara cualquier franja, en vez de asumir
    la misma franja (Tarde) que se cede."""
    cliente = _ClienteGroqFalso(contenido=_propuesta_esperada_json())

    extraer_propuesta("texto", _CONTEXTO, client=cliente)

    bloque_sistema = cliente.kwargs_recibidos["messages"][0]["content"]
    assert "esas fechas ofrecidas son de esa misma franja cedida" in bloque_sistema


def test_pide_el_mensaje_del_usuario_con_la_fecha_de_hoy_antepuesta():
    cliente = _ClienteGroqFalso(contenido=_propuesta_esperada_json())

    extraer_propuesta("cambio mi mañana", _CONTEXTO, client=cliente)

    mensaje_usuario = cliente.kwargs_recibidos["messages"][1]["content"]
    assert mensaje_usuario.startswith("Hoy es")
    assert "cambio mi mañana" in mensaje_usuario


def test_el_mensaje_de_error_incluye_el_detalle_original_para_diagnostico():
    """El route solo loguea str(exc); si perdemos el detalle aquí, en producción
    no hay forma de saber si un fallo fue timeout, rate limit o auth sin
    reproducirlo a mano."""
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    excepcion = groq.APITimeoutError(request=request)
    cliente = _ClienteGroqFalso(excepcion=excepcion)

    with pytest.raises(ErrorAsistente) as exc_info:
        extraer_propuesta("texto cualquiera", _CONTEXTO, client=cliente)

    assert "timed out" in str(exc_info.value).lower()


# --- _extraer_propuesta_anthropic (DESACTIVADO, ver docs/crear_parser.md) ---
# Nada en la app llama a esta función; se conserva y se sigue testeando por
# si se recupera como motor en el futuro.

def test_anthropic_desactivado_con_cliente_falso_devuelve_la_propuesta_parseada():
    propuesta = _propuesta_esperada()
    cliente = _ClienteAnthropicFalso(respuesta=SimpleNamespace(parsed_output=propuesta))

    resultado = _extraer_propuesta_anthropic(
        "cambio mi mañana del 28 por tu tarde del 29", _CONTEXTO, client=cliente
    )

    assert resultado is propuesta
    assert cliente.kwargs_recibidos["output_format"] is PropuestaPublicacion


def test_anthropic_desactivado_error_de_la_api_lanza_excepcion_controlada():
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    excepcion = anthropic.APIConnectionError(request=request)
    cliente = _ClienteAnthropicFalso(excepcion=excepcion)

    with pytest.raises(ErrorAsistente):
        _extraer_propuesta_anthropic("texto cualquiera", _CONTEXTO, client=cliente)


def test_anthropic_desactivado_pide_extended_thinking_porque_haiku_4_5_no_soporta_adaptive():
    """Haiku 4.5 solo acepta extended thinking; 'adaptive' devuelve un 400
    ('adaptive thinking is not supported on this model')."""
    cliente = _ClienteAnthropicFalso(respuesta=SimpleNamespace(parsed_output=_propuesta_esperada()))

    _extraer_propuesta_anthropic("texto", _CONTEXTO, client=cliente)

    thinking = cliente.kwargs_recibidos["thinking"]
    assert thinking["type"] == "enabled"
    assert thinking["budget_tokens"] >= 1024
