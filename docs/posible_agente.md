Recomendación corta

  Haz la opción 1 y déjala preparada para convertirse en la 3. Descarta la 2.

  En este código las opciones 1 y 3 no son dos arquitecturas distintas: las dos terminan en "propuesta estructurada → el usuario confirma → se 
  ejecuta el camino de publicación que ya existe". Solo cambia el modo de entrada (pegar un texto de una vez vs. conversación con preguntas). La 3
  es un incremento pequeño sobre la 1: añadir al esquema un campo de "qué me falta" y un bucle de repregunta.

  La opción 2 es la peor de las tres: hace el trabajo difícil (interpretar lo que quiere el usuario) y luego le devuelve el trabajo tedioso (meter
  fechas y franjas a mano). Captura poco del valor y encima tiene un modo de fallo feo: el asistente describe pasos que no coinciden con lo que
  el usuario ve en pantalla.
  
  ---
  Pros y contras

  1) Parser (pegar mensaje de WhatsApp)
  - ➕ El input ya existe: la gente ya escribe estos mensajes. No hay que enseñar nada nuevo.
  - ➕ Una sola llamada al modelo, sin estado conversacional. Latencia y coste predecibles.
  - ➕ Fácil de evaluar: coges 50 mensajes reales y mides aciertos.
  - ➖ Si el mensaje es ambiguo ("cambio el finde"), solo puedes fallar o adivinar; no hay repregunta.

) Consejero
  - ➕ Cero riesgo: no escribe en la BD.
  - ➖ Deja al usuario el trabajo aburrido justo después de haberle hecho explicarlo todo.
  - ➖ Las instrucciones se desincronizan con la UI en cada cambio de plantilla y hay que mantenerlas traducidas.
  - ➖ Rompe el hábito de i18n: el texto que genera el modelo no pasa por gettext.

  3) Agente conversacional
  - ➕ Resuelve la ambigüedad que la 1 no puede.
  - ➕ Cubre al usuario que no tiene un mensaje escrito, solo una idea.
  - ➖ Estado conversacional, más tokens, más latencia, más superficie de prompt injection.
  - ➖ No lo construyas primero: sin la 1 funcionando no sabes si el problema real es entender el texto o entender al usuario.

  ---
  Cómo se implementa (la parte que importa)
  
  La decisión de diseño clave: el modelo emite JSON estructurado y nunca llama a herramientas de escritura. Nada de tool-use con publicar_cambio
  como tool. El modelo propone; Python valida y ejecuta.
 1. Contrato de salida

  # app/services/asistente_publicacion.py
  class TurnoPropuesto(BaseModel):
      fecha: date
      franja: str | None      # nombre de FranjaHoraria, None = cualquiera
      
  class PropuestaPublicacion(BaseModel):
      tipo: Literal["cambio", "regalo", "peticion", "junte", "cambio_dia"]
      turnos_cedidos: list[TurnoPropuesto]
      turnos_aceptados: list[TurnoPropuesto]
      mensaje: str | None
      campos_faltantes: list[str]   # vacío = propuesta completa
      
  Ese último campo es lo que convierte la opción 1 en la 3 sin rediseñar nada: si viene vacío, prefill directo; si no, repreguntas.

  2. La llamada

  import anthropic
  client = anthropic.Anthropic()

  resp = client.messages.parse(
      model="claude-opus-5",
      max_tokens=2000,
      thinking={"type": "adaptive"},
      system=[{
          "type": "text",
          "text": _prompt_sistema(grupo),   # franjas válidas del grupo, tipos, reglas
          "cache_control": {"type": "ephemeral"},
      }], 
      messages=[{"role": "user", "content": texto_pegado}],
      output_format=PropuestaPublicacion,
  )   
  propuesta = resp.parsed_output

  El prompt de sistema es por grupo de intercambio, no global: le inyectas el vocabulario cerrado de FranjaHoraria (nombre, hora_inicio, hora_fin)
  de ese grupo, la fecha de hoy, y la planilla del usuario si la tiene cargada. Ese prompt es idéntico para todos los usuarios del mismo grupo →
  con el cache_control de arriba, a partir de la segunda llamada del grupo pagas ~0,1× por ese prefijo. Como el prompt es estable, ponlo entero
  antes del mensaje del usuario y no le metas datetime.now() con hora: usa solo la fecha, o invalidas la caché en cada petición.

3. Resolución en Python, no en el modelo

  El modelo devuelve nombres de franja y fechas ISO. El servidor:
  - resuelve franja → franja_horaria_id contra FranjaHoraria del grupo del usuario (si no casa exacto → campos_faltantes);
  - resuelve fechas relativas ("el martes", "el finde") contra hoy y, si existe, la planilla del usuario (app/services/planilla.py) — esto es lo
  que permite que "te cambio mi noche del jueves" se convierta en la franja real que tiene asignada;
  - pasa el resultado por _validar_turnos y validar_publicacion_cambio_dia, que ya existen y ya están testeados.

  4. La confirmación es el formulario que ya tienes

  No construyas una pantalla de confirmación nueva. Rellena /publicar con la propuesta usando el mismo mecanismo de prefill que ya usa
  _leer_prefill_calendario() en app/routes/publicaciones.py. Con eso:
  - la "confirmación obligatoria" se cumple sola: el usuario ve exactamente lo que se va a publicar en la UI real;
  - editar una fecha mal interpretada es gratis, no hay que volver al chat;
  - publicar_cambio(...) sigue siendo el único camino de escritura;
  - no añades ni una cadena de texto nueva a traducir.
5. Para la opción 3, encima de eso

  Añades sesión conversacional (guardando el historial de mensajes en servidor, no en el cliente), y el bucle: mientras campos_faltantes no esté
  vacío, generas una pregunta y vuelves a llamar con el historial. El resto —resolución, validación, prefill, publicación— no cambia ni una línea.

  ---
  Complejidad real

  ┌─────────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │         │                                                             Trabajo                                                             │
  ├─────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Opción  │ ~2-3 días. Un servicio nuevo (~200 líneas), una ruta, un modal para pegar el texto, y el prefill que ya existe. Dependencia     │
  │ 1       │ nueva: anthropic en requirements.txt + ANTHROPIC_API_KEY en Railway.                                                            │
  ├─────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Opción  │ +1-2 días sobre la 1. Sesión de chat, bucle de repregunta, plantilla de conversación.                                           │
  │ 3       │                                                                                                                                 │
  ├─────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Opción  │ ~2 días, y el resultado es peor que la 1.                                                                                       │
  │ 2       │                                                                                                                                 │
  └─────────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

  Lo caro no es el código, es el conjunto de evaluación: necesitas 40-60 mensajes reales de WhatsApp de tus usuarios con la publicación correcta
  anotada a mano. Sin eso no sabes si el parser acierta el 95% o el 60%, y esa diferencia decide si la función es útil o es una fuente de
  publicaciones mal puestas. Recógelos antes de escribir el prompt. 

  Coste operativo: con el prompt de sistema cacheado, una publicación son unos 2-3k tokens de entrada y ~300 de salida → del orden de 1-2 céntimos
  por publicación con claude-opus-5. A volumen alto merece la pena medir si claude-sonnet-5 mantiene la precisión en tu eval; es decisión tuya,
  no la tomes a ciegas.
Riesgos a cubrir desde el principio:
  - Prompt injection: el texto pegado viene de un tercero (el mensaje de WhatsApp puede haberlo escrito otra persona). Como el modelo solo emite
  JSON validado y no ejecuta nada, el peor caso es una propuesta absurda que el usuario ve y descarta. Ese es exactamente el motivo de no darle
  herramientas de escritura.
  - Visibilidad restringida: la resolución de franjas debe hacerse contra el grupo del usuario autenticado, nunca contra un id que venga en la
  respuesta del modelo.
  - i18n: el JSON estructurado no lleva texto de interfaz, así que la regla de gettext se mantiene intacta. Si algún día quieres que el asistente
  explique algo en prosa, ese texto no podrá pasar por el catálogo — tenlo presente antes de añadirlo.

  Método: rama desde staging en worktree, TDD sobre el servicio de parsing con los mensajes reales como fixtures, PR contra staging.


