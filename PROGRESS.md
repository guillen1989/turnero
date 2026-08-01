# Estado del desarrollo

## Fase actual
Fase 16 — Feature flag general `multi_unidad` para poder desactivar por
completo el sistema de usuarios en varios servicios, plan completo en
`docs/FEAT_FLAG_MULTI.md`.

## Paso actual / siguiente paso
Paso 5 completado. Siguiente: Paso 6 de `docs/FEAT_FLAG_MULTI.md` —
Notificaciones y Web Push: etiquetas de unidad.

## Decisiones de diseño (Fase 16)
- Un único flag `multi_unidad`, reutilizando `FeatureFlag`/`feature_activa`
  tal cual (sin tabla ni mecanismo nuevo). "Global-only" se consigue por
  convención: nunca se puebla `FeatureFlagUnidad` para esta clave, y el
  `<select>` de unidades se oculta para ella en el admin de flags.
  Detalle completo en `docs/FEAT_FLAG_MULTI.md`.

## Últimos pasos completados
- [x] Fase 16, Paso 5 (`docs/FEAT_FLAG_MULTI.md`) — Registro: bloque "añadir otro
  servicio" oculto con flag desactivado, `_resolver_extra_servicio` ignora campos
  extra. Tests en `test_auth_routes.py`.
- [x] Fase 16, Paso 4 (`docs/FEAT_FLAG_MULTI.md`) — Rutas de gestión de servicios
  decoradas con `@requiere_feature("multi_unidad")`, pestaña "Servicios" oculta en
  perfil. Bug corregido en `test_abandonar_unidad_con_flag_inactivo_devuelve_404`
  (crear unidad directamente en vez de vía registro).
- [x] Fase 16, Paso 3 (`docs/FEAT_FLAG_MULTI.md`) — Choke points centrales:
  `unidades_de` y `unidad_activa_o_403` comprueban `feature_activa("multi_unidad")`.
  Tests en `tests/test_unidad_usuario.py` (7 tests: 3 clases). `pertenece_a`
  sin cambios (con test de no-regresión). `multi_unidad` añadido a conftest.
- [x] Fase 16, Paso 2 (`docs/FEAT_FLAG_MULTI.md`) — Admin: ocultar `<select>` de
  unidades para el flag `multi_unidad` con mensaje "Este flag es global". Test
  en `test_admin_feature_flags.py::test_multi_unidad_no_muestra_selector_unidades`.
- [x] Fase 16, Paso 1 (`docs/FEAT_FLAG_MULTI.md`) — Migración de seed `multi_unidad`
  (`40d2e20fa8f0`), activado por defecto (`activo_global=True`), aplicado en local.
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
