"""Sinónimos de motes de franjas observados en mensajes de WhatsApp.

Clave: forma normalizada (ver `resolver._normalizar`) del mote.
Valor: nombre canónico de la franja tal como se busca en FranjaHoraria.

Se alimenta de docs/vocabulario_corpus.md conforme se anote el corpus real
(Fase 0.1 de docs/crear_parser.md). De momento solo hay ejemplos semilla.
"""

SINONIMOS_FRANJA = {
    "mañanita": "Mañana",
}
