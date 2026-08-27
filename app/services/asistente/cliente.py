"""Cliente de la API de Anthropic: convierte un mensaje libre en una PropuestaPublicacion.

Aísla el resto de la app de la librería `anthropic` — solo este módulo importa
o captura sus excepciones.
"""
import anthropic

from app.services.asistente.schema import PropuestaPublicacion

_MODELO = "claude-haiku-4-5"
_MAX_TOKENS = 2048


class ErrorAsistente(Exception):
    """La API del asistente no ha podido resolver la propuesta (red, timeout, etc.)."""


def _construir_prompt(contexto):
    """Prompt de sistema: solo contenido estático por grupo, cacheable entre llamadas.

    No debe incluir la fecha de hoy ni nada variable: invalidaría la caché de
    prompt de Anthropic, que se activa sobre el bloque `system` completo.
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
        "- Si falta algún dato imprescindible para completar la propuesta, indícalo "
        "en `campos_faltantes` en vez de inventarlo."
    )


def _construir_mensaje_usuario(texto, hoy):
    dias_semana = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
    dia = dias_semana[hoy.weekday()]
    return f"Hoy es {dia} {hoy.isoformat()}.\n\n{texto}"


def extraer_propuesta(texto, contexto, client=None):
    if client is None:
        client = anthropic.Anthropic()

    try:
        respuesta = client.messages.parse(
            model=_MODELO,
            max_tokens=_MAX_TOKENS,
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
