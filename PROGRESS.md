# Estado del desarrollo

## Fase actual
Fase 16 — Feature flag general `multi_unidad` para poder desactivar por
completo el sistema de usuarios en varios servicios, plan completo en
`docs/FEAT_FLAG_MULTI.md`.

## Paso actual / siguiente paso
Empezar por el Paso 1 de `docs/FEAT_FLAG_MULTI.md`: migración de seed que
crea el flag `multi_unidad` (desactivado por defecto).

## Decisiones de diseño (Fase 16)
- Un único flag `multi_unidad`, reutilizando `FeatureFlag`/`feature_activa`
  tal cual (sin tabla ni mecanismo nuevo). "Global-only" se consigue por
  convención: nunca se puebla `FeatureFlagUnidad` para esta clave, y el
  `<select>` de unidades se oculta para ella en el admin de flags.
  Detalle completo en `docs/FEAT_FLAG_MULTI.md`.

## Últimos pasos completados
- [x] Fase 15 (`docs/FIX_MULTI.md`) cerrada — Paso 5: Cierre: suite completa en verde (1503
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
