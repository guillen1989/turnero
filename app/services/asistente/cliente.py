"""Cliente del asistente: convierte un mensaje libre en una PropuestaPublicacion.

Aísla el resto de la app de la librería del proveedor de IA — solo este
módulo importa o captura sus excepciones.

Motor activo: Groq (GPT-OSS 120B) — más barato y más rápido que Claude
Haiku. La lógica original con Anthropic se conserva desactivada al final
del archivo (ver decisión 2026-08-28 en docs/crear_parser.md); nada la
invoca.

Nota: llama-3.1-8b-instant y llama-3.3-70b-versatile (probados antes)
devuelven 404 model_not_found en producción — Groq los pasó a nivel
Enterprise en su ola de deprecaciones de junio 2026. openai/gpt-oss-120b
es el modelo de mayor capacidad que sigue disponible en el tier free/dev.
"""
import anthropic
import groq
from pydantic import ValidationError

from app.services.asistente.schema import PropuestaPublicacion

_MODELO = "openai/gpt-oss-120b"
_MAX_TOKENS = 2048


class ErrorAsistente(Exception):
    """La API del asistente no ha podido resolver la propuesta (red, timeout, formato, etc.)."""


def _construir_prompt(contexto):
    """Prompt de sistema: solo contenido estático por grupo, cacheable entre llamadas.

    No debe incluir la fecha de hoy ni nada variable: invalidaría la caché de
    prompt del proveedor, que se activa sobre el bloque de sistema completo.
    """
    franjas = "\n".join(
        f"- {f['nombre']}: {f['hora_inicio']}–{f['hora_fin']}"
        for f in contexto["franjas"]
    )
    tipos = ", ".join(contexto["tipos_validos"])
    return (
        "Eres un asistente que lee mensajes de WhatsApp entre compañeros "
        "sanitarios y extrae de ellos una propuesta de cambio de turno.\n\n"
        f"Franjas horarias válidas de este grupo:\n{franjas}\n\n"
        f"Tipos de publicación válidos: {tipos}\n\n"
        "Cómo distinguir el tipo (mira qué ofrece y qué pide el mensaje, no solo "
        "el verbo):\n"
        "- `cambio`: cede uno o más turnos concretos Y pide uno o más turnos "
        "concretos a cambio (fecha señalada en ambos lados).\n"
        "- `peticion`: solo quiere librar un turno concreto, sin ofrecer nada "
        "concreto a cambio ('a convenir', 'ya veremos', 'lo que sea', sin fecha "
        "para lo que ofrece). Usa `cedidos` con el turno a librar y "
        "`aceptados: []`.\n"
        "- `regalo`: ofrece trabajar un turno sin pedir nada a cambio. Usa "
        "`aceptados` con el turno ofrecido y `cedidos: []`.\n"
        "- `cambio_dia`: cede y acepta un turno del mismo día, en franjas "
        "distintas (p. ej. pasar de la mañana a la tarde el mismo día).\n"
        "- `junte`: cadena de varios turnos de una franja para agruparlos en "
        "menos días.\n\n"
        "Reglas:\n"
        "- Usa siempre el nombre de franja tal cual aparece en la lista anterior, "
        "traduciendo apodos o sinónimos que use el mensaje al nombre canónico.\n"
        "- Las fechas del mensaje del usuario son relativas a la fecha de hoy que "
        "él mismo indica al principio de su mensaje, nunca a este texto.\n"
        "- 'Hago <A> por <B>' es al revés de 'Cambio <A> por <B>': en 'Cambio' quien "
        "escribe cede A y pide B a cambio, pero en 'Hago' quien escribe se ofrece a "
        "trabajar A (va en `aceptados`) a cambio de que alguien le cubra B (va en "
        "`cedidos`).\n"
        "- Si un turno indica el día del mes pero no el mes (p. ej. 'T24', 'la N "
        "del 10'), y ningún otro turno del mismo mensaje aclara el mes, asume el "
        "mes en curso; si ese día ya pasó respecto a hoy, asume el mes siguiente.\n"
        "- Si el mensaje cede turnos de una única franja y después ofrece una lista "
        "de fechas sueltas sin volver a indicar franja en cada una (p. ej. tras "
        "'Puedo hacer:'), esas fechas ofrecidas son de esa misma franja cedida: no "
        "las dejes sin franja ni las trates como si aceptara cualquier franja.\n"
        "- Si falta algún dato imprescindible para completar la propuesta, indícalo "
        "en `campos_faltantes` en vez de inventarlo."
    )


def _construir_mensaje_usuario(texto, hoy):
    dias_semana = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
    dia = dias_semana[hoy.weekday()]
    return f"Hoy es {dia} {hoy.isoformat()}.\n\n{texto}"


_INSTRUCCION_JSON = (
    "\n\nResponde ÚNICAMENTE con un objeto JSON con esta forma exacta, sin "
    "texto adicional ni bloques de código:\n"
    '{"tipo": "cambio|peticion|regalo|cambio_dia|junte", '
    '"cedidos": [{"fecha": "YYYY-MM-DD o null si no se conoce", "franja": "nombre o null"}], '
    '"aceptados": [{"fecha": "YYYY-MM-DD o null si no se conoce", "franja": "nombre o null"}], '
    '"campos_faltantes": ["..."]}'
)


def extraer_propuesta(texto, contexto, client=None):
    """Motor activo: Groq (GPT-OSS 120B)."""
    if client is None:
        client = groq.Groq()

    try:
        respuesta = client.chat.completions.create(
            model=_MODELO,
            max_completion_tokens=_MAX_TOKENS,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": _construir_prompt(contexto) + _INSTRUCCION_JSON,
                },
                {
                    "role": "user",
                    "content": _construir_mensaje_usuario(texto, contexto["hoy"]),
                },
            ],
        )
    except groq.GroqError as e:
        raise ErrorAsistente(f"Error al comunicarse con la API del asistente: {e}") from e

    contenido = respuesta.choices[0].message.content
    try:
        return PropuestaPublicacion.model_validate_json(contenido)
    except ValidationError as e:
        raise ErrorAsistente(
            f"La respuesta del asistente no tiene el formato esperado: {e}"
        ) from e


# ============================================================================
# DESACTIVADO (2026-08-28) — motor original con Anthropic Claude Haiku 4.5.
#
# Se sustituye por Groq/Llama 3.1 8B (más barato y más rápido, ver decisión
# en docs/crear_parser.md). Nada en la app invoca esta función; se conserva
# tal cual por si se quiere recuperar como motor más adelante.
# ============================================================================

_MODELO_ANTHROPIC = "claude-haiku-4-5"
_MAX_TOKENS_ANTHROPIC = 2048


def _extraer_propuesta_anthropic(texto, contexto, client=None):
    if client is None:
        client = anthropic.Anthropic()

    try:
        respuesta = client.messages.parse(
            model=_MODELO_ANTHROPIC,
            max_tokens=_MAX_TOKENS_ANTHROPIC,
            thinking={"type": "enabled", "budget_tokens": 1024},
            system=[
                {
                    "type": "text",
                    "text": _construir_prompt(contexto),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {"role": "user", "content": _construir_mensaje_usuario(texto, contexto["hoy"])}
            ],
            output_format=PropuestaPublicacion,
        )
    except anthropic.AnthropicError as e:
        raise ErrorAsistente(f"Error al comunicarse con la API del asistente: {e}") from e

    return respuesta.parsed_output
