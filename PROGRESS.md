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
- Multi-unidad (Fase 16): Paso 5 completado. Siguiente: Paso 6 de
  `docs/FEAT_FLAG_MULTI.md` — Notificaciones y Web Push: etiquetas de
  unidad.
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
- [x] test: la suite se ejecuta en paralelo en CI (`pytest -n auto`). El
  aislamiento de BD por checkout (`tests/conftest.py`) ahora también aísla
  por worker de xdist (sufijo `PYTEST_XDIST_WORKER` en el nombre de la BD),
  para que los `TRUNCATE`/`create_all` concurrentes de distintos workers no
  se pisen entre sí. `pytest-xdist==3.6.1` añadido a `requirements.txt`.
  Validado localmente: suite completa (~1600 tests) en verde con `-n 4`.
- [x] feat: el asistente de parseo de WhatsApp queda empaquetado detrás de
  un flag `asistente_parser` (`activo_global=False` por defecto, migración
  `d836f60ead28`), en preparación para su promoción a producción de forma
  controlada. Rutas `/asistente/parsear` y `/asistente/consejos` decoradas
  con `@requiere_feature`; CTA del dashboard y botón+modal de
  `publicar.html` ocultos con `{% if asistente_activo %}`; JS del modal
  guardado con `if (modalAsistente && btnAbrirAsistente)` para no fallar si
  el flag está desactivado. Tests en `test_asistente_route.py`,
  `test_publicar.py` y `test_dashboard.py` (2 tests cada uno: flag
  activo/desactivado). Flag añadido a las listas de activación de
  `tests/conftest.py` y `e2e/conftest.py`. Suite completa en verde tras
  aplicar el cambio en paralelo con `-n auto` (ver paso anterior).
- [x] fix: el asistente ya infiere el mes cuando un turno solo trae el día
  (p. ej. "T24"/"T28" sin mes en ningún punto del mensaje) — regla añadida
  al prompt de `_construir_prompt`: mes en curso, o el siguiente si ese día
  ya pasó respecto a "hoy". Confirmado con el corpus real
  (`~/desarrollo/turnero/mensajes_cambios`, 461 líneas) y logs de staging:
  la notación M/T/N+día ya funcionaba bien siempre que el mensaje mencionara
  el mes en algún punto; el caso sin mes en absoluto era el hueco. Probado
  en vivo contra la API de Groq (varios "hoy" distintos, incluido fin de
  mes). De paso, la prueba destapó un bug latente: un `cedidos` con
  `franja: None` (posible desde el fix anterior de `fecha: null`, antes
  quedaba oculto porque la propuesta ya fallaba en `fecha`) crasheaba
  `resolver_propuesta` con `AttributeError` en `_normalizar(None)`; ahora
  se trata como problema puntual ("Falta la franja de un turno") igual que
  una franja desconocida. Test en `test_asistente_resolver.py`.
- [x] fix: el parser del asistente de WhatsApp lanzaba `ErrorAsistente`
  (descartando toda la propuesta) cuando el modelo devolvía `fecha: null`
  en un turno por no tener datos suficientes (p. ej. "Cambio T24 por T28
  porfi", sin fecha). `TurnoPropuesto.fecha` ahora acepta `None`;
  `resolver_propuesta` trata un turno sin fecha como un problema de ese
  turno concreto (mensaje "Falta la fecha de un turno") sin descartar el
  resto de la propuesta, igual que ya hacía con franjas desconocidas.
  Tests en `test_asistente_schema.py` y `test_asistente_resolver.py`.
- [x] fix: elimina el problema N+1 de commits en las rutas batch de
  planilla (`rango/aplicar`, `multiples/aplicar`, `vacios/aplicar`), que
  hacían un `db.session.commit()` por cada día procesado. `añadir_turno` y
  `establecer_estado_dia` aceptan ahora `commit=False`; cada ruta hace un
  único commit al final y `rollback()` con mensaje de error si falla a
  mitad de lote (todo-o-nada). Tests en `test_planilla_relleno.py` (5
  tests: un solo commit por ruta, regresión de un día, atomicidad ante
  fallo simulado).
- [x] fix: al confirmar/rechazar/desconfirmar un match desde el dashboard,
  la redirección conserva el filtro de estado activo (`?estado=...`) en vez
  de volver siempre a la vista por defecto. Nuevo campo oculto
  `redirect_estado` en los formularios y helper `_redirect_a_dashboard()`
  en `app/routes/matches.py`. Tests en `test_confirmacion.py` (3 tests:
  confirmar/rechazar/desconfirmar con estado preservado).
- [x] feat: sistema de eliminación (uno a uno y Eliminar todos) en la pestaña
  Confirmados de Mis cambios publicados, replicando el mismo sistema ya
  existente en Caducados. Nueva ruta `POST /publicaciones/eliminar-confirmadas`,
  modal de confirmación y botones en el dashboard. Fix: `DocumentoCambio.match_id`
  se desvincula (->NULL) al borrar matches huérfanos para evitar violación de FK.
  Tests en `test_editar_eliminar_publicacion.py` (3 tests: login requerido,
  borrado masivo con aislamiento, FK DocumentoCambio) y `test_dashboard.py`
  (2 tests: presencia/ausencia de botones).
- [x] Fix urgente (main → staging): `unidad_activa_o_403` ya no aborta con
  403 cuando el `unidad_id` obsoleto viene solo de la sesión (p. ej. tras
  un cambio de unidad del usuario); limpia la sesión y cae a la unidad
  principal. Test en `test_servicio_unidad_usuario.py`.
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
- **MEDIDA TEMPORAL (2026-08-27):** el límite diario de usos del asistente
  de WhatsApp (`LIMITE_PARSEOS_DIA` = 20 en `app/routes/asistente.py`) está
  desactivado (`LIMITE_PARSEOS_DIA_ACTIVO = False`) mientras se prueba en
  staging con mensajes reales. Reactivar antes de promocionar el asistente
  a producción de forma permanente.
- **2026-08-28:** el motor del asistente de parseo de WhatsApp cambió de
  Anthropic (Claude Haiku 4.5) a Groq — más barato y más rápido. La lógica
  de Anthropic se conserva desactivada (sin invocarse) en
  `app/services/asistente/cliente.py::_extraer_propuesta_anthropic`, por si
  se recupera más adelante. Requiere `GROQ_API_KEY` en el entorno (ver
  `.env.example`); `ANTHROPIC_API_KEY` deja de ser necesaria mientras el
  motor de Anthropic esté desactivado. Detalle en `docs/crear_parser.md`
  (vive en el repo `turnero`, rama `main`, fuera de este worktree).
  Modelo inicial `llama-3.1-8b-instant` falló en el primer test real en
  staging (404 model_not_found: Groq lo pasó a nivel Enterprise en su ola de
  deprecaciones de junio 2026). Probado `llama-3.3-70b-versatile` (también
  Enterprise, sin confirmar en staging) y finalmente fijado a
  `openai/gpt-oss-120b` — el modelo de mayor capacidad que sigue disponible
  en el tier free/dev — pendiente de confirmar en staging con mensajes
  reales.

## Mantenimiento reciente (independiente de la Fase 10 — supervisoras multiunidad)
Implementación de `PLAN_SUPERVISORAS_MULTIUNIDAD.md`: las supervisoras podrán
gestionar varias unidades (no solo la suya), vía tabla N:M `unidad_supervisada`
independiente de `Usuario.unidad_id`/`categoria_id`. 7 pasos con TDD y un
commit por paso.

## Historial completo
El registro detallado de fases y pasos anteriores está en
`PROGRESS_ARCHIVE.md`.
