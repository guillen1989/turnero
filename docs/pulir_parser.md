# Pulir el parser en producción

El parser de mensajes de WhatsApp ya está desplegado (ver `docs/plan_trabajo_parser.md`,
cerrado). Este documento recoge el proceso para seguir mejorándolo a partir de
fallos reales detectados en uso, ya sea en QA manual o en producción. No reemplaza
al plan anterior, es su continuación.

## Proceso, paso a paso

1. **Detectar un fallo real.** Un mensaje real que el parser interpretó mal
   (tipo equivocado, cedidos/aceptados intercambiados o incompletos, mensaje
   que no consiguió interpretar).
2. **Anotar la interpretación correcta** y añadirla como entrada nueva en
   `tests/fixtures/corpus/dev.jsonl`, con el siguiente id libre (`wNNN`).
   Cada entrada: `id`, `texto` (el mensaje tal cual, emojis incluidos),
   `fecha_mensaje` (fecha real en que se recibió), `esperado` (`tipo`,
   `cedidos`, `aceptados`).
3. **Ejecutar el eval contra todo el dev set**, no solo el caso nuevo:
   ```bash
   cd <worktree en staging>
   PYTHONPATH=. python3 scripts/eval_parser.py tests/fixtures/corpus/dev.jsonl
   ```
   Esto evita el error de "arreglar el caso reportado y romper otros diez en
   silencio". El número que importa es el del corpus entero, no el del mensaje
   que acabas de meter.
4. **Diagnosticar el fallo dominante** antes de tocar el prompt. Usa
   `--detalle salida.jsonl` para ver el JSON crudo de cada fallo:
   ```bash
   PYTHONPATH=. python3 scripts/eval_parser.py tests/fixtures/corpus/dev.jsonl --detalle /tmp/fallos.jsonl
   ```
   El histograma de `eval_parser.py` (`cedido_de_mas`, `cedido_de_menos`,
   `aceptado_de_mas`, `aceptado_de_menos`, `tipo`) dice qué tipo de error
   predomina. Ataca el más frecuente primero, no el último mensaje que llegó.
5. **Ajustar el prompt/reglas** en `app/services/asistente/cliente.py` (o los
   few-shot del corpus) para atacar ese patrón.
6. **Re-ejecutar el eval contra dev set completo.** Solo se considera una
   mejora real si el número global sube (o al menos no baja) respecto al
   baseline anterior — no basta con que el caso nuevo pase.
7. **Test set aparte.** No se toca `tests/fixtures/corpus/test.jsonl` en cada
   iteración. Se consulta solo de forma esporádica, cuando el dev set lleva
   un tiempo por encima del umbral, para comprobar que no hay sobreajuste al
   dev set.
8. **Commit atómico**: corpus (`dev.jsonl`) + cambio de prompt/reglas +
   registro de la nueva medición en la tabla de abajo, todo en un mismo commit.

## Umbrales

El umbral propuesto en `docs/plan_trabajo_parser.md` (≥90% exact match / <2%
error silencioso) **nunca se llegó a alcanzar** antes de salir a producción —
el parser se desplegó sin superar esa puerta. El objetivo de este documento es
seguir iterando con mensajes reales hasta alcanzarlo de verdad, no dar por
bueno el número del día ni bajar el umbral para que cuadre con lo que hay.

## Notas

- **Fechas de solo-día cerca de fin de mes.** Algunas entradas anotadas
  (`w006`, `w020`, `w027`, `w036`) mencionan un día sin mes explícito cerca
  del cambio de mes, donde la regla genérica del prompt ("si el día ya pasó,
  asumir el mes siguiente") no basta por sí sola para determinar la
  intención real: el parser solo recibe el mensaje aislado, sin el hilo de
  conversación de WhatsApp que a veces es la única fuente real de esa
  información (`w006`/`w020`), o donde el nombre del día de la semana
  desambigua mejor que la regla genérica (`w027`). Se optó por la **opción
  1**: mantener en el corpus la interpretación verdadera/informada por
  contexto en vez de la que produciría la regla genérica a ciegas, aceptando
  que algunos de estos casos son estructuralmente irresolubles con solo el
  mensaje aislado (el modelo no tiene forma de acertar sin ese contexto).
  Si esto da resultados pobres o inconsistentes en la práctica, la
  **alternativa pendiente (opción 2)** es re-anotar estos casos para que
  coincidan con la heurística estricta "el día ya pasó → mes siguiente" sin
  contexto de hilo, de forma que el eval mida cumplimiento de la regla en
  vez de acierto de la intención real.

## Historial de medición (dev set)

| Fecha | Anotadas | Exact match | Error silencioso | Nota |
|---|---|---|---|---|
| 2026-08-30 | 66 | 48.5% (32/66) | 33.3% (22/66) | Baseline tras sumar 7 mensajes reales de QA manual (`w304`-`w310`); histograma: cedido_de_mas 19, cedido_de_menos 21, tipo 14, aceptado_de_mas 23, aceptado_de_menos 20 |
| 2026-08-30 | 66 | 50.0% (33/66) | 24.2% (16/66) | Mismo baseline, remedido tras corregir un bug del propio arnés (`_turnos_a_tuplas` comparaba franja sin normalizar mayúsculas/minúsculas, inflando `error_silencioso` en todas las medidas anteriores); también se corrigió `w310` para ser consistente con `w019` |
| 2026-08-30 | 66 | 53.0% (35/66) | 30.3% (20/66) | + 2 reglas de dirección en el prompt (patrón "Alguien hace A por B" y dirección en `cambio_dia`); mejora exact match pero empeora error_silencioso, en su mayoría por ruido de franja/tipo no relacionado con las reglas nuevas |
| 2026-08-30 | 66 | 71.2% (47/66) | 21.2% (14/66) | + 5 ejemplos few-shot (turnos de conversación reales, no reglas en prosa) cubriendo peticion-vs-cambio con oferta vaga, dirección en cambio_dia, e inversión de "Hago". Mejora ambas métricas a la vez; probado también `reasoning_effort="high"` en gpt-oss-120b, descartado por provocar fallos de validación JSON. Histograma restante: aceptado_de_mas 10, cedido_de_menos 10, tipo 8, cedido_de_mas 7, aceptado_de_menos 6 |
| 2026-08-30 | 66 | 78.8% (52/66) | 12.1% (8/66) | Comparación de motor con el mismo prompt (reglas + few-shot): `qwen/qwen3.8-27b` supera a `openai/gpt-oss-120b` (71.2%/21.2%) en ambas métricas. Se adopta `qwen/qwen3.8-27b` como motor activo. No se prueban `qwen/qwen3.6-27b` ni `groq/compound-mini` (decisión del usuario: quedarse con qwen). Histograma: tipo 4, aceptado_de_mas 8, cedido_de_mas 7, cedido_de_menos 7, aceptado_de_menos 7, fallo_extraccion 3 |
| 2026-08-30 | 202 | 83.2% (168/202) | 11.9% (24/202) | Baseline honesto tras: (1) anotar 207 mensajes reales más del corpus sin usar (`tests/fixtures/corpus/test.jsonl`, descargados en la Fase 5 pero nunca anotados), (2) repartir 75/25 aleatorio (semilla 42) entre `dev.jsonl`/`test.jsonl`, (3) arreglar la fuga de datos original: `w008`/`w010`/`w011` ya no cuentan como evaluación en `dev.jsonl` (siguen en el archivo como fuente de few-shot, pero con `esperado: null`), (4) arreglar un bug del arnés (`_turnos_a_tuplas` no ordenaba turnos con `fecha: null` mezclada con fechas concretas). Histograma: tipo 17, aceptado_de_mas 21, cedido_de_mas 13, cedido_de_menos 14, aceptado_de_menos 13 |
| 2026-08-30 | 202 | 82.2% (166/202) | 15.8% (32/202) | **Probado y descartado.** + 1 regla de prosa ("cambio a 3" es jerga de favor a plazo, no una fecha literal) + 2 ejemplos few-shot (rollover de mes en fecha-sin-mes con dos turnos; "cambio a 3" como petición). Empeora ambas métricas respecto al baseline anterior (exact match -1.0pp, error_silencioso +3.9pp) en vez de mejorarlas. Histograma: tipo 19, aceptado_de_mas 16, cedido_de_mas 15, cedido_de_menos 15, aceptado_de_menos 16. No se investigó a fondo el porqué de la regresión (más ejemplos few-shot pueden diluir la atención del modelo sobre las reglas existentes); revertido íntegramente en `cliente.py`, se mantiene la versión anterior (83.2%/11.9%) como estado activo. Pendiente: si se reintenta este patrón, probar los dos cambios por separado en vez de juntos, para aislar cuál de los dos causa la regresión. |
