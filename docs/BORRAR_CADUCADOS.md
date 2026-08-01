# Plan: eliminar publicaciones caducadas desde "Mis cambios"

> Cada paso está pensado para completarse en una sesión independiente de
> Claude Code. Al terminar un paso: **marca su casilla** (`[x]`), asegúrate de
> que todos los tests pasan (`pytest --testmon`), actualiza `PROGRESS.md`
> según `CLAUDE.md` y haz **un commit atómico** que incluya código + tests +
> `PROGRESS.md`. Continúa con el siguiente paso en una sesión nueva si hace
> falta ahorrar contexto.

## Objetivo

En la pantalla "Mis cambios" (`/`, `?estado=caducada`), permitir que el
usuario elimine publicaciones caducadas, una por una o todas de golpe. Algunos
usuarios quieren conservarlas visibles (no se cambia el comportamiento por
defecto: las caducadas se siguen mostrando igual que ahora); solo se añade la
opción de borrarlas.

## Contexto técnico (leer antes de empezar cualquier paso)

- **La ruta de borrado individual ya existe y ya sirve para caducadas sin
  cambios**: `POST /publicaciones/<pub_id>/eliminar`
  (`app/routes/publicaciones.py:424`, función `eliminar`). Solo comprueba
  `pub.usuario_id == current_user.id` (403 si no), **no** comprueba el
  `estado` de la publicación. Llama a
  `eliminar_publicacion(pub)` (`app/services/publicaciones.py:271`), que ya
  gestiona correctamente sintéticas, matches, notificaciones y auditoría.
  → El Paso 1 es solo **tests** que confirmen este comportamiento con una
  publicación en estado `caducada` (no hace falta tocar el backend).
- La plantilla `app/templates/main/dashboard.html` ya tiene, para cada
  publicación, un formulario de borrado con modal de confirmación
  (línea ~328, `modal-eliminar` / `abrirModalEliminar()` / JS al final del
  archivo). Pero ese bloque de acciones (`pub-acciones`, línea ~326-337) solo
  se renderiza `{% if pub.esta_activa() %}` (línea 287), y `esta_activa()`
  (`app/models/publicacion.py:46`) es `estado in ("abierta",
  "parcialmente_resuelta")` — **falso** para `caducada`. Por eso hoy no se ve
  botón de eliminar en la pestaña Caducados.
- Precedente exacto a imitar para "borrar todos": `app/routes/notificaciones.py`
  - `borrar_aviso(notif_id)` (línea 154): borra una notificación propia.
  - `borrar_todos_avisos()` (línea 165): `Notificacion.query.filter(...).delete()`
    y redirige.
  - Plantilla `app/templates/notificaciones/avisos.html` línea 10-15: botón
    "Borrar todos" en `avisos-header-actions`, visible solo si hay avisos,
    en un `<form>` POST propio (sin modal de confirmación en ese caso
    concreto — para caducados, dado que es una acción más destructiva sobre
    varias publicaciones a la vez, sí conviene modal de confirmación; ver
    Paso 3).
- El dashboard es la vista `main.index` (`app/routes/main.py:204`), con
  pestañas controladas por `estado_filtro` (query param `estado`). La pestaña
  caducados usa `_ESTADOS_DASHBOARD["caducada"] = ["caducada"]` y cae en la
  rama `else` genérica (línea 326-336) que hace:
  ```python
  publicaciones = (
      PublicacionCambio.query
      .filter_by(usuario_id=current_user.id)
      .filter(PublicacionCambio.estado.in_(estados))
      .filter(PublicacionCambio.es_sintetica.is_(False))
      .order_by(PublicacionCambio.fecha_creacion.desc())
      .all()
  )
  ```
- El conteo de la pestaña (badge `(N)`) sale de `_conteos_tabs()`
  (`app/routes/main.py:151`), campo `"caducada"`. Al borrar hay que
  redirigir de vuelta a `?estado=caducada` para que el usuario vea la lista
  actualizada y el conteo correcto.
- No hay tests todavía que cubran el borrado de una publicación caducada ni
  un borrado masivo por estado — hay que escribirlos todos desde cero
  (TDD estricto, rojo → verde).
- Los textos de plantilla van siempre con `{{ _('...') }}` (i18n obligatorio,
  ver `CLAUDE.md`).

---

## Paso 1 — Test: confirmar que el borrado individual ya funciona con caducadas ✅

- [x] En `tests/test_editar_eliminar_publicacion.py`, añadir un test que:
  1. Cree una publicación y la deje en estado `caducada` (asignar
     `pub.estado = "caducada"` directamente y hacer commit, sin depender del
     job de caducidad).
  2. Haga `POST /publicaciones/<pub_id>/eliminar` autenticado como el dueño.
  3. Compruebe `resp.status_code == 302` y que
     `db.session.get(PublicacionCambio, pub_id) is None`.
- [x] Ejecutar `pytest --testmon` y confirmar que pasa (no debería requerir
  cambios de código, solo el test; si falla, investigar por qué antes de
  seguir).
- [x] Commit: `test: cubre eliminar publicación individual en estado caducada`.

## Paso 2 — Backend: ruta de borrado masivo de caducadas ☐

- [ ] Test primero en `tests/test_editar_eliminar_publicacion.py` (o un
  archivo nuevo `tests/test_eliminar_caducadas.py`, a discreción, siguiendo
  el estilo de los tests existentes en ese archivo):
  - Requiere login (302 a `/login` si no autenticado).
  - Con 2 publicaciones `caducada` del usuario y 1 `abierta`: tras el POST,
    las 2 `caducada` desaparecen y la `abierta` sigue existiendo.
  - Publicaciones `caducada` de **otro** usuario no se tocan (aislamiento
    por `usuario_id`).
  - Redirige a `main.index` con `?estado=caducada` (o equivalente,
    verificar `Location` en la respuesta).
- [ ] Implementar en `app/routes/publicaciones.py` una nueva ruta
  `POST /publicaciones/eliminar-caducadas` (nombre de función sugerido:
  `eliminar_caducadas`), que:
  ```python
  @bp.post("/publicaciones/eliminar-caducadas")
  @login_required
  def eliminar_caducadas():
      caducadas = PublicacionCambio.query.filter_by(
          usuario_id=current_user.id, estado="caducada"
      ).all()
      for pub in caducadas:
          eliminar_publicacion(pub)
      flash(_("Publicaciones caducadas eliminadas."), "success")
      return redirect(url_for("main.index", estado="caducada"))
  ```
  Reutiliza `eliminar_publicacion` (ya importado en el archivo) en vez de un
  `.delete()` masivo, para no duplicar la lógica de limpieza de sintéticas /
  matches / notificaciones / auditoría que ya gestiona esa función.
- [ ] Ejecutar `pytest --testmon` — todos los tests nuevos y existentes en
  verde.
- [ ] Commit: `feat: añade ruta para eliminar todas las publicaciones caducadas`.

## Paso 3 — Frontend: botones de eliminar en la pestaña Caducados ☐

- [ ] En `app/templates/main/dashboard.html`:
  - Añadir un botón "Eliminar todos" junto a las demás acciones del
    header (`dashboard-header-actions`, línea ~9), visible solo cuando
    `estado_filtro == 'caducada' and publicaciones` (mismo patrón condicional
    que `avisos-header-actions` en `avisos.html`). Debe reutilizar el modal
    de confirmación existente (`modal-eliminar` / `abrirModalEliminar()`) o,
    si se prefiere no reutilizar el mismo modal para no confundir el mensaje
    de "publicación" (singular) con el de borrado masivo, duplicar un
    segundo modal `modal-eliminar-todos-caducadas` con su propio texto de
    confirmación (recomendado, dado que borra varias publicaciones a la
    vez — el usuario debe entender que es irreversible y afecta a todas).
    Form:
    ```html
    <form method="post" action="{{ url_for('publicaciones.eliminar_caducadas') }}" style="display:inline" onsubmit="return false">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <button type="button" class="btn btn-danger btn-sm" onclick="abrirModalEliminarTodasCaducadas(this.closest('form'))">{{ _('Eliminar todos') }}</button>
    </form>
    ```
  - Extender la condición del bloque `pub-acciones` (línea ~287,
    `{% if pub.esta_activa() %}`) a
    `{% if pub.esta_activa() or estado_filtro == 'caducada' %}`, de forma que
    en la pestaña Caducados se muestre el bloque de acciones. Dentro de ese
    bloque, el enlace "Editar" y el botón "Compartir" solo tienen sentido
    para publicaciones activas: envolverlos en
    `{% if pub.esta_activa() %}...{% endif %}` para que en caducadas solo se
    vea el botón "Eliminar" (que ya está fuera del `wa_texto`/`pub_url` que
    se calculan más arriba en ese mismo bloque — revisar que ese cálculo no
    falle para publicaciones caducadas antes de mover código, o mover el
    botón "Eliminar" fuera del `{% if pub.esta_activa() %}` grande en vez de
    complicar las condiciones internas; elegir la opción que quede más
    simple al implementar).
  - El botón de eliminar individual ya apunta a
    `publicaciones.eliminar` y ya usa el modal existente — no requiere
    cambios, solo que ahora sea alcanzable en esta pestaña.
- [ ] Añadir el JS del nuevo modal (si se optó por uno separado en el punto
  anterior) siguiendo el mismo patrón que `abrirModalEliminar` /
  `cerrarModalEliminar` ya presentes al final de `dashboard.html`.
- [ ] Comprobar manualmente en local (`flask run` o el flujo habitual del
  proyecto) que:
  - En la pestaña Caducados se ve el botón "Eliminar" por publicación y
    "Eliminar todos" en el header.
  - En el resto de pestañas no aparece "Eliminar todos" y el comportamiento
    de "Editar"/"Compartir"/"Eliminar" de publicaciones activas no cambia.
- [ ] Commit: `feat: permite eliminar publicaciones caducadas desde el dashboard`.

## Paso 4 — Tests de integración de la vista (opcional pero recomendado) ☐

- [ ] Test que haga `GET /?estado=caducada` con una publicación caducada del
  usuario y compruebe que la respuesta contiene el botón/form de eliminar
  individual (`publicaciones.eliminar`) y el de "Eliminar todos"
  (`publicaciones.eliminar_caducadas`).
- [ ] Test que compruebe que esos botones **no** aparecen en `GET /?estado=activos`.
- [ ] `pytest --testmon` en verde.
- [ ] Commit: `test: cubre la presencia de los botones de borrado en la pestaña Caducados`.

## Paso 5 — Cierre: PR contra staging ☐

- [ ] Confirmar que el árbol de trabajo está limpio y todos los tests pasan
  (`pytest --testmon`; si hay dudas de cobertura completa, una única pasada
  de la suite completa antes del PR).
- [ ] `git push` de la rama de feature.
- [ ] `gh pr create --base staging` con resumen de los cambios y plan de
  pruebas manual (marcar los pasos del Paso 3 verificados a mano).
- [ ] Marcar esta casilla y dar el plan por completado.

---

## Notas / decisiones pendientes de confirmar al implementar

- Nombre final de la ruta/endpoint (`publicaciones.eliminar_caducadas`) y de
  la URL (`/publicaciones/eliminar-caducadas`): ajustar si al implementar se
  encuentra un nombre ya usado o un patrón de URL más consistente con el
  resto del blueprint.
- Si en el futuro se quiere generalizar "eliminar todas las de un estado"
  más allá de caducadas, extraer la ruta a algo parametrizado — **no
  hacerlo ahora**, el MVP de este plan es solo caducadas (ver "Simplicidad
  de MVP" en `CLAUDE.md`).
