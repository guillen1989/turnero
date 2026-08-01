# Estado del desarrollo

## Fase actual
Tras fusionar `staging` en `main` hay dos frentes activos en paralelo:
1. Publicación en Google Play Store (`docs/PLAN_PLAY_STORE.md`) — Fase 6
   (pruebas cerradas) en curso; Fase 3 (aspectos legales) completa; Fase 2
   (dominio) parcialmente completa.
2. Fase 16 — Feature flag general `multi_unidad` para poder desactivar por
   completo el sistema de usuarios en varios servicios, plan completo en
   `docs/FEAT_FLAG_MULTI.md`.

## Paso actual / siguiente paso
- Multi-unidad (Fase 16): empezar por el Paso 1 de `docs/FEAT_FLAG_MULTI.md`:
  migración de seed que crea el flag `multi_unidad` (desactivado por
  defecto).
- Play Store (en paralelo): resuelta la incidencia crítica de nivel de API
  de destino (ver "Últimos pasos completados"); esperar la confirmación de
  Google de que la app ya no está afectada, y seguir con lo pendiente de la
  Fase 6 (mantener la pista cerrada activa 14 días con ≥12 testers).
  Pendiente también Fase 2 (actualizar `APP_BASE_URL`/referencias de URL de
  producción en el repo para usar `app.turnero.xyz`, y verificar que
  `/manifest.json` y `/sw.js` se sirven correctamente desde ese dominio).

## Decisiones de diseño (Fase 16)
- Un único flag `multi_unidad`, reutilizando `FeatureFlag`/`feature_activa`
  tal cual (sin tabla ni mecanismo nuevo). "Global-only" se consigue por
  convención: nunca se puebla `FeatureFlagUnidad` para esta clave, y el
  `<select>` de unidades se oculta para ella en el admin de flags.
  Detalle completo en `docs/FEAT_FLAG_MULTI.md`.

## Últimos pasos completados
- [x] Fase 15 (`docs/FIX_MULTI.md`) cerrada — Paso 5: Cierre: suite completa
  en verde (1503 passed), PROGRESS.md cerrando Fase 15, revisión de código
  muerto.
- [x] Paso 4 (`docs/FIX_MULTI.md`) — `busquedas.py:32` validación de franja
  con unidad activa; `unidad.py` (5 líneas) con `unidad_activa_o_403`.
  Tests en `test_busquedas_guardadas.py` y `test_turnos_unidad.py`.
- [x] Paso 3 (`docs/FIX_MULTI.md`) — `PublicacionCambio.unidad_id` + bandeja
  única etiquetada en dashboard.
- [x] Paso 2 (`docs/FIX_MULTI.md`) — Selector de unidad al crear hoja de
  cambio.
- [x] Paso 1 (`docs/FIX_MULTI.md`) — `TurnoPlanilla` (y compañía) por unidad.
- [x] Paso 0 (`docs/FIX_MULTI.md`) — decisiones de diseño confirmadas.
- [x] Incidencia de nivel de API de destino (2026-07-31): Google avisó de que
  `targetSdkVersion 35` incumplía el requisito de Android 16 (API 36) antes
  del 31 ago 2026. Corregido `android-twa/app/build.gradle`
  (`targetSdkVersion` → 36, `versionCode`/`versionName` → 2/"1.0.1") y
  `android-twa/twa-manifest.json` en paralelo; nuevo `.aab` firmado por el
  usuario y subido a la pista cerrada. Detalle completo, incluido un bug
  conocido de la plantilla de Bubblewrap CLI que hay que recordar si se
  regenera el proyecto, en `docs/PLAN_PLAY_STORE.md` ("Incidencia: nivel de
  API de destino").
- [x] `docs/PLAN_PLAY_STORE.md` incorporado a esta rama (basada en `main`,
  el archivo solo existía en `staging`).
- [x] Fase 1, paso 1: auditoría Lighthouse categoría PWA contra
  `https://staging.turnero.xyz/` — puntuación 1.0/1.0. Detalle e informe en
  `docs/PLAN_PLAY_STORE.md` (sección "Notas de ejecución") y
  `docs/audits/lighthouse-pwa-staging-2026-07-28.html`.
- [x] Fase 1, paso 2: verificada la zona segura "maskable" de
  `icon-192.png`/`icon-512.png`. La ilustración ya respetaba el margen del
  10%, pero el fondo azul tenía un halo blanco de ~2.5% que no llegaba al
  borde — regenerados ambos PNG rellenando el anillo exterior con el mismo
  azul sólido (borde a borde, sin transparencia). Detalle en
  `docs/PLAN_PLAY_STORE.md`.
- [x] Fase 1, paso 3: añadida página offline (`/offline`) y fallback en
  `app/static/sw.js` para peticiones de navegación sin red.
- [x] Fase 1, pasos 4 y 5 (cierran la Fase 1): verificado que
  `theme_color`/`background_color` del manifest coinciden con el diseño y
  que no hay contenido mixto `http://` en templates/estáticos — sin cambios
  de código, solo verificación. Detalle en `docs/PLAN_PLAY_STORE.md`.
- [x] Fase 2, decisión de dominio: `app.turnero.xyz`, ya configurado en
  Railway y en producción desde hace dos semanas (**[ACCIÓN HUMANA]**
  resuelta por el usuario). Quedan pendientes los pasos de código de la
  Fase 2 (actualizar `APP_BASE_URL` y verificar manifest/SW en ese dominio).
- [x] Fase 12 (`docs/PLAN_3.md`, hojas de cambio "a 3"/cadena_3) completa y
  cerrada en `staging` (8 pasos); incorporada a `main` al fusionar `staging`.
  Detalle paso a paso archivado en `PROGRESS_ARCHIVE.md`.
- [x] Fase 3 completa: páginas públicas `/privacidad`, `/terminos` y
  `/eliminar-cuenta` (`app/routes/main.py` + `app/templates/main/`),
  enlazadas desde `base.html` y `auth/registro.html`, catálogo de
  traducción actualizado y tests en `tests/test_paginas_legales.py`. Detalle
  en `docs/PLAN_PLAY_STORE.md`.

## Notas / decisiones / asunciones pendientes
- Lighthouse v13 (la que instala `npx lighthouse` por defecto) ya no trae la
  categoría `pwa` — Google la retiró del core. Para repetir esta auditoría
  en el futuro hay que fijar una versión antigua, p. ej. `npx lighthouse@10`.
- La unidad principal del usuario siempre aparece en `usuario_unidad`
  (invariante sembrado por el backfill de la migración; `sincronizar_unidades`
  lo mantiene y no permite eliminarla).
- `unidad_activa_o_403` sigue la precedencia query param > sesión
  (`session["unidad_activa_id"]`) > unidad principal. Persiste en sesión
  automáticamente cuando se pasa `unidad_id` explícito por query param.
- Los 21 casos "MUST change" de la auditoría de `docs/USUARIOS_MULTI.md`
  (Paso 5) ya están resueltos en los Pasos 1-4 de esa fase.
- `unidad.py` usa `unidad_activa_o_403` (no `unidad_supervisada_o_403`)
  porque la configuración de turnos es una acción de la unidad activa del
  usuario, no exclusiva de supervisoras.
- Preguntas abiertas del plan de la Fase 13 (registro libre de unidades,
  abandono de unidad) siguen pendientes de confirmar.

## Mantenimiento reciente (independiente de la Fase 10 — supervisoras multiunidad)
Implementación de `PLAN_SUPERVISORAS_MULTIUNIDAD.md`: las supervisoras podrán
gestionar varias unidades (no solo la suya), vía tabla N:M `unidad_supervisada`
independiente de `Usuario.unidad_id`/`categoria_id`. 7 pasos con TDD y un
commit por paso.

## Historial completo
El registro detallado de fases y pasos anteriores está en
`PROGRESS_ARCHIVE.md`.
