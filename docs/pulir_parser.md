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

## Historial de medición (dev set)

| Fecha | Anotadas | Exact match | Error silencioso | Nota |
|---|---|---|---|---|
| 2026-08-30 | 66 | 48.5% (32/66) | 33.3% (22/66) | Baseline tras sumar 7 mensajes reales de QA manual (`w304`-`w310`); histograma: cedido_de_mas 19, cedido_de_menos 21, tipo 14, aceptado_de_mas 23, aceptado_de_menos 20 |
