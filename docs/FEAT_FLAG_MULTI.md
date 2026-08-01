# Plan: feature flag general para desactivar la multi-unidad

> Cada paso está pensado para completarse en una sesión independiente. Al
> terminar un paso: todos los tests en verde, marca su casilla `[x]` en este
> documento, actualiza `PROGRESS.md` y haz **un commit atómico** que incluya
> código + tests + este documento + `PROGRESS.md` (TDD, según `CLAUDE.md`).
> Así una sesión sucesiva puede leer este archivo, ver qué queda pendiente y
> continuar sin rehacer trabajo ni releer todo el contexto.

## Objetivo

Todo el sistema de "usuarios en varios servicios (unidades)" —
`docs/USUARIOS_MULTI.md` (Fase 13/14) + `docs/FIX_MULTI.md` (Fase 15), ya
fusionado en `staging` — debe poder **activarse o desactivarse por completo
mediante un único flag general**, sin posibilidad de activarlo/desactivarlo
solo para determinadas unidades (a diferencia de otros flags existentes como
`hoja_cambio_digital`, que sí admiten habilitación por unidad).

Con el flag **desactivado**, la aplicación debe comportarse exactamente como
antes de la Fase 13: cada usuario opera únicamente con su unidad principal
(`usuario.unidad`), sin selectores de unidad, sin bloque de "añadir otro
servicio" en el registro, sin gestión de servicios en el perfil, y sin
etiquetas de unidad en notificaciones/push/publicaciones (al colapsar a una
única unidad, esas etiquetas ya no tienen sentido y desaparecen solas). Los
datos de membresías adicionales, turnos de planilla en otras unidades, etc.
**no se borran** — simplemente dejan de ser accesibles hasta que se
reactive el flag.

## Contexto técnico (leer antes de empezar cualquier paso)

Infraestructura de feature flags ya existente y a reutilizar (no crear un
mecanismo nuevo):

- `app/models/feature_flag.py` (`FeatureFlag`: `clave`, `descripcion`,
  `activo_global`) y `app/models/feature_flag_unidad.py`
  (`FeatureFlagUnidad`, N:M flag↔unidad para habilitación parcial).
- `app/services/feature_flags.py`:
  - `feature_activa(clave, unidad=None)` — si no se pasa `unidad`, **solo
    mira `activo_global`** (la lista `unidades_habilitadas` se ignora
    cuando `unidad is None`). Este es el mecanismo que ya nos da
    "global-only" gratis: basta con no pasar nunca una `unidad` al
    comprobar este flag concreto.
  - `feature_activa_para_usuario_actual(clave)` — usa
    `current_user.unidad` como `unidad`; funcionalmente equivalente a
    global-only *mientras nunca se puebla* `FeatureFlagUnidad` para este
    flag (ver Paso 2).
  - `requiere_feature(clave)` — decorador que hace `abort(404)` a una ruta
    completa si el flag no está activo. Ya usado por
    `hoja_cambio_digital`, `planilla_supervision_multiunidad` e
    `importacion_planilla` (grep `requiere_feature` en `app/routes/`).
  - `app/__init__.py:45-46` expone `feature_activa_para_usuario_actual`
    como global de Jinja bajo el nombre `feature_activa`, así que las
    plantillas ya pueden hacer `{% if feature_activa('multi_unidad') %}`
    sin tocar nada más.
- Migraciones de seed de flags: `migrations/versions/c90b9b61f0f8_...py`
  (patrón `op.bulk_insert` sobre `feature_flag`, `downgrade` con `DELETE`).
- Admin: `app/routes/admin/feature_flags.py` +
  `app/templates/admin/feature_flags.html` — un único listado con
  checkbox `activo_global` y `<select multiple>` de unidades por flag.

Choke points de la multi-unidad a los que hay que enseñar el flag
(`app/services/unidad_usuario.py`):

- `unidades_de(usuario)` (línea 8) — devuelve la unidad principal + todas
  las membresías `usuario_unidad`. Es el que consultan
  `app/routes/calendario.py:48`, `documento_cambio.py:484,543`,
  `notificaciones.py:182`, `planilla.py:101`, `main.py:214,485`,
  `auth.py:665` para decidir si mostrar selector/etiqueta de unidad
  (`unidades|length > 1`). **Colapsarlo a `[usuario.unidad]` cuando el
  flag esté desactivado hace que todos esos selectores y etiquetas
  desaparezcan solos**, sin tocar cada sitio uno a uno.
- `unidad_activa_o_403(usuario, unidad_id, session_key=...)` (línea 32) —
  choke point de **todas** las rutas que resuelven "con qué unidad estoy
  trabajando ahora" (`calendario.py:36`, `documento_cambio.py:296,399`,
  `planilla.py:52,115,198,209,236,272,314,358,372,405,442`, `main.py:392`,
  `publicaciones.py:225,373,618`). Con el flag desactivado debe **ignorar
  siempre** el `unidad_id` de query string y el de sesión, y devolver
  `usuario.unidad` sin abortar con 403 (para no romper bookmarks/sesiones
  con un `unidad_id` guardado de cuando el flag estaba activo).
- `pertenece_a(usuario, unidad)` (línea 16) — **no tocar**: se usa también
  para comprobar la propiedad de datos ya existentes (p. ej.
  `publicaciones.py:470,613` al validar el dueño de una publicación
  antigua). Si se hiciera depender del flag, desactivar el flag podría
  devolver 403 sobre datos legítimos creados mientras estaba activo. Solo
  `unidad_activa_o_403` (el punto de *selección* activa, no el de
  *propiedad* de datos) debe cambiar de comportamiento con el flag.

Sitios que consultan la relación `usuario.unidades` **directamente**, sin
pasar por `unidades_de()`, y que por tanto NO colapsarán solos con el
cambio anterior — hay que corregirlos aparte:

- `app/templates/notificaciones/avisos.html` líneas 22, 37, 59, 98:
  `{% if aviso.unidad_id and current_user.unidades|length > 1 and aviso.unidad %}`.
- `app/push/sender.py:230`: `if unidad_nombre and len(usuario.unidades) > 1`.
- `app/templates/main/dashboard.html:203` **ya** usa `unidades|length > 1`
  con `unidades` pasado desde `main.py:485` (`unidades=unidades_de(...)`) —
  este ya está bien, solo verificar que sigue así.

Rutas dedicadas en exclusiva a gestionar la multi-unidad (candidatas a
`@requiere_feature("multi_unidad")` directo, sin lógica adicional):

- `app/routes/auth.py:662` `perfil_servicios` (GET).
- `app/routes/auth.py:685` `agregar_unidad` (POST).
- `app/routes/auth.py:725` `abandonar_unidad` (POST).

Punto no cubierto por una ruta dedicada — el bloque opcional "añadir otro
servicio" vive **dentro** de la ruta general `auth.py:142 registro()`
(no se puede decorar la ruta entera, sirve también al registro de una sola
unidad):

- `app/routes/auth.py:100 _resolver_extra_servicio(form)` — debe devolver
  `([], False)` sin procesar nada si el flag está desactivado (defensa en
  profundidad: aunque la plantilla oculte el bloque, un POST directo no
  debe colar una segunda unidad).
- `app/templates/auth/registro.html:130-135` bloque `#extra-servicio-block`
  — ocultar con `{% if feature_activa('multi_unidad') %}`.
- `app/templates/auth/perfil.html:11` enlace a la pestaña "Servicios" —
  ocultar con el mismo `{% if %}`.

## Decisión de diseño: un único flag, reutilizando la infraestructura existente

- **Clave del flag: `multi_unidad`.**
- Se reutiliza `FeatureFlag`/`feature_activa` tal cual — no se crea tabla
  ni mecanismo nuevo. La propiedad "solo global, nunca por unidad" se
  consigue **por convención**: en todo el código, este flag se comprueba
  siempre con `feature_activa("multi_unidad")` (sin `unidad`) o con el
  global de Jinja `feature_activa('multi_unidad')` (que internamente usa
  `current_user.unidad`, pero como nunca se puebla
  `FeatureFlagUnidad` para esta clave, el resultado equivale a mirar solo
  `activo_global`).
- En `app/templates/admin/feature_flags.html`, ocultar el `<select
  multiple>` de "Unidades habilitadas" cuando `flag.clave == "multi_unidad"`
  (con una nota explicando que este flag es global-only), para que un
  admin no pueda pensar que seleccionar unidades ahí tiene efecto.
- Alternativa descartada: añadir una columna `solo_global` a `FeatureFlag`
  para generalizar la restricción a cualquier flag futuro. Se descarta por
  ahora (YAGNI/simplicidad de MVP — hoy solo hace falta para este flag); si
  en el futuro surge un segundo flag global-only, revisar esta decisión.

## Paso 1 — Migración: crear el flag `multi_unidad` (desactivado por defecto)

- [x] Migración de seed (mismo patrón que `c90b9b61f0f8_...py`):
  `op.bulk_insert` en `feature_flag` con
  `clave="multi_unidad"`, `descripcion` explicando el alcance, y
  `activo_global=True` (activado por defecto para que la multi-unidad siga
  funcionando; en producción el flag ya está activo, así que no hay cambio).
  `downgrade()` con `DELETE FROM feature_flag WHERE clave = 'multi_unidad'`.
- [x] `flask db heads` debe mostrar exactamente `1 (head)`.
- [x] Aplicar la migración en local.

## Paso 2 — Admin: ocultar el selector por unidad para este flag

- [x] Test de la vista `admin.feature_flags` (o de plantilla): comprobar
  que la fila del flag `multi_unidad` no renderiza el `<select
  name="unidades_habilitadas">`, mientras que el resto de flags sí lo
  siguen mostrando.
- [x] `app/templates/admin/feature_flags.html`: condicionar el bloque del
  selector a `flag.clave != "multi_unidad"`, añadiendo un texto breve
  (`{{ _('Este flag es global: no admite activación por unidad.') }}`) en
  su lugar.
- [x] `pytest --testmon` en verde.

## Paso 3 — Choke points centrales: `unidades_de` y `unidad_activa_o_403`

- [x] Tests de `app/services/unidad_usuario.py` (mockeando/creando el flag
  `multi_unidad` activo/inactivo vía `app/services/feature_flags.py`):
  - `unidades_de(usuario)` con flag desactivado devuelve solo
    `[usuario.unidad]` aunque el usuario tenga membresías en
    `usuario_unidad`; con el flag activo, sigue devolviendo todas (test de
    no-regresión).
  - `unidad_activa_o_403(usuario, unidad_id)` con flag desactivado: pasando
    el `unidad_id` de una unidad secundaria real del usuario, devuelve
    igualmente `usuario.unidad` (no aborta, no la respeta); con
    `session[session_key]` informado a una unidad secundaria, igual
    (devuelve la principal, ignora la sesión); con flag activo, comportamiento
    sin cambios (test de no-regresión).
- [x] Implementar: ambas funciones comprueban
  `feature_activa("multi_unidad")` al principio y cortocircuitan como
  arriba si está desactivado.
- [x] `pertenece_a` — **sin cambios** (ver justificación en el contexto
  técnico); añadir un test que lo documente explícitamente (con el flag
  desactivado, `pertenece_a` sigue devolviendo `True` para una membresía
  secundaria real, aunque `unidad_activa_o_403` ya no permita
  seleccionarla activamente).
- [x] `pytest --testmon` en verde.

## Paso 4 — Rutas dedicadas de gestión de servicios: `@requiere_feature`

- [ ] Tests de `app/routes/auth.py`: con el flag desactivado,
  `GET /perfil/servicios`, `POST /perfil/unidades/agregar` y
  `POST /perfil/unidades/<id>/abandonar` devuelven 404; con el flag
  activado, comportamiento actual sin cambios (test de no-regresión).
- [ ] Decorar `perfil_servicios`, `agregar_unidad` y `abandonar_unidad` con
  `@requiere_feature("multi_unidad")` (mismo patrón que
  `documento_cambio.py`/`planilla_import.py`).
- [ ] `app/templates/auth/perfil.html:11`: ocultar el enlace a la pestaña
  "Servicios" con `{% if feature_activa('multi_unidad') %}` (si no, un
  usuario llegaría a un enlace que da 404).
- [ ] `pytest --testmon` en verde.

## Paso 5 — Registro: bloque "añadir otro servicio"

- [ ] Tests de `app/routes/auth.py::registro` / `_resolver_extra_servicio`:
  con el flag desactivado, un POST que incluya los campos
  `extra_servicio`/`extra_hospital_id`/... se registra igualmente pero
  **ignorando** esos campos (el usuario queda con una sola unidad, sin
  error); con el flag activado, comportamiento actual sin cambios.
- [ ] `_resolver_extra_servicio(form)` (`app/routes/auth.py:100`): primera
  línea, si `not feature_activa("multi_unidad")` devolver `([], False)`.
- [ ] `app/templates/auth/registro.html:130-135`: ocultar el checkbox y el
  bloque `#extra-servicio-block` con `{% if feature_activa('multi_unidad') %}`.
- [ ] `pytest --testmon` en verde.
- [ ] Verificar en navegador con el flag desactivado: el formulario de
  registro no muestra la opción de segundo servicio.

## Paso 6 — Notificaciones y Web Push: etiquetas de unidad

- [ ] Tests: con el flag desactivado, un usuario con membresías reales en
  2 unidades (dato preexistente) no ve la etiqueta de unidad en
  `/notificaciones` ni en el cuerpo de un push, aunque
  `aviso.unidad`/`unidad_nombre` vengan informados; con el flag activado,
  comportamiento actual sin cambios.
- [ ] `app/routes/notificaciones.py` (función que renderiza `avisos`):
  pasar al contexto de plantilla algo como `mostrar_unidad = len(unidades_de(usuario)) > 1`
  (ya calcula `unidades = unidades_de(usuario)` en la línea 182 — reusar
  esa variable) y sustituir en `app/templates/notificaciones/avisos.html`
  (líneas 22, 37, 59, 98) `current_user.unidades|length > 1` por la nueva
  variable de contexto.
- [ ] `app/push/sender.py:230`: sustituir `len(usuario.unidades) > 1` por
  `len(unidades_de(usuario)) > 1` (importar `unidades_de` desde
  `app.services.unidad_usuario`).
- [ ] Confirmar que `app/templates/main/dashboard.html:203` ya usa la
  variable de contexto correcta (`unidades` desde `main.py:485`) — no
  debería requerir cambios, solo un test de no-regresión.
- [ ] `pytest --testmon` en verde.

## Paso 7 — Verificación manual end-to-end y cierre

- [ ] Con un usuario demo que tenga 2 unidades reales en base de datos:
  - Flag **desactivado**: verificar en navegador que no aparece ningún
    selector de unidad en `/calendario`, `/cambios`, `/planilla`, ni en la
    hoja de cambio nueva; que `/perfil` no muestra la pestaña "Servicios";
    que `/perfil/servicios` da 404 si se accede directamente por URL; que
    las notificaciones y el dashboard no muestran etiquetas de unidad; que
    la planilla solo muestra los turnos de la unidad principal.
  - Activar el flag desde `/admin/feature-flags` (checkbox
    `activo_global`, sin tocar ningún selector de unidades porque ya no
    existe para este flag) y repetir la misma navegación: todo debe volver
    a comportarse como hoy en `staging` (selectores visibles, pestaña
    "Servicios" accesible, etiquetas de unidad donde corresponda).
- [ ] Pasar la suite completa una única vez (el resto de pasos usa
  `pytest --testmon`).
- [ ] Actualizar `PROGRESS.md` cerrando esta fase.
- [ ] Revisar que no queda código muerto (imports sin usar, etc.).
