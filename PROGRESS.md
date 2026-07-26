# Estado del desarrollo

## Mantenimiento reciente (independiente de la Fase 10 — infraestructura de feature flags)
Implementación de `docs/FEATURE_FLAGS.md`, Fase A (infraestructura agnóstica de
features concretas), en worktree/branch `feature/feature-flags` desde
`origin/staging`. PR de esta fase va contra `staging`, no contra `main`.
- [x] Paso 1 — Modelo `FeatureFlag` (`clave` única, `descripcion`,
  `activo_global` con default `False`) + tests
  (`tests/test_models_feature_flag.py`).
- [x] Paso 2 — Modelo `FeatureFlagUnidad` (N:M flag↔unidad, mismo patrón que
  `UnidadSupervisada`) + relación `FeatureFlag.unidades_habilitadas` /
  backref `Unidad.feature_flags_habilitados` + tests
  (`tests/test_models_feature_flag_unidad.py`).
- [x] Paso 3 — Migración Alembic `7be3ca3f48b9` (tablas nuevas, sin filas
  previas → un solo paso, sin el patrón de tres pasos de `NOT NULL`).
  `flask db heads` da un único head.
- [x] Paso 4 — Servicio `app/services/feature_flags.py` (`feature_activa` +
  `crear_flag`/`activar_global`/`desactivar_global`/`habilitar_para_unidad`/
  `deshabilitar_para_unidad`) + tests (`tests/test_servicio_feature_flags.py`,
  cubre flag inexistente → False, activo_global gana aunque la unidad no
  esté en la lista, unidad en la lista gana aunque activo_global sea False).
- [ ] Paso 5 — Decorador `requiere_feature` + context processor Jinja
  `feature_activa`.
- [ ] Paso 6 — UI admin `/admin/feature-flags`.

La Fase B (aplicar flags a funcionalidades concretas de `staging`) requiere
decisión explícita del usuario sobre qué ocultar, y se aborda en PR(s)
separados posteriores — no se mezcla con este.

## Mantenimiento reciente (independiente de la Fase 10 — ahorro de tokens en sesiones de Claude Code)
PR contra `staging` con 3 cambios para reducir el gasto de tokens de las sesiones
de Claude Code (el gasto se había disparado con el tamaño del proyecto):
- [x] `app/routes/admin.py` (1194 líneas, 38 rutas) dividido en el paquete
  `app/routes/admin/` (10 módulos por dominio: `vista_general`, `usuarios`,
  `geografia`, `publicaciones`, `feedback`, `demo`, `franjas`, `analytics`,
  más `__init__.py` con `bp`/`admin_required` y `helpers.py` con los
  `_choices_*` compartidos). Mismos 38 endpoints (`url_for("admin.xxx")` sin
  cambios), verificado con `test_admin.py` + `test_admin_analytics.py` (47
  tests) y conteo de rutas registradas.
- [x] `tests/test_rutas_documento_cambio.py` (1942 líneas, 85 tests) dividido
  en 8 archivos por escenario (`test_documento_cambio_{creacion,firma,lista,
  registro_papel,supervision,anular,bloque,encadenadas}.py`) + un módulo
  nuevo `tests/helpers_documento_cambio.py` con los helpers/constantes
  compartidos (`_setup`, `_login`, `_FIRMA_PNG`, `_crear_documento_completo`,
  etc.). Los 85 tests siguen pasando.
- [x] `AGENTS.md` (casi duplicado de `CLAUDE.md`, ya divergente) reducido a un
  stub que remite a `CLAUDE.md` como única fuente, para no volver a mantener
  las convenciones dos veces.
- [x] Reforzada en `CLAUDE.md` la recomendación de usar `pytest --testmon` en
  vez de la suite completa en el día a día.

Nota para la próxima sesión: al dividir `app/routes/admin.py`, el primer
intento de split olvidó el import de `request` en `geografia.py`; al dividir
el test file, dos archivos nuevos olvidaron importar `_mes_actual_y_siguiente`/
`_crear_documento_completo` de `helpers_documento_cambio.py` — el `NameError`
resultante dejaba una transacción a medias que causaba deadlocks en tests
posteriores (parecía contención de la BD de test, pero era un import que
faltaba). Verificar con `pyflakes` tras cualquier split de este tipo antes de
fiarte de los resultados de tests que fallan con errores de BD poco claros.

## Mantenimiento reciente (independiente de la Fase 10 — limpieza de sintéticas huérfanas)
PR contra `staging` con 2 cambios detectados al analizar el fan-out combinatorio
del motor de matching en producción:
- [x] `app/services/caducidad.py`: las publicaciones sintéticas (`es_sintetica`)
  cuyo padre A o B deja de estar activo se **eliminan** en vez de solo marcarse
  `cancelada`. Antes se acumulaban sin límite (en producción llegaron a ser el
  70% de la tabla `publicacion_cambio`). El borrado respeta el orden de FKs
  (`MatchParticipacion` → `MatchCambio`/`Notificacion` huérfanos →
  `Notificacion`/`TurnoCedido`/`TurnoAceptado` → `PublicacionCambio`).
- [x] `app/routes/admin/analytics.py`: los contadores `oportunidades_3` y
  `oportunidades_4` (vista `/admin/analytics` y endpoint `/analytics/data`, con
  y sin filtro por unidad) no filtraban por `estado`, así que las sintéticas
  ya `cancelada`/`caducada` inflaban el conteo de oportunidades reales.

Pendiente, fuera de alcance de este PR (anotado, no implementado):
- El fan-out combinatorio en sí (`buscar_cadenas_parciales_4_para` /
  `buscar_avisos_interes_para` generan todas las combinaciones sin límite) no
  se ha limitado con un top-K; queda documentado como mejora futura.
- `cancelar_publicacion`/`editar_publicacion` (vía `_cancelar_sinteticas_de`
  en `app/services/publicaciones.py`) tienen el mismo defecto de origen
  (cancelan sintéticas sin borrarlas) pero no se tocaron en este PR para no
  ampliar su alcance.

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
- [ ] Paso 7 — Limpieza y prueba manual end-to-end.

## Fase actual
Fase 10 — Hoja de cambios digital (documento de cambio con firma)

## Paso actual / siguiente paso
perf(publicaciones): eliminar una publicación con sintéticas dependientes
tardaba ~10s en producción y provocaba un `WORKER TIMEOUT` de gunicorn —
`_eliminar_sinteticas_de`/`_eliminar_matches_de_publicacion` hacían una
tanda de consultas/deletes por cada sintética en un bucle Python (hasta
225 sintéticas dependientes vistas en producción para una sola
publicación real). Reescrito a deletes/updates en bloque
(`.filter(...).delete(synchronize_session=False)` /
`.update(..., synchronize_session=False)`) que operan sobre la lista
completa de ids de una vez: `_eliminar_matches_de_publicacion` ahora
delega en la nueva `_eliminar_matches_de_publicaciones` (acepta una lista
de ids), y `_eliminar_sinteticas_de` calcula todos los `sint_ids` con una
sola query y borra notificaciones/turnos/publicaciones sintéticas con 4
deletes en bloque en vez de 4×N. Como las FK de `TurnoCedido`/
`TurnoAceptado` → `publicacion_cambio` no tienen `ondelete=CASCADE` a
nivel de BD (el `cascade="all, delete-orphan"` del modelo es solo de ORM
y no actúa en deletes en bloque), el orden de borrado sigue siendo
explícito: participaciones/matches → notificaciones → turnos →
publicaciones. 2 tests nuevos en `tests/test_editar_eliminar_publicacion.py`:
uno de integración (elimina una pub con 5 sintéticas dependientes vía
HTTP y verifica que todas —y sus turnos— desaparecen) y uno de regresión
de rendimiento con el fixture `query_counter` ya existente (comprueba que
el nº de SELECTs al eliminar una publicación con 5 sintéticas es igual
que con 1, no proporcional a N) para detectar si el problema vuelve a
aparecer.

Siguiente: investigar (sin implementar todavía, a la espera de que el
usuario decida) una mejora en el motor de matching (`app/matching/service.py`)
para acotar el crecimiento sin límite de publicaciones sintéticas por
cadena_3/cadena_4 — la causa de fondo de las 225 sintéticas por
publicación real vistas en producción, que es lo que hacía tan doloroso
el N+1 ahora corregido, y que seguirá generando volumen creciente en la
BD y en el dashboard aunque el borrado ya no sea lento.

## Paso anterior
perf(db): `publicacion_cambio`, `usuario` y `unidad` no tenían más índice
que la PK (`\d publicacion_cambio` en producción lo confirmó), pese a que
`usuario_id`, `estado`, `es_sintetica` y `tipo` de `publicacion_cambio`,
`categoria_id` de `usuario` y `grupo_intercambio_id` de `unidad` son
justo las columnas que filtran todas las búsquedas del motor de matching
y el dashboard. Cuarto y último paso del plan de 4 para resolver los
cuelgues de producción (ver pasos anteriores). Fix: `index=True` en esas
6 columnas (`app/models/publicacion.py`, `app/models/usuario.py`,
`app/models/unidad.py`) y migración generada con `flask db migrate`
(nunca a mano) — `285a7610df2f_añade_índices_para_filtros_de_matching.py`,
`flask db heads` da un único head. Solo crea índices (`create_index`),
no toca datos ni columnas existentes, así que no aplica el patrón de 3
pasos de `NOT NULL`. Aplicada y verificada en local (`flask db upgrade`)
· 890 tests passing.

Con esto quedan completados los 4 pasos del plan. Pendiente de que el
usuario decida cuándo hacer push/deploy a producción (ninguno de los 4
commits se ha empujado todavía) y, tras el deploy, verificar en
`railway logs` que: (a) arrancan 3 workers de gunicorn, (b) `flask db
upgrade` aplica la migración de índices sin errores, y (c) no vuelven a
aparecer `WORKER TIMEOUT` en los días siguientes.

## Paso anterior
chore(deploy): `Procfile` pasa de `gunicorn run:app` (default: 1 worker
síncrono, sin `-w`) a `gunicorn --workers 3 --timeout 60 run:app`. Tercer
paso del plan de 4 para resolver los cuelgues de producción (ver pasos
anteriores): con 1 solo worker, cualquier request lento (el motor de
matching en el grupo de intercambio más activo, u otra cosa en el
futuro) congelaba la app entera para todos los usuarios, no solo para
quien la disparó — es la causa de que los 3 `WORKER TIMEOUT` de gunicorn
vistos en producción (2026-07-14/15) se sintieran como "toda la app va
lenta" en vez de "una acción en concreto tardó". Con 3 workers, ese mismo
request lento deja de bloquear al resto. 60s de timeout (antes 30s,
default de gunicorn) da margen mientras los pasos 1 y 2 ya aplicados
reducen el tiempo real. 3 workers es un valor conservador para el plan
de Railway actual; si tras el deploy aparece presión de memoria
(reinicios por OOM en los logs, no `WORKER TIMEOUT`), habría que subir de
plan antes de subir el nº de workers.

Pendiente: **no se ha desplegado ni empujado (push) todavía** — el commit
queda listo en local (rama `staging`) a la espera de que el usuario
confirme el push/deploy. La verificación de este paso (confirmar en
`railway logs` que arrancan 3 workers y que `/health` sigue respondiendo)
solo se puede hacer después de ese deploy.

## Paso anterior
perf(matching): las 5 búsquedas de matching que se lanzan en cada
publish/editar/contraoferta (`buscar_matches_para`, `buscar_cadenas_3_para`,
`buscar_cadenas_4_para`, `buscar_cadenas_parciales_4_para`,
`buscar_avisos_interes_para`, en `app/matching/service.py`) repetían cada
una su propia llamada a `_candidatas_base` (misma consulta + 2
`selectinload`) en vez de compartir un único cálculo — 5x consultas
redundantes por request. Segundo paso del plan de 4 para resolver los
cuelgues de producción (ver paso anterior). Fix: nueva función pública
`candidatas_activas_para(publicacion)` (antes lógica repetida al principio
de cada búsqueda) y parámetro opcional `candidatas=None` en las 5
funciones — si se pasa ya calculado se reutiliza, si no se calcula como
antes (así los tests unitarios existentes, que llaman con un solo
argumento, siguen funcionando sin cambios). Las 3 rutas que hacían este
patrón (`nueva`, `editar` y `contraoferta` en `app/routes/publicaciones.py`)
calculan ahora `candidatas` una vez y la pasan a las 5 búsquedas.
`buscar_sinteticas_que_coinciden_con` queda fuera: consulta sintéticas,
no candidatas normales. Nuevo test de regresión
(`test_publicar_calcula_candidatas_una_sola_vez` en
`test_integracion_matching.py`) que espía `_candidatas_base` con
`unittest.mock.patch.object(..., wraps=...)` y comprueba `call_count == 1`
tras un publish real vía el cliente HTTP — confirmado en rojo sin el fix
(5 llamadas) y en verde con el fix aplicado · 890 tests passing.

Quedan 2 pasos del plan: 3) gunicorn con varios workers en el `Procfile`
(red de seguridad de infraestructura: que un request lento no bloquee
toda la app, ya que solo hay 1 worker síncrono hoy) y 4) añadir los
índices que faltan en `publicacion_cambio`/`usuario`/`unidad` (hoy solo
tienen la PK).

## Paso anterior
perf(busquedas): corregido un N+1 en `notificar_busquedas_guardadas`
(`app/services/busquedas_guardadas.py`) — por cada `BusquedaGuardada`
candidata que coincidía con una publicación nueva, se hacía un
`db.session.get(Usuario, busqueda.usuario_id)` dentro del bucle, en vez
de reutilizar el `Usuario` que la propia consulta ya traía por el `join`.
Detectado investigando por qué la app en producción se ha vuelto notable
mente más lenta en los últimos días (a petición del usuario, sin ninguna
sospecha previa de dónde estaba el problema): los logs de Railway
mostraban 3 `WORKER TIMEOUT` de gunicorn en 48h (2026-07-14 12:23,
2026-07-15 00:29, 2026-07-15 14:16), y el stack trace del worker matado
apuntaba siempre a este mismo punto — `notificar_busquedas_guardadas`
llamada desde `crear_pub_sintetica`, que a su vez se llama hasta 13 veces
en un solo publish/editar en el grupo de intercambio más activo
(categoría 2 / grupo 5: 89 publicaciones "cambio" activas ahora mismo).
Como no hay más de 1 worker de gunicorn (`Procfile` sin `-w`), cada
timeout congelaba la app entera para todos los usuarios, no solo para
quien publicaba. Fix: `contains_eager(BusquedaGuardada.usuario)` en la
query de candidatas (ya hace `join` con `Usuario`) y uso directo de
`busqueda.usuario` en vez del `get()` redundante. Nuevo test
(`test_notificar_busquedas_guardadas_no_crece_con_n`) que cuenta
`SELECT`s ejecutados (nuevo fixture `query_counter` en `conftest.py`,
basado en el evento `after_cursor_execute` de SQLAlchemy) y comprueba que
no crecen con el número de búsquedas guardadas coincidentes — usando
usuarios *distintos* por búsqueda, ya que con el mismo usuario repetido
el identity map de SQLAlchemy habría ocultado el bug. Confirmado en rojo
sin el fix (12 selects con 5 búsquedas vs 8 con 1) y en verde con el fix
aplicado (igual en ambos casos) · 889 tests passing.

Este es el primer paso de un plan de 4 para resolver los cuelgues de
producción (ver `/home/portatil/.claude/plans/dreamy-noodling-glacier.md`
si sigue disponible, o pedir al usuario que lo recuerde): 2) reutilizar
`_candidatas_base` entre las 6 búsquedas de matching que se lanzan en
cada publish/editar (hoy se repite la misma consulta 6 veces), 3) gunicorn
con varios workers en el `Procfile` (red de seguridad de infraestructura:
que un request lento no bloquee toda la app), 4) añadir los índices que
faltan en `publicacion_cambio`/`usuario`/`unidad` (hoy solo tienen la PK).
Worktree `turnos-factibles-y-causas` (rama
`worktree-turnos-factibles-y-causas`, creada desde `origin/staging` en
`dfc0557`, que ya incluye el PR #21 mergeado -- ver más abajo). Motivado por
tres peticiones del usuario tras usar la app en producción:

a. Los desplegables de turno en `/documentos-cambio/nuevo` y
   `/documentos-cambio/registrar-papel` listan todas las `FranjaHoraria` del
   grupo, aunque el trabajador elegido no curre ese turno ese día concreto --
   deberían filtrarse por lo que el usuario realmente tiene asignado en la
   planilla ese día.
b. `comprobar_factibilidad` (`app/services/factibilidad_documento_cambio.py`)
   devuelve `no_factible` sin decir *por qué* (corta en el primer fallo que
   encuentra) -- la supervisora necesita ver el motivo concreto (no trabaja
   ese turno / no está libre / rompe el límite de días consecutivos / rompe
   el descanso nocturno) para cada participante.
c. "Hojas de cambio encadenadas": permitir registrar una hoja que depende de
   otra hoja todavía pendiente de autorizar, sin que salga `no_factible`
   solo porque los efectos de la primera aún no están volcados a la
   planilla real.

Van en **dos PRs separados** porque (c) es bastante más grande y arriesgado
que (a)+(b).

- **PR 1 (mergeado como PR #23): Bloque A + Bloque B.**
  - [x] Bloque A — Filtrado de `<select>` de turno por planilla real: HECHO.
  - [x] Bloque B — Motivos de no factibilidad: HECHO.
- [x] Bloque C — Hojas de cambio encadenadas: HECHO.
  - [x] Modelo: columna `DocumentoCambio.depende_de_id` (FK self-referential nullable) + relación `depende_de`.
  - [x] Migración: `0de75e74af26` (un solo paso, nullable sin backfill).
  - [x] Servicio de overlay: `_construir_overlay()` recorre la cadena de predecesores pendientes y construye conjuntos `added`/`removed` de turnos. Funciones de factibilidad (`_trabaja_turno`, `_libre_para_turno`, `_trabaja_el_dia`, `_contar_dias_consecutivos_trabajados`, `_viola_limite_dias_consecutivos`, `_viola_descanso_nocturno`) aceptan parámetro `overlay` opcional; sin overlay, comportamiento idéntico al actual.
  - [x] Servicio de recálculo: `_recalcular_factibilidad_dependientes()` se llama desde `autorizar_documento`, `denegar_documento` y `anular_documento` para actualizar `factibilidad_estado`/`factibilidad_motivos` de todos los documentos que dependen del documento modificado.
  - [x] Rutas: `nueva()` y `registrar_papel()` aceptan `depende_de_id` del formulario y pasan `hojas_pendientes` a las plantillas. Nuevo helper `_hojas_pendientes_encadenables()`.
  - [x] UI: select opcional "Esta hoja depende de otra" en `nuevo.html` y `registrar_papel.html` listando hojas pendientes de la misma unidad. Badge "Encadenada a" en `ver.html` y `supervisora.html`.
  - [x] Tests: 13 nuevos (2 modelo + 4 overlay + 3 recálculo + 4 rutas), 143 pasando. 3 tests de PDF con fallo preexistente (incompatibilidad `openssl_md5` en Python 3.8, no relacionado con este cambio).
- [x] Style: intensificados los colores de la fila de números de día (`#94a3b8`) y de los botones solo-supervisora en la navbar (mayor opacidad amber).

- **PR 2 (completado en `staging`): Bloque C — hojas de cambio encadenadas.**
  Implementado tras mergear el PR 1. Diseño acordado con el usuario:
  - Los números de hoja (`DocumentoCambio.numero_unidad`) son relativos a
    `unidad_id` (`_siguiente_numero_unidad`, `UniqueConstraint("unidad_id",
    "numero_unidad", ...)`), **no** un identificador global -- el
    encadenado debe referenciar siempre por el `id` real (autoincrement,
    único de verdad), nunca por `numero_unidad`, para evitar ambigüedad
    entre unidades.
  - Nueva columna nullable `DocumentoCambio.depende_de_id` (FK
    self-referential a `DocumentoCambio.id`). Migración de un solo paso
    (nullable, sin backfill necesario -- no rompe el patrón de tres pasos
    porque no es `NOT NULL`).
  - UI en el alta de una hoja: select opcional "¿Esta hoja depende de otra
    hoja aún no autorizada?", listando las hojas pendientes de la misma
    `unidad_id` como p.ej. `"Hoja nº 12 (14/03) -- cedes noche a Ana,
    recibes tarde de Ana"` (el `value` del `<option>` es el `id` real;
    mostrar `numero_unidad` como texto es seguro porque la lista ya está
    acotada a una sola unidad).
  - Backend: construir un "overlay" del estado hipotético de la planilla
    (estado real + deltas de la cadena de documentos predecesores aún
    pendientes) y hacer que las funciones auxiliares de
    `factibilidad_documento_cambio.py` (`_trabaja_turno`,
    `_libre_para_turno`, `_trabaja_el_dia`,
    `_contar_dias_consecutivos_trabajados`) consulten ese overlay en vez de
    `TurnoPlanilla`/`EstadoDiaPlanilla` directamente -- sin cadena, el
    overlay es un no-op y el comportamiento actual no cambia (compatible
    hacia atrás).
  - Si se deniega/anula un predecesor, hay que recalcular la factibilidad
    de la hoja dependiente (puede volver a `no_factible`); una vez
    autorizado el predecesor (`volcar_documento_a_planillas` aplicado), la
    dependiente pasa a comprobarse contra el estado real directamente (deja
    de necesitar el overlay).

## Paso anterior
Rama `feature/planilla-supervision-highlights` (PR #22 mergeada): 4 mejoras
visuales de `/planilla/supervision` pedidas por el usuario.

Rama `fix/planilla-supervision-followups` (a partir de `staging`, ya con la
lista de 9 mejoras anterior mergeada). Lista de 8 seguimientos pedidos por el
usuario tras probar `/planilla/supervision` y `/documentos-cambio/supervisora`
en vivo:

### Detalle de la ronda anterior (8 seguimientos, ya mergeada en `staging`)
- [x] 1. Color propio (ámbar) para los botones solo-supervisora del nav, para
  distinguirlos de un vistazo de la fila de usuario normal de arriba
  (`.nav-supervisora-row a` en `main.css`).
- [x] 2. Los usuarios eliminados (`Usuario.eliminado`, nueva property que
  comprueba `password_hash == 'CUENTA_ELIMINADA'`) ya no aparecen en
  `/planilla/supervision` (filtrado en la ruta `index`).
- [x] 3. Bug real encontrado y corregido: el commit anterior (`e7df65d`) solo
  había verificado que "añadir turno extra sin sustituir" funcionaba en la
  planilla propia del trabajador (`/planilla/dia/añadir`), **no** en el editor
  de la supervisora. `ajustar_turno_trabajador` (servicio) siempre borraba
  todo el día antes de aplicar la selección; ahora acepta `sustituir: bool =
  True` y, si es `False` y hay `franja_id`, añade sin tocar lo que ya había.
  La ruta `/planilla/supervision/ajustar` acepta un nuevo campo de formulario
  `anadir_extra`; el modal de la plantilla añade un checkbox "Añadir turno
  extra" que solo se muestra cuando la selección es un turno concreto (no un
  estado ni "vaciar"). Tests de regresión a nivel de servicio y de ruta.
- [x] 4. El modal de "Modificar turno" de `/planilla/supervision` incluye
  ahora un enlace "📄 Registrar cambio manualmente (papel)" que lleva a
  `/documentos-cambio/registrar-papel` preseleccionando trabajador y fecha
  (`registrar_papel` acepta `usuario1_id`/`fecha` por query string en GET).
- [x] 5. Botón "Registrar cambio desde papel" con clase propia
  `.btn-registrar-papel` (ámbar, con emoji 📄) en vez de `btn-secondary`
  genérico, tanto en `/documentos-cambio/supervisora` como en el nuevo enlace
  del punto 4.
- [x] 6. `registrar_documento_cambio_papel` comprueba la factibilidad antes de
  aplicar el cambio: si sale `no_factible`, hace rollback, lanza
  `CambioNoFactibleError` (nueva excepción) y no crea ni aplica nada; la ruta
  `registrar_papel` la captura y muestra un aviso en vez de aplicar el
  cambio. `no_verificado` sigue dejando pasar (no hay planilla suficiente
  para *saber* que es inviable, distinto de saber que sí lo es).
- [x] 7. Las hojas de cambio (`DocumentoCambio`/`ParticipanteDocumentoCambio`)
  ya no dependen del nombre en vivo de `Usuario` para documentos completos:
  nuevo campo `nombre_congelado` (nullable, migración `fce42d5845ad`, sin
  backfill porque el proyecto todavía no ha llegado a producción) en
  `ParticipanteDocumentoCambio`, con la propiedad `nombre_mostrar` (=
  `nombre_congelado or usuario.nombre`). Se rellena en el momento de
  completarse el documento: en `registrar_documento_cambio_papel` (nace
  completo) y en `firmar_documento` cuando `todos_han_firmado()`. Plantillas
  (`ver.html`, `lista.html`, `supervisora.html`) y generación de PDF/notas
  ilog (`app/services/documento_cambio.py`) cambiadas a `nombre_mostrar`.
  `eliminar_cuenta()` no necesitó tocarse. Se muestra siempre el nombre
  congelado para documentos completos (no solo cuando la cuenta ya no
  existe), para que el PDF sea estable en el tiempo. Tests de regresión a
  nivel de modelo, servicio (firma digital y papel, incluyendo PDF) y ruta
  (`/documentos-cambio/supervisora` tras `eliminar_cuenta`).
- [x] 8. Confirmado el hueco real que sospechaba el usuario sobre
  `origen_papel` (commit `4d3636d3`): la columna sí se usaba en
  `documento_cambio/ver.html` y `supervisora.html`, pero **no** en
  `documento_cambio/lista.html` ("Mis hojas de cambio", la vista de cada
  trabajador) -- ahí no había ninguna insignia "Papel". Añadida + test de
  regresión.
- [x] 9. UX del modal "Modificar turno" de `/planilla/supervision`
  reordenado: el checkbox "Añadir turno extra" del punto 3 solo aparecía
  *después* de elegir el turno concreto, lo cual no era evidente para la
  supervisora al probarlo en vivo. Sustituido por un `radiogroup` de dos
  opciones ("Modificar turno del día" / "Añadir turno extra (doblaje)")
  que se muestra *antes* del desplegable de turno/estado; al elegir
  "añadir", se deshabilitan las opciones no aplicables ("Vaciar día" y el
  optgroup de estados especiales, que no tienen sentido en un doblaje).
  Sin cambios de backend (la ruta/servicio ya soportaban `sustituir=False`
  desde el punto 3). Cobertura nueva a nivel e2e con Playwright
  (`e2e/test_planilla_supervision.py`, 3 tests: orden visual del radio
  antes que el select, deshabilitado de estados especiales en modo
  "añadir", y que añadir un turno extra no borra el turno existente del
  día). 49 tests en verde (`test_rutas_planilla_supervision.py` +
  `test_servicio_planilla_supervision.py` + el nuevo fichero e2e).
- [x] 10. El radiogroup del punto 9 seguía sin ser evidente al usarlo en
  vivo (dos radios + un desplegable compartido para todo: turnos, estados
  y "vaciar" era demasiado indirecto). Rediseño a UI de filas con iconos:
  el modal ahora lista una fila por cada turno/estado ya asignado ese día,
  cada una con "✎" (modificar esa franja concreta por otra) y "−"
  (eliminarla, sin tocar el resto -- soporta doblajes); debajo, un botón
  "+ Añadir" muestra el formulario para dar de alta un turno o estado
  nuevo. El icono de papel del punto 4 se queda sin texto visible (solo el
  emoji) para que el modal sea más visual. Backend: dos rutas nuevas,
  `POST /planilla/supervision/turno/eliminar` y
  `POST /planilla/supervision/turno/editar`, más los servicios
  `eliminar_turno_trabajador`/`editar_turno_trabajador` (reutilizan
  `eliminar_turno`/`añadir_turno` de `app/services/planilla.py`) --
  `ajustar_turno_trabajador` y su ruta `/ajustar` se conservan para
  "añadir turno nuevo" / asignar estado / vaciar día. Regla de sustitución
  simplificada: elegir un turno en el "+" siempre añade (nunca vacía el
  día), elegir un estado especial o "vaciar" siempre sustituye todo el
  día -- ya no hace falta el checkbox/radio de modo. Los datos de cada
  celda (turnos + estado) se serializan a JSON en la ruta (`_turnos_a_json`,
  `_estado_a_json`) y se pintan en el modal por JS sin peticiones extra.
  Tests: cobertura completa a nivel de ruta para las dos rutas nuevas,
  test de ruta para los atributos JSON de la celda, y reescritura completa
  de `e2e/test_planilla_supervision.py` (5 tests Playwright: iconos
  editar/eliminar en la fila, eliminar quita solo esa franja, editar
  sustituye solo esa franja, añadir no pierde el turno existente, icono de
  papel sin texto). 68 tests en verde (`test_rutas_planilla_supervision.py`
  + `test_servicio_planilla_supervision.py` + `e2e/test_planilla_supervision.py`).

Todos los tests afectados en verde (incluidos los del punto 7, ya
implementado tras confirmación del usuario). PR #21 abierto en borrador
contra `staging`. Pendiente: mergear esta rama en `staging` y empujar a
`origin`.

## Backlog (fuente: .backlog)
- [x] B19: "Cambios a 4" — cadena de intercambio a 4 bandas (ciclos completos, sintéticas/avisos para huecos parciales, badges, preferencia de visualización en calendario) ✓
- [x] B18: Calendario visual — modo visor "Juntes de noches" (además de Ofertas/Peticiones) ✓
- [x] B0: Panel Notificaciones: toggle global push, prefs individuales (match/confirmación/total), suscripciones a compañeros ✓
- [x] B0b: «Me interesa» en Buscar cambios: match manual desde cualquier publicación ajena (Regalo/Petición/Junte/Cambio con modal de selección) ✓
- [x] B1: Mensaje opcional (≤200 chars) al publicar un cambio ✓
- [x] B2: Jerarquía hospital > categoría > servicio en desplegables ✓
- [x] B3: Botón de instalación de la PWA ✓
- [x] B4: Tipos de turno personalizados al publicar (nombre + horario) ✓
- [x] B5: Arreglar notificaciones push (CSRF + codificación VAPID) ✓
- [x] B6: Pestaña confirmados muestra nombre del compañero ✓
- [x] B7: Banner de instalación reaparece tras desinstalar la PWA ✓
- [x] B8: Publicar tipo 'regalo' (ofrecer turno sin recibir nada) ✓
- [x] B9: Publicar tipo 'petición' (librar turno sin ofrecer nada) ✓
- [x] B10: Ofrecer 'cualquier turno de un día' al publicar ✓
- [x] B11: Avisos por email con límite diario configurable ✓
- [x] B12: Notificación por email al admin cuando se recibe un feedback ✓
- [x] B13: Matching a 3 bandas (ciclo A→B→C→A) — motor puro + servicio + ruta + dashboard ✓
- [x] B14: Aviso de coincidencia parcial (cambio ↔ regalo / cambio ↔ petición) ✓
- [x] B15: Contraoferta — proponer términos personalizados sobre una publicación de tipo cambio ✓
- [x] B16: Invitar a un compañero — enlace WhatsApp + URL pre-rellenada ✓
- [x] B17: Fix push acumulativo — contador basado en Notificacion.leida, se resetea al visitar Compatibles ✓

## Historial completo
El registro detallado de pasos y fases anteriores (previo al último resumido arriba), y el checklist histórico completo de pasos completados, están en `PROGRESS_ARCHIVE.md`. No hace falta leerlo para reanudar el trabajo — solo consultarlo si se necesita el contexto de una decisión antigua.

## Notas / decisiones / asunciones pendientes
- Sin campo teléfono en ningún modelo ni formulario (decisión explícita del usuario).
- FranjaHoraria se define a nivel de GrupoDeIntercambio, no de Unidad individual.
- No se crea entidad Turno separada: fecha + franja_horaria_id se embeben directamente en turno_cedido y turno_aceptado.
- Autenticación: email + contraseña (Flask-Login + Werkzeug).
- El motor de matching se implementa como módulo puro sin acoplamiento a Flask ni SQLAlchemy.
- Los conflictos de pip (streamlit, spyder) son del sistema y no afectan al proyecto.
- conftest.py empuja un app context fresco por test para aislar g (Flask-Login) y la sesión SQLAlchemy. Necesario porque en Flask 3.x g está scoped al app context (no al request context) y Flask-Login cachea current_user en g._login_user.

### Hoja de cambios digital (Fase 10) — decisiones tomadas con el usuario
- Fase 1 explícitamente: sin cadenas a 3/4 bandas, sin juntes de noches, mono-cuenta (las dos firmas se hacen desde el mismo dispositivo/cuenta).
- Se genera el documento aunque no se haya comprobado factibilidad contra planillas (decisión consciente: el objetivo inmediato es tener un prototipo que enseñar a los jefes, no bloquear por falta de verificación). La comprobación de factibilidad es un paso posterior.
- Firma dibujada con el dedo (canvas) por decisión explícita del usuario para dar sensación de formalidad ante su supervisora, aunque no tenga valor legal reforzado — de ahí `hash_documento` en `FirmaDocumentoCambio` como rastro real por detrás del gesto visual.
- El documento generado debe ser visualmente lo más fiel posible a `hojacambios.png` (formulario real "SOLICITUD DE CAMBIO DE TURNO O GUARDIA" del Hospital Universitario La Paz, guardado en la raíz del repo).
- Las dos rejillas L-M-X-J-V-S-D del impreso son para juntes de noches (fuera de alcance ahora) — se renderizan en blanco/estáticas, sin datos.
- El bloque "INFORME POR PARTE DE LA SUPERVISORA" (Favorable/Desfavorable + firma) no se usa en la práctica según el usuario, pero se mantiene en el documento generado como bloque estático/en blanco, sin tercer firmante ni lógica funcional.
- Plantilla: HTML/Jinja2 + renderizado a PDF con WeasyPrint (no Word/LibreOffice), generado bajo demanda (no se persiste el PDF, evita el problema de disco efímero en Railway) — pendiente de implementar.
- `ESPECIFICACION.md` pendiente de actualizar (ver nota en el paso anterior): el principio "no deja constancia oficial... no es un documento de RRHH" queda desactualizado con esta funcionalidad.
- Bug preexistente encontrado en `app/templates/publicaciones/publicar.html` (no arreglado, fuera de alcance de esta fase): usa clases `alert`/`alert--{{cat}}` para los flash messages, que no existen en `main.css` (solo `flash`/`flash--*` están definidas), y además duplica el bloque `get_flashed_messages` que `base.html` ya renderiza globalmente — el mensaje sale dos veces, una con estilo y otra en texto plano sin caja. Las plantillas nuevas de `documento_cambio` no repiten el patrón. Pendiente decidir si merece su propio paso de limpieza.

- [x] fix(documento-cambio): la decisión de la supervisora (autorizar/denegar en `ver.html`) mostraba dos recuadros de firma duplicados, uno por cada `<form>` independiente (`autorizar-form`/`denegar-form`) · fusionados en un único `<form id="decision-form">` con un solo lienzo de firma y dos acciones vía `formaction` en los botones "Autorizar"/"Denegar" (y en sus respectivos "usar firma guardada") · el textarea de motivo pasa a ser común a ambas acciones (ya no `required` en HTML: el servidor ya validaba y redirigía con flash si faltaba, sin esa validación ninguna ruta se rompe) · `firma-canvas.js::initFirmaForm` generalizado para soportar varios botones `.firma-usar-guardada` en el mismo formulario (antes asumía uno solo) y estos pasan a ser botones `type="submit"` reales con `formaction` propio en vez de disparar `form.requestSubmit()`/`form.submit()` a mano (se simplifica el JS: el navegador ya respeta `formaction` al hacer clic) · mismo cambio aplicado al botón "Firmar con firma guardada" de la sección de firma del participante, por coherencia con el nuevo mecanismo · 1 test nuevo (`test_decision_supervisora_muestra_un_unico_recuadro_de_firma`) · 65 tests de `test_rutas_documento_cambio.py` + 90 de auth/dashboard passing

- [x] fix(documento-cambio): `comprobar_factibilidad` marcaba como `no_factible` cambios en papel legítimos cuando el día cedido caía dentro de la racha de días consecutivos (o era la noche anterior/siguiente) del día que ese mismo participante recibía en el mismo documento — detectado en staging al intentar registrar un cambio real (Ana García cede "Mañana" el 1/7 y recibe "Diurno 12h" el 4/7): su racha ya publicada llegaba a 12 días seguidos sin descontar el 1/7, por encima del límite de 8 del grupo, aunque ese día deja de ser suyo con el propio cambio · `_trabaja_el_dia`, `_contar_dias_consecutivos_trabajados`, `_viola_limite_dias_consecutivos` y `_viola_descanso_nocturno` reciben ahora `fecha_cedida` (el `turno_cede_fecha` del participante en ese documento) y tratan ese día como no trabajado al evaluar la racha/descanso del día recibido · 2 tests nuevos (racha con día cedido de por medio, descanso nocturno con la noche cedida como día anterior) · 11 tests de `test_servicio_factibilidad_documento_cambio.py` + 178 de los módulos relacionados de `documento_cambio` passing

- [x] style(planilla-supervision): 4 mejoras visuales de `/planilla/supervision` pedidas por el usuario. De las 4, 2 ya estaban implementadas de rondas anteriores sin cambios necesarios: botones solo-supervisora con color propio (`.nav-supervisora-row a`) y resaltado de fila al clicar el nombre de un trabajador (`.supervision-fila-resaltada`, ya soporta varios trabajadores resaltados a la vez de forma independiente). Las 2 restantes sí requerían trabajo: (1) la fila de números de día en la cabecera no se distinguía de la fila de contadores de presencia justo encima (ambas con el mismo fondo `#f5f7fa` heredado de `.supervision-matriz thead th`) — nueva clase `supervision-dianum-fila` en el `<tr>` con fondo propio (`#e2e8f0`), excluyendo vía `:not()` las celdas que ya tienen fondo de "hoy"/fin de semana para no pisarlas; (2) los días con doblaje (más de un turno el mismo día) no resaltaban visualmente, solo se veían los chips apilados — en vez del borde negro grueso que proponía el usuario, se usa `box-shadow: inset 0 0 0 3px` en ámbar (mismo acento ya usado para lo "de supervisora"/papel) sobre una nueva clase `supervision-celda--doblaje`: un borde real hubiera desplazado la cuadrícula al chocar con `border-collapse: collapse` de la tabla, mientras que el inset shadow no participa en el colapso de bordes ni compite con los fondos de "hoy"/fin de semana/fila resaltada, que son la misma propiedad `background`. 3 tests nuevos (clase de doblaje presente con 2 turnos, ausente con 1, clase de la fila de números de día) · 48 tests de `planilla_supervision` (rutas + servicio) passing
