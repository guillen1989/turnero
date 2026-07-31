# Plan: usuarios normales en varios servicios (unidades)

> Cada paso está pensado para completarse en una sesión independiente. Al
> terminar un paso: todos los tests en verde, marca su casilla `[x]` en este
> documento, actualiza `PROGRESS.md` y haz **un commit atómico** que incluya
> código + tests + este documento + `PROGRESS.md` (TDD, según `CLAUDE.md`).
> Así una sesión sucesiva puede leer este archivo, ver qué queda pendiente y
> continuar sin rehacer trabajo ni releer todo el contexto.

## Terminología

En este código "servicio" = modelo `Unidad`. No existe una tabla `Servicio`
separada. Todo el plan usa "unidad" para referirse al concepto que el usuario
llama "servicio".

## Contexto técnico (leer antes de empezar cualquier paso)

Precedente a imitar en todo: el mecanismo ya existente para que una
**supervisora** trabaje sobre varias unidades.

- `app/models/usuario.py:14` — `Usuario.unidad_id` es un FK único y
  `NOT NULL` a `unidad.id`: la unidad "principal" del usuario. Se mantiene
  así — demasiado código depende de `current_user.unidad` /
  `current_user.unidad_id` directamente (`grupo_intercambio`, planilla,
  búsqueda de colegas, matching) como para tocarlo. La multi-unidad se añade
  **de forma aditiva**.
- `app/models/usuario.py:37-39` — `unidades_supervisadas = db.relationship("Unidad", secondary="unidad_supervisada", back_populates="supervisoras")`:
  única relación M:N usuario↔unidad que existe hoy en el código. Es el
  patrón a clonar.
- `app/models/unidad_supervisada.py` — tabla de asociación pura, PK
  compuesta `(usuario_id, unidad_id)`, sin columnas propias.
- `app/services/supervision.py` — helpers a clonar:
  - `unidades_supervisadas_de(usuario)`: lista ordenada por nombre.
  - `unidad_supervisada_o_403(usuario, unidad_id)`: si `unidad_id` es
    `None`, usa la unidad propia si está entre las permitidas, si no la
    primera de la lista; si viene informado, exige que esté entre las
    permitidas o aborta 403.
  - `sincronizar_unidades_supervisadas(usuario, unidad_ids)`: diff
    add/delete contra la tabla de asociación.
- Plantillas con el selector: `app/templates/documento_cambio/supervisora.html:10-15`,
  `app/templates/planilla_import/index.html:9-14`,
  `app/templates/planilla_supervision/index.html:16-21`. Patrón: si
  `unidades|length > 1`, `<select onchange="window.location.href=this.value">`
  con `<option value="{{ url_for(endpoint, unidad_id=u.id, ...) }}">`.
- Migración de referencia:
  `migrations/versions/666dde3fff3c_añade_tabla_unidad_supervisada.py` — crea
  la tabla de asociación y hace un `INSERT ... SELECT id, unidad_id FROM
  usuario WHERE es_supervisora = true` para sembrarla con el estado
  existente. El nuevo caso mirror-eará esto pero para *todos* los usuarios.
- Alta/edición de supervisoras desde admin:
  `app/routes/admin/usuarios.py` (`usuario_nuevo`, `usuario_editar`) +
  `app/forms/admin.py` (`AdminUsuarioForm.unidades_supervisadas`,
  `SelectMultipleField`) + `app/templates/admin/usuario_form.html`.
- Rutas objetivo para el selector de unidad activa (hoy asumen una sola
  unidad vía `current_user.unidad`):
  - `app/routes/calendario.py:26` (`index`) — usa `construir_calendario_mes(current_user, ...)`.
  - `app/routes/main.py:372` (`cambios`) — línea 385
    `grupo_id = current_user.unidad.grupo_intercambio_id`, línea 396 join
    `Usuario.unidad_id == Unidad.id`.
  - `app/routes/planilla.py:45` (`index`) y `_resolver_seleccion` (línea 34)
    — usan `current_user` / `current_user.grupo_intercambio` directamente.
- Registro/perfil de usuario normal (una sola unidad hoy):
  `app/services/registro.py` (`registrar_usuario`, `encontrar_o_crear_unidad`,
  `resolver_unidad`), `app/routes/auth.py:70` (`registro`) y
  `app/routes/auth.py:367` (`perfil`, líneas 419-434 llaman a
  `actualizar_perfil`, que sustituye la unidad — no añade una segunda).
- Notificaciones: `app/models/notificacion.py:7-36` — **no tiene** columna de
  unidad/servicio de origen; hoy se infiere transitivamente vía
  `usuario_id -> usuario.unidad_id`, lo que deja de servir en cuanto un
  usuario puede pertenecer a varias. Sitios donde se instancia
  `Notificacion(...)` y habrá que añadir el origen:
  `app/services/busquedas_guardadas.py:126`, `app/services/documento_cambio.py:61`,
  `app/services/matches.py:73,85,114,133`, `app/services/publicaciones.py:62`,
  `app/routes/publicaciones.py:645`.
- Ruta de notificaciones: `app/routes/notificaciones.py` (`panel` línea
  40-52, `avisos` línea 114-151). `_colegas_del_usuario` (línea 178-188) usa
  `usuario.unidad.grupo_intercambio_id` — habrá que revisarlo para que
  considere todas las unidades del usuario si aplica.

## Decisiones tomadas (confirmadas por el usuario)

- **Categoría por unidad, no global.** Un usuario puede tener una
  **categoría profesional distinta en cada unidad** a la que pertenece (p.
  ej. enfermera en el servicio A, auxiliar en el servicio B). Por tanto la
  tabla de asociación nueva (`usuario_unidad`) **no es una tabla de
  asociación pura como `unidad_supervisada`**: debe llevar su propia columna
  `categoria_id`, ya que el matching y la visibilidad ("misma categoría
  profesional y mismo grupo de intercambio") dependen de la categoría
  *en esa unidad concreta*, no de una categoría global del usuario.
  `Usuario.categoria_id` se mantiene como la categoría de la unidad
  principal (compat con todo el código que ya la usa directamente).
- **Unidad activa persistida en sesión**, no solo query param como hace hoy
  la supervisora. Motivo: un usuario normal navega entre `/calendario`,
  `/cambios` y `/planilla` como páginas independientes a lo largo del día, y
  perder la selección en cada navegación sería más fricción que para una
  supervisora que suele quedarse en una sola pantalla. El query param
  sigue existiendo como override puntual (p. ej. el `<select>` de cambio de
  unidad), pero si no viene informado se usa la unidad activa de sesión, y
  si tampoco hay sesión se cae a la unidad principal.
- **`unidad_id` (principal) no se toca.** Sigue siendo el FK NOT NULL de
  siempre; la multi-unidad es aditiva vía `usuario_unidad`.

## Preguntas abiertas / a confirmar antes o durante el desarrollo

- [ ] ¿Añadir una unidad nueva (propia o de otro usuario, ya existente en la
  BD) es libre para cualquier usuario autenticado, igual que hoy es libre
  elegir la unidad en el registro? ¿O debería requerir algún tipo de
  validación (p. ej. que un admin/supervisora de esa unidad lo apruebe)?
  El plan de abajo asume **autoservicio libre**, igual que el resto del
  registro hoy, salvo que se indique lo contrario.
- [ ] ¿Puede un usuario abandonar una unidad (no solo añadir)? El plan
  incluye esa opción básica en el perfil por simetría con "añadir", pero
  confirma si hace falta alguna restricción (p. ej. no poder abandonar la
  unidad principal, o exigir que no tenga publicaciones abiertas en ella).

---

## Paso 1 — Modelo de datos: tabla `usuario_unidad` con categoría por unidad

- [ ] Escribir tests de modelo: crear un `Usuario`, asociarlo a una segunda
  `Unidad` con una `Categoria` propia distinta de `usuario.categoria_id`, y
  comprobar que `usuario.unidades` (nueva relación) devuelve ambas unidades
  y que se puede leer la categoría específica de cada membresía.
- [ ] Modelo `UsuarioUnidad` (`app/models/usuario_unidad.py`), mirror de
  `unidad_supervisada.py` pero con columna propia:
  - `usuario_id` (FK, parte de la PK compuesta)
  - `unidad_id` (FK, parte de la PK compuesta)
  - `categoria_id` (FK a `categoria.id`, `NOT NULL` — la categoría del
    usuario *en esa unidad*)
- [ ] Añadir a `Usuario` (`app/models/usuario.py`):
  - `unidades = db.relationship("Unidad", secondary="usuario_unidad", back_populates="miembros")`
  - considerar un helper/property para acceder a la membresía completa
    (con su categoría), no solo a la `Unidad`, ya que el `secondary=`
    simple no expone las columnas extra de la tabla de asociación — puede
    hacer falta acceder también a `usuario.membresias_unidad` (relationship
    directa al modelo `UsuarioUnidad`) cuando se necesite la categoría.
- [ ] Añadir a `Unidad` (`app/models/unidad.py`) la relación inversa
  `miembros`.
- [ ] Servicio `app/services/unidad_usuario.py` (mirror de
  `supervision.py`):
  - `unidades_de(usuario)` → lista ordenada por nombre, incluyendo siempre
    la unidad principal.
  - `categoria_en_unidad(usuario, unidad)` → categoría del usuario en esa
    unidad concreta (la principal si `unidad == usuario.unidad`, si no la
    de `UsuarioUnidad`).
  - `pertenece_a(usuario, unidad)`.
  - `unidad_activa_o_403(usuario, unidad_id, session_key="unidad_activa_id")`
    — mismo espíritu que `unidad_supervisada_o_403` pero con la lógica de
    sesión descrita arriba (query param > sesión > unidad principal).
  - `sincronizar_unidades(usuario, membresias)` donde `membresias` es un
    dict `{unidad_id: categoria_id}` — igual que
    `sincronizar_unidades_supervisadas` pero conservando/actualizando la
    categoría de cada membresía, y **sin poder eliminar la unidad
    principal** de la lista (asegurar con un `assert`/validación explícita).
- [ ] Todos los tests en verde (`pytest --testmon`).

## Paso 2 — Migración Alembic

- [ ] Modificar los modelos (paso 1) y ejecutar
  `flask db migrate -m "añade tabla usuario_unidad"`.
- [ ] Revisar el `upgrade()` generado y editarlo para que mirror-ee
  `666dde3fff3c`: crear tabla con PK compuesta `(usuario_id, unidad_id)`,
  FKs a `usuario.id` y `unidad.id`, columna `categoria_id NOT NULL` con FK a
  `categoria.id`.
- [ ] Backfill: `INSERT INTO usuario_unidad (usuario_id, unidad_id,
  categoria_id) SELECT id, unidad_id, categoria_id FROM usuario` — siembra
  la membresía de la unidad principal de cada usuario existente, usando su
  categoría global actual.
- [ ] `downgrade()` simétrico (`drop_table`).
- [ ] `flask db heads` debe mostrar exactamente `1 (head)`.
- [ ] Aplicar la migración en local y correr la suite de modelos del paso 1
  contra la BD migrada.

## Paso 3 — Alta de cuenta: añadir un segundo servicio opcional

- [ ] Tests de `app/routes/auth.py::registro` (o del servicio
  `registrar_usuario`) cubriendo: registro con una sola unidad (comportamiento
  actual, no debe romperse) y registro añadiendo una segunda unidad +
  categoría en esa unidad.
- [ ] Formulario de registro: añadir un bloque opcional "añadir otro
  servicio" (checkbox/botón "+ añadir servicio" que revela un segundo
  selector de hospital/unidad + categoría, igual de estructura que el
  principal — reutilizar los mismos endpoints `api_hospitales`/`api_unidades`
  ya existentes en `auth.py`).
- [ ] `registrar_usuario` (`app/services/registro.py`) acepta una lista
  opcional de unidades adicionales (cada una con su propia categoría) y
  llama a `sincronizar_unidades` tras crear el usuario con su unidad
  principal de siempre.
- [ ] Plantilla de registro actualizada; verificar en navegador (`/run` o
  servidor de desarrollo) el flujo completo: alta con 1 unidad, alta con 2.

## Paso 4 — Autoservicio: añadir/abandonar unidades desde el perfil

- [ ] Tests de la nueva vista de gestión de unidades del perfil de usuario
  normal (no supervisora): añadir una unidad nueva con su categoría, listar
  las unidades actuales, abandonar una unidad no-principal.
- [ ] Nueva sección en `app/templates/auth/perfil.html` (o pestaña nueva,
  a decidir por consistencia visual con `perfil_supervisora.html`) que
  liste las unidades actuales del usuario (con su categoría en cada una) y
  permita:
  - añadir una unidad (selector hospital → unidad + categoría en esa
    unidad), reutilizando `sincronizar_unidades`.
  - abandonar una unidad no-principal (confirmar respuesta a la pregunta
    abierta sobre restricciones antes de implementar el botón "abandonar").
- [ ] Ruta nueva o ampliación de `app/routes/auth.py::perfil` para manejar
  el POST de alta/baja de unidad.
- [ ] Verificar en navegador el flujo de añadir una segunda unidad desde un
  usuario ya registrado con una sola.

## Paso 5 — Selector de unidad activa en `/calendario`, `/cambios`, `/planilla`

- [ ] Tests de cada ruta: usuario con 2 unidades, comprobar que sin
  `unidad_id` en la URL se usa la de sesión (o la principal si no hay
  sesión), que con `unidad_id` válido cambia el contexto, y que con
  `unidad_id` de una unidad a la que NO pertenece devuelve 403.
- [ ] Sustituir los usos directos de `current_user.unidad` /
  `current_user.grupo_intercambio` en `app/routes/calendario.py`,
  `app/routes/main.py::cambios` y `app/routes/planilla.py` (incluida
  `_resolver_seleccion`) por `unidad_activa_o_403(current_user, unidad_id)`
  del paso 1, y por `categoria_en_unidad(current_user, unidad_activa)` allí
  donde hoy se usa `current_user.categoria_id` para filtrar matching /
  visibilidad (p. ej. `main.py:400` `Usuario.categoria_id ==
  current_user.categoria_id` debe pasar a comparar contra la categoría del
  usuario **en la unidad activa**, no la global).
- [ ] Guardar la unidad activa en sesión al cambiarla (nueva clave de
  sesión, p. ej. `session["unidad_activa_id"]`).
- [ ] Reutilizar el patrón de plantilla del `<select onchange=...>` (mismo
  idioma que `documento_cambio/supervisora.html`) en las plantillas de
  `calendario`, `cambios` (dashboard) y `planilla`, mostrando el selector
  solo si `len(unidades_de(current_user)) > 1` (simplicidad MVP: usuarios de
  una sola unidad no ven ningún selector nuevo).
- [ ] Auditar otros puntos que asuman implícitamente una sola unidad del
  usuario al construir/filtrar publicaciones o el motor de matching (grep
  de `current_user.unidad` / `current_user.categoria_id` / `current_user.grupo_intercambio`
  fuera de las 3 rutas ya cubiertas) y decidir, caso a caso, si deben pasar
  a depender de la unidad activa.
- [ ] Verificar manualmente en navegador: usuario con 2 unidades cambiando
  entre ellas en las 3 páginas, comprobando que el calendario/cambios/planilla
  mostrados corresponden solo a la unidad seleccionada.

## Paso 6 — Notificaciones: unidad de origen + bandeja única

- [ ] Tests: crear notificaciones para un usuario con 2 unidades desde
  distintos orígenes (match, publicación, documento de cambio) y comprobar
  que cada una queda etiquetada con la unidad correcta; comprobar que
  `/notificaciones` sigue mostrando todas juntas (una sola bandeja, sin
  filtrar por unidad activa).
- [ ] Migración de 3 pasos (`CLAUDE.md`) para añadir `unidad_id` (nullable
  primero) a `Notificacion`, backfill desde `usuario.unidad_id` de cada
  notificación existente, luego `NOT NULL`.
- [ ] Añadir el argumento `unidad_id`/`unidad` a la creación de
  `Notificacion` en los 6 sitios listados en el contexto técnico
  (`busquedas_guardadas.py:126`, `documento_cambio.py:61`, `matches.py:73,85,114,133`,
  `publicaciones.py:62`, `routes/publicaciones.py:645`), pasando en cada
  caso la unidad relevante al evento (normalmente la unidad de la
  publicación/documento que originó la notificación, no necesariamente
  `usuario.unidad` si el destinatario tiene varias).
- [ ] Plantilla de `/notificaciones` (`app/routes/notificaciones.py` +
  su template): mostrar el nombre de la unidad de origen junto a cada
  aviso, **solo si `current_user` pertenece a más de una unidad** (si solo
  tiene una, no añadir ruido visual).
- [ ] Revisar `_colegas_del_usuario` (`app/routes/notificaciones.py:178-188`)
  para que considere las unidades relevantes al calcular "colegas" cuando
  el usuario pertenece a varias.
- [ ] Verificar en navegador con un usuario demo de 2 unidades que recibe
  avisos de ambas y los distingue correctamente.

## Paso 7 — Web Push: incluir la unidad en el payload

- [ ] Revisar el código que construye el payload de Web Push (buscar desde
  `push_subscription`/`push_activo` en `app/models/usuario.py` hacia el
  servicio que envía las notificaciones push) y comprobar si ya incluye
  algún texto identificable de la unidad.
- [ ] Si no lo incluye, añadir el nombre de la unidad de origen al título o
  cuerpo del push, solo cuando el usuario destinatario pertenece a más de
  una unidad, siguiendo el mismo test-first que en el resto de pasos.

## Paso 8 — Documentación y cierre

- [ ] Actualizar `PROGRESS.md` con el cierre de esta fase.
- [ ] Revisar que no queda código muerto de rutas/plantillas antiguas
  (p. ej. si el formulario de registro cambió de forma, limpiar el HTML
  anterior).
- [ ] Pasar la suite completa una única vez al cerrar la fase (el resto de
  pasos usa `pytest --testmon`).
