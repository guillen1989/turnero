# Estado del desarrollo

## Fase actual
Publicación en Google Play Store (`docs/PLAN_PLAY_STORE.md`) — Fase 6
(pruebas cerradas) en curso; Fase 3 (aspectos legales) completa; Fase 2
(dominio) parcialmente completa.

## Paso actual / siguiente paso
Resuelta la incidencia crítica de nivel de API de destino de Google Play
(ver "Últimos pasos completados"): nuevo `.aab` con `targetSdkVersion 36`
subido a la pista cerrada. Siguiente paso: esperar la confirmación de
Google de que la app ya no está afectada, y seguir con lo pendiente de la
Fase 6 (mantener la pista cerrada activa 14 días con ≥12 testers). En
paralelo sigue pendiente Fase 2 (actualizar `APP_BASE_URL`/referencias de
URL de producción en el repo para usar `app.turnero.xyz`, y verificar que
`/manifest.json` y `/sw.js` se sirven correctamente desde ese dominio).

## Últimos pasos completados
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
- [x] Fase 3 completa: páginas públicas `/privacidad`, `/terminos` y
  `/eliminar-cuenta` (`app/routes/main.py` + `app/templates/main/`),
  enlazadas desde `base.html` y `auth/registro.html`, catálogo de
  traducción actualizado y tests en `tests/test_paginas_legales.py`. Detalle
  en `docs/PLAN_PLAY_STORE.md`.

## Notas / decisiones / asunciones pendientes
- Lighthouse v13 (la que instala `npx lighthouse` por defecto) ya no trae la
  categoría `pwa` — Google la retiró del core. Para repetir esta auditoría
  en el futuro hay que fijar una versión antigua, p. ej. `npx lighthouse@10`.

## Mantenimiento reciente (independiente de la Fase 10 — supervisoras multiunidad)
Implementación de `PLAN_SUPERVISORAS_MULTIUNIDAD.md`: las supervisoras podrán
gestionar varias unidades (no solo la suya), vía tabla N:M `unidad_supervisada`
independiente de `Usuario.unidad_id`/`categoria_id`. 7 pasos con TDD y un
commit por paso.

- [x] Paso 1 — Modelo: `UnidadSupervisada` (`app/models/unidad_supervisada.py`,
  PK compuesta `usuario_id`+`unidad_id`), relaciones
  `Usuario.unidades_supervisadas` / `Unidad.supervisoras`
  (`secondary="unidad_supervisada"`). Migración `666dde3fff3c` (generada con
  `flask db migrate`, un único head) crea la tabla y hace backfill (`INSERT
  ... SELECT id, unidad_id FROM usuario WHERE es_supervisora = true`) para las
  supervisoras ya existentes. Tests en `tests/test_models_unidad_supervisada.py`.
- [x] Paso 2 — Servicio `app/services/supervision.py`:
  `unidades_supervisadas_de(usuario)` (ordenadas por nombre) y
  `puede_supervisar(usuario, unidad)`. Tests en
  `tests/test_servicio_supervision.py`.
- [x] Paso 3 — Rutas `planilla_supervision.py`: `_unidad_supervisada_o_403(unidad_id)`
  sustituye a `_exigir_supervisora()`, usando `puede_supervisar`; sin
  `unidad_id`, resuelve a `current_user.unidad` si está entre las
  supervisadas (compatibilidad con supervisoras de una sola unidad) o si no
  a la primera de `unidades_supervisadas_de`. `unidad_id` se pasa como
  querystring en `index()`/`reglas()` (GET) y como campo oculto de formulario
  en `ajustar`/`turno_eliminar`/`turno_editar` (POST); los redirects a
  `index` y `reglas` lo propagan para volver a la unidad correcta. Plantilla
  `planilla_supervision/index.html` actualizada: nav de mes y los 2
  formularios ocultos llevan `unidad_id`; `reglas.html` también. Se
  actualizaron los 3 helpers de test que creaban supervisoras sin
  `UnidadSupervisada` asociada (`tests/test_rutas_planilla_supervision.py`,
  `tests/test_reglas_comprobacion.py`, `e2e/test_planilla_supervision.py`)
  para crear esa asociación automáticamente, y también
  `scripts/seed_staging.py` (afecta a `tests/test_seed_staging_uco.py`).
  Tests nuevos: acceso a 2 unidades por separado y 403 en una tercera no
  supervisada (`index` y `ajustar`), más 403 en `reglas`.
- [x] Paso 4 — Selector de unidad en `index.html` y `reglas.html`: un
  `<select>` junto al título (clase `planilla-select`, `onchange` navega con
  `window.location.href`), visible solo si `unidades_supervisadas` tiene más
  de un elemento (oculto para el caso legado de una sola unidad). Verificado
  con un test E2E nuevo (Playwright, `e2e/test_planilla_supervision.py::
  test_selector_de_unidad_cambia_los_trabajadores_mostrados`) que confirma
  que cambiar la opción del selector cambia los trabajadores mostrados en la
  matriz, en vez de una prueba manual en navegador.
- [x] Paso 5 — Formulario admin: asignar unidades supervisadas.
  `sincronizar_unidades_supervisadas(usuario, unidad_ids)` en
  `app/services/supervision.py` deja las filas `UnidadSupervisada` de un
  usuario exactamente en el conjunto pedido (añade las que faltan, borra
  las que sobran). `AdminUsuarioForm` gana un `SelectMultipleField`
  `unidades_supervisadas` ("Unidades adicionales que supervisa"; la propia
  unidad del usuario se añade siempre por unión de conjuntos, nunca hay
  que seleccionarla a mano). Nuevo helper `_choices_unidades()` en
  `app/routes/admin/helpers.py`. `usuario_nuevo()`/`usuario_editar()`
  llaman a `sincronizar_unidades_supervisadas(u, seleccionadas | {unidad.id})`
  si `es_supervisora` es `True` tras guardar, o con conjunto vacío si es
  `False` (limpia todas las filas). El GET de `usuario_editar()`
  precarga el multi-select con las unidades ya asociadas, excluyendo la
  propia. Plantilla `usuario_form.html`: el nuevo `<select multiple>` solo
  es visible si el checkbox "Supervisora" está marcado (JS, mismo patrón
  que el toggle ya existente de "categoría nueva"). 6 tests nuevos en
  `tests/test_servicio_supervision.py` (servicio) y `tests/test_admin.py`
  (crear supervisora con unidades extra, editar para añadir/quitar, y
  desmarcar "Supervisora" limpia todas las filas) — en este último, ojo:
  simular un checkbox desmarcado en WTForms requiere *omitir* la clave del
  POST, no enviarla con valor `False` (cualquier valor presente, incluida
  la cadena `"False"`, hace que `BooleanField` lo interprete como
  marcado).
- [x] Paso 6 — Contraseña por invitación para supervisoras creadas por el
  admin. Nueva `crear_supervisora_con_invitacion(usuario)` en
  `app/services/registro.py`: pone una contraseña aleatoria desconocida
  (`secrets.token_urlsafe(32)`), reutiliza `generar_token_reset` (sin
  cambios, ya era genérico) y `enviar_email` con la plantilla nueva
  `email/invitacion_supervisora.html` (copia de `recuperar_password.html`
  con texto de invitación), enlazando a la vista ya existente
  `auth.restablecer_password` (sin tocar). En `usuario_nuevo()`
  (`app/routes/admin/usuarios.py`): si `es_supervisora` es `True`, el
  campo contraseña deja de ser obligatorio y no se usa — se pone un valor
  aleatorio temporal antes del primer `flush()` (necesario por la columna
  `NOT NULL`) y, tras el `commit()` inicial, se llama a
  `crear_supervisora_con_invitacion(u)` (que vuelve a generar la
  contraseña real y envía el email). `usuario_editar()` no necesitó
  cambios: ya trataba la contraseña como opcional. Plantilla
  `usuario_form.html`: el campo contraseña se oculta con JS y se muestra
  en su lugar un aviso ("se enviará un email de invitación") cuando el
  checkbox "Supervisora" está marcado — mismo `<script>` que ya
  alternaba el selector de unidades del Paso 5. 3 tests nuevos en
  `tests/test_admin.py` (crea supervisora sin contraseña y envía
  invitación con enlace a `restablecer_password`; la contraseña generada
  no coincide con ningún valor conocido; crear un usuario normal sin
  contraseña sigue dando error de validación, sin tocar ese flujo).
- [x] Paso 7 — Limpieza y extensión a `planilla_import.py`. La búsqueda de
  `current_user.unidad` en contextos de supervisión encontró un hueco real
  fuera del alcance original de los Pasos 1-6: `app/routes/planilla_import.py`
  seguía usando `current_user.unidad`/`_exigir_supervisora()` sin soporte
  multiunidad. Ampliado a petición explícita ("fold it into this PR"):
  - Extraído `unidad_supervisada_o_403(usuario, unidad_id)` de
    `planilla_supervision.py` (helper local) a `app/services/supervision.py`
    (función de servicio compartida, ya probada con 6 tests nuevos en
    `tests/test_servicio_supervision.py`), siguiendo el precedente de
    `abort()` en la capa de servicios de
    `app/services/busquedas_guardadas.py::eliminar_busqueda`.
    `planilla_supervision.py` refactorizado para usarla (sin cambio de
    comportamiento, 79 tests verdes).
  - `planilla_import.py`: `index()`, `subir()`, `codigos()` aceptan
    `unidad_id` (querystring en GET, campo oculto en POST) vía
    `unidad_supervisada_o_403`; `vincular()` ya no necesita `unidad_id`
    porque el `MapeoTrabajadorPlanilla` fija la unidad — se valida con
    `puede_supervisar(current_user, mapeo.unidad)` en su lugar de
    `mapeo.unidad_id != current_user.unidad_id`.
  - Plantillas `planilla_import/index.html` y `codigos.html`: mismo
    `<select>` de unidad que `planilla_supervision` (visible solo si
    `unidades_supervisadas|length > 1`) y campo oculto `unidad_id` en los
    formularios de subir/configurar códigos.
  - 7 tests nuevos en `tests/test_rutas_importar_planilla.py` (segunda
    unidad supervisada funciona en `index`/`subir`/`codigos`/`vincular`,
    y 403 en unidad no supervisada); el helper `_setup` de ese archivo
    ahora añade `UnidadSupervisada` al crear una supervisora, igual que en
    `test_rutas_planilla_supervision.py`.
  - Test E2E nuevo para `planilla_import`: `e2e/test_planilla_import.py`
    (selector de unidad cambia los trabajadores pendientes mostrados).
- [x] Paso 8 (integración, no previsto en el plan original) — Feature flags
  (PR #32) mergeados después de los Pasos 1-7 protegían las rutas con
  `@requiere_feature` pero el conftest no activaba los flags, provocando
  404 en todos los tests de supervisión. Añadida `_activar_feature_flags_de_test()`
  en `clean_db` (conftest) que crea y activa los 3 flags existentes tras
  cada truncate. Ajustados los tests de feature flags (`test_feature_flag_*.py`)
  para usar `desactivar_global` en vez de `crear_flag` (los flags ya los
  crea el conftest). Activación también en `e2e/conftest.py::clean_e2e_db`.
  Suite completa pendiente de ejecutar por timeout; tests clave todos verdes.
- [x] Paso 9 — Test E2E del flujo completo descrito en el Paso 7 del plan:
  `e2e/test_supervisora_multiunidad_e2e.py` cubre (1) login fallido con
  contraseña trivial (la cuenta se creó con contraseña aleatoria),
  (2) generación de token y establecimiento de contraseña vía
  `auth/restablecer-password/<token>`, (3) login exitoso como supervisora,
  (4) selector de unidad funcional en `/planilla/supervision/` y
  `/planilla/importar/` (cambiar de UCI a Urgencias muestra distintos
  trabajadores). No ejecutado en este entorno (Playwright sin navegadores);
  validar con `pytest e2e/test_supervisora_multiunidad_e2e.py` al abrir el PR.
