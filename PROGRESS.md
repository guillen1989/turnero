# Estado del desarrollo

## Fase actual
Fase 15 — Arreglar deuda pendiente de multi-unidad (usuarios en varios
servicios), plan completo en `docs/FIX_MULTI.md`. **COMPLETADA.**

## Paso actual / siguiente paso
Fase 15 cerrada. Todos los pasos (0-5) completados. Siguiente fase pendiente
de definir.

## Decisiones de diseño (Paso 0)
- "Mis cambios publicados": bandeja única con etiqueta de unidad.
- Planilla: una planilla por unidad (columna de unidad en `TurnoPlanilla`
  y compañía, requiere migración de modelo).

## Últimos pasos completados
- [x] Paso 5 (`docs/FIX_MULTI.md`) — Cierre: suite completa en verde (1503
  passed), PROGRESS.md cerrando Fase 15, revisión de código muerto.
- [x] Paso 4 (`docs/FIX_MULTI.md`) — `busquedas.py:32` validación de franja
  con unidad activa; `unidad.py` (5 líneas) con `unidad_activa_o_403`.
  Tests en `test_busquedas_guardadas.py` y `test_turnos_unidad.py`.
- [x] Paso 3 (`docs/FIX_MULTI.md`) — `PublicacionCambio.unidad_id` + bandeja
  única etiquetada en dashboard.
- [x] Paso 2 (`docs/FIX_MULTI.md`) — Selector de unidad al crear hoja de
  cambio.
- [x] Paso 1 (`docs/FIX_MULTI.md`) — `TurnoPlanilla` (y compañía) por unidad.
- [x] Paso 0 (`docs/FIX_MULTI.md`) — decisiones de diseño confirmadas.

## Historial completo
El registro detallado de fases y pasos anteriores está en
`PROGRESS_ARCHIVE.md`.

## Notas / decisiones / asunciones pendientes
- La unidad principal del usuario siempre aparece en `usuario_unidad`
  (invariante sembrado por el backfill de la migración; `sincronizar_unidades`
  lo mantiene y no permite eliminarla).
- `unidad_activa_o_403` sigue la precedencia query param > sesión
  (`session["unidad_activa_id"]`) > unidad principal. Persiste en sesión
  automáticamente cuando se pasa `unidad_id` explícito por query param.
- Los 21 casos "MUST change" de la auditoría de `docs/USUARIOS_MULTI.md`
  (Paso 5) ya están resueltos en los Pasos 1-4 de esta fase.
- `unidad.py` usa `unidad_activa_o_403` (no `unidad_supervisada_o_403`)
  porque la configuración de turnos es una acción de la unidad activa del
  usuario, no exclusiva de supervisoras.
- Preguntas abiertas del plan de la Fase 13 (registro libre de unidades,
  abandono de unidad) siguen pendientes de confirmar.
