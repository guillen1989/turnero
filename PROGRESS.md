# Estado del desarrollo

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

## Fixes puntuales sobre supervisoras multiunidad / importación de planilla
Tres bugs reportados tras el trabajo anterior, corregidos en una rama aparte
(`fix-supervisor-unidad-planilla`, worktree desde `staging`):

- [x] Descubribilidad del selector de unidad: el `<select class="planilla-select">`
  de `planilla_import/index.html`, `planilla_import/codigos.html`,
  `planilla_supervision/index.html` y `planilla_supervision/reglas.html` solo
  tenía `aria-label`, sin texto visible — nada indicaba que ahí se podía
  alternar de unidad. Añadida `<label for="planilla-select-unidad">{{ _('Unidad') }}:</label>`
  visible delante de cada selector (clase nueva `.planilla-select-label` en
  `main.css`).
- [x] `/auth/perfil` para supervisoras: antes permitían cambiar su propia
  unidad/hospital desde el formulario normal, lo cual no tiene sentido — solo
  deben poder alternar entre las unidades que un administrador les asignó
  para supervisar (`UnidadSupervisada`), nunca su unidad base. La ruta
  `perfil()` en `app/routes/auth.py` ahora comprueba `current_user.es_supervisora`
  antes de tocar `PerfilForm` y, si lo es, renderiza una plantilla nueva de
  solo lectura (`auth/perfil_supervisora.html`: hospital/unidad/categoría
  como texto, con nota explicando que el cambio de unidad supervisada se
  hace desde el selector de las pantallas de planilla) — así un POST
  manipulado tampoco puede cambiar la unidad, porque no se procesa. Tests en
  `tests/test_auth_routes.py`.
- [x] `/planilla/importar`: los trabajadores sin vincular se quedaban en
  pantalla para siempre. Añadida columna `descartado` (bool, `server_default
  'false'`, migración `576142da40ac`) a `MapeoTrabajadorPlanilla`.
  `trabajadores_sin_vincular()` excluye los descartados;
  `resolver_o_crear_trabajador()` reactiva (`descartado = False`) un
  trabajador si vuelve a aparecer en una importación posterior. Nueva ruta
  `POST /planilla/importar/descartar` (servicio
  `descartar_trabajadores(unidad, mapeo_ids)`) y checkboxes + "seleccionar
  todos" + botón "Dejar sin asignar" en `planilla_import/index.html` (usa
  `form="descartar-form"` para no anidar `<form>`). Tests en
  `tests/test_servicio_planilla_matching.py` (5 nuevos, todos verdes) y
  `tests/test_rutas_importar_planilla.py` (4 nuevos, verdes en aislado).

### Nota sobre flakiness de test pre-existente (no introducida por este trabajo)
`tests/test_rutas_importar_planilla.py` falla de forma no determinista
cuando se ejecuta el archivo completo (`ObjectDeletedError`/`IntegrityError`
en objetos como `Categoria`/`Usuario`), incluso en el archivo **original sin
modificar** (verificado con una copia temporal de `git show HEAD:...`) y con
orden de tests fijo (`-p no:randomly`). Cada test pasa de forma fiable en
aislado. No se identificó la causa raíz exacta (se investigó
`clean_db`/`_activar_feature_flags_de_test` en `conftest.py` y se descartó
paralelismo externo — no hay procesos `pytest`/`xdist` concurrentes contra
la misma BD). Queda como deuda de infraestructura de test a investigar
aparte; no bloquea estos tres fixes.

## Fixes de creación/eliminación de usuarios (rama `fix-user-creation-bugs`)
Cuatro bugs reportados sobre la gestión de usuarios desde el panel admin,
corregidos en un worktree aparte desde `staging`:

- [x] Contraseña por invitación para **todos** los usuarios nuevos, no solo
  supervisoras. `crear_supervisora_con_invitacion` (Paso 6, arriba) se
  generaliza a `crear_usuario_con_invitacion(usuario)` en
  `app/services/registro.py` y se llama siempre desde `usuario_nuevo()`
  (`app/routes/admin/usuarios.py`), sin condicionarla a `es_supervisora`.
  El formulario ya nunca acepta una contraseña en la creación: se genera
  con `secrets.token_urlsafe(32)` y se sobreescribe otra vez dentro de
  `crear_usuario_con_invitacion` antes de enviar el email. Plantilla
  `usuario_form.html`: el bloque de contraseña se oculta con un `{% if
  es_creacion %}` (deja de depender del checkbox "Supervisora" por JS) y
  siempre muestra el aviso de invitación al crear. Email genérico:
  `email/invitacion_supervisora.html` renombrada a
  `email/invitacion_usuario.html`, con texto neutro ("Se ha creado tu
  cuenta") en vez de específico de supervisoras.
- [x] Email duplicado al crear usuario causaba 500 (constraint UNIQUE de
  BD sin validar antes). Añadida comprobación explícita en
  `usuario_nuevo()` (`Usuario.query.filter_by(email=email).first()`) y en
  `usuario_editar()` (misma comprobación, excluyendo el propio id:
  `Usuario.id != u.id`) que añaden un `flash` de error y re-renderizan el
  formulario en vez de dejar que el `INSERT`/`UPDATE` falle.
- [x] Eliminar una supervisora daba 500: `eliminar_usuario_admin()` no
  cubría todas las dependencias FK que solo existen para supervisoras
  (p. ej. filas de `DocumentoCambio` con `creado_por_id`/`supervisora_id`/
  `anulado_por_id` apuntando a ella, `AjustePlanillaSupervisora.realizado_por_id`,
  o `MapeoTrabajadorPlanilla.usuario_id`). Ampliado el borrado en cascada de
  `app/services/registro.py::eliminar_usuario_admin` para nulificar o
  borrar (según la FK) cada una de esas tablas antes de borrar el usuario,
  incluyendo el caso de documentos que ella creó (se borran enteros, junto
  con sus participantes/firmas de otros usuarios).
- [x] Email de invitación no llegaba en Railway staging: no requería
  cambio de código aparte — al generalizar la invitación (punto 1) a
  todos los usuarios nuevos, el envío pasa siempre por
  `app/services/email.py` (Resend vía HTTPS, ya usado por supervisoras),
  que ya funciona en staging.

Los 4 fixes viven en los mismos archivos (`usuarios.py`, `registro.py`,
`usuario_form.html`, plantilla de email renombrada) y se han probado
juntos; suite completa verde sin regresiones (`pytest -p no:testmon`).

## Junte de noches en la hoja de cambio digital (worktree `feature/junte-frames-pdf`)
Primer paso de una iniciativa mayor: que `documento_cambio/pdf.html` también
sirva para juntes de noches (hasta ahora esas dos rejillas L-M-X-J-V-S-D del
impreso se renderizaban en blanco/estáticas, ver Fase 10). Este paso es solo
el layout — añade los `@frame` necesarios, sin tocar el modelo de datos:
- 18 `@frame` nuevos, coordenadas medidas sobre `hoja-cambio-fondo.png`
  (905x1280px @ A4, 0.232mm/px): 4 para los nombres (fila "3 noches"/"4
  noches" x tablas "CORRESPONDE A"/"CAMBIO") y 14 para las 7 columnas de
  día (L-D) x 2 filas de la tabla "CAMBIO" (la tabla "CORRESPONDE A" ya trae
  esas marcas impresas en el fondo).
- Contenido condicionado a un flag nuevo `mostrar_junte` (mismo patrón que
  el bloque de decisión de la supervisora), para no afectar a los documentos
  de tipo `cambio`/`cambio_dia` ya existentes.
- Las filas de la tabla "CAMBIO" son las más ajustadas (~6.15-6.27mm, ver
  advertencia sobre el mínimo de 6mm en el comentario del propio
  `pdf.html`) — cubierto con un test de regresión que renderiza el PDF real
  y comprueba que las 7 marcas de cada fila no se descartan en silencio.
- Tests nuevos en `tests/test_pdf_junte_frames.py`: renderizan la plantilla
  directamente (no vía `generar_pdf_documento`) porque `DocumentoCambio`
  todavía no admite juntes (`match_admite_documento_cambio` los excluye
  explícitamente, y `ParticipanteDocumentoCambio` solo modela un
  cede/recibe, no un patrón semanal).

## Siguiente paso
Para el hilo de junte de noches: decidir y construir el modelo de datos
(¿nuevo tipo de `DocumentoCambio` o una entidad aparte?) que alimente estos
frames a partir de una publicación `junte` ya emparejada, y enganchar
`generar_pdf_documento` (o un servicio equivalente) para pasarle
`mostrar_junte=True` y los datos reales. Ninguno pendiente para los 4 fixes
de creación/eliminación de usuarios de la sección anterior — ya en PR contra
`staging`. Si se retoma ese hilo, investigar la flakiness de
`tests/test_rutas_importar_planilla.py` descrita arriba (deuda de
infraestructura de test preexistente, no introducida por ese trabajo).
