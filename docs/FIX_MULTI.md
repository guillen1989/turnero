# Plan: arreglar deuda pendiente de multi-unidad (usuarios en varios servicios)

> Cada paso está pensado para completarse en una sesión independiente. Al
> terminar un paso: todos los tests en verde, marca su casilla `[x]` en este
> documento, actualiza `PROGRESS.md` y haz **un commit atómico** que incluya
> código + tests + este documento + `PROGRESS.md` (TDD, según `CLAUDE.md`).
> Así una sesión sucesiva puede leer este archivo, ver qué queda pendiente y
> continuar sin rehacer trabajo ni releer todo el contexto.

## Contexto (leer antes de empezar cualquier paso)

La funcionalidad de "usuarios normales en varios servicios (unidades)" se
implementó en `docs/USUARIOS_MULTI.md` (Pasos 1-8, fusionado a `staging` en
el PR #53, `feature/usuarios-multi-unidad`). Ese documento sigue siendo la
referencia de la arquitectura multi-unidad: `Usuario.unidades` (M:N vía
`UsuarioUnidad`, con `categoria_id` propio por membresía),
`app/services/unidad_usuario.py` (`unidad_activa_o_403`,
`categoria_en_unidad`, `unidades_de`, unidad activa persistida en
`session["unidad_activa_id"]`).

El Paso 5 de ese plan hizo una auditoría (ver `docs/USUARIOS_MULTI.md`,
sección "Resultados de la auditoría" dentro del Paso 5) y encontró **21
casos "MUST change"** en 4 archivos que siguen usando
`current_user.unidad` / `current_user.categoria_id` /
`current_user.grupo_intercambio` en vez de la unidad activa. Esos 21 casos
quedaron pendientes explícitamente para una fase futura. **Esta fase es esa
fase futura**, más dos huecos de diseño adicionales descubiertos ahora:

1. **Bug en `/planilla`**: el selector de unidad (`planilla-select-unidad`)
   cambia `unidad_activa` correctamente (confirmado leyendo
   `app/routes/planilla.py::index`, que ya llama a `unidad_activa_o_403` y
   filtra `franjas` por `unidad_activa.grupo_intercambio_id`), **pero el
   visor de turnos del mes no se filtra por unidad**. Causa raíz:
   `get_turnos_mes`, `get_estados_mes`, `get_salientes_mes`,
   `get_notas_mes` y `dias_sin_cumplimentar` en `app/services/planilla.py`
   filtran únicamente por `usuario_id` + año/mes — nunca por unidad,
   porque **`TurnoPlanilla`, `EstadoDiaPlanilla`, `SalienteDia` y
   `NotaDia` no tienen ninguna columna que indique a qué unidad
   pertenecen**. El cambio de unidad en el selector solo afecta a qué
   franjas aparecen como opciones para *añadir* un turno nuevo, no a qué
   turnos ya guardados se muestran.
2. **`PublicacionCambio` y "Mis cambios publicados" (`main.index` /
   `app/templates/main/dashboard.html`)**: la publicación tampoco tiene
   columna de unidad — se infiere transitivamente vía
   `usuario.unidad_id` (la unidad *principal*, no la activa en el momento
   de publicar). El dashboard `main.index` no filtra ni por unidad ni
   ofrece selector: **muestra todas las publicaciones del usuario
   (`PublicacionCambio.usuario_id == current_user.id`) sin distinguir de
   qué unidad son** — no es un fallo de query, es que la información de
   "de qué unidad es esta publicación" ni siquiera existe hoy en el
   modelo.
3. **`DocumentoCambio` (hoja de cambio) sí tiene `unidad_id`** (`app/models/documento_cambio.py:32`,
   `nullable=False`), pero `app/routes/documento_cambio.py::nueva` lo fija
   siempre a `current_user.grupo_intercambio` (la unidad principal): no
   hay forma de elegir con qué unidad se está haciendo el cambio si el
   usuario pertenece a varias.

## Opinión y decisión de diseño — "Mis cambios publicados"

Antes de tocar código: **recomendación para el punto 2** (mismo criterio
que ya se aplicó a las notificaciones en el Paso 6 de
`docs/USUARIOS_MULTI.md`, que resolvió el mismo dilema con "bandeja única +
etiqueta de unidad de origen"):

**Una sola pantalla `main.index` con todas las publicaciones del usuario en
todas sus unidades, etiquetando cada tarjeta con el nombre de la unidad**
(solo si el usuario pertenece a más de una — igual que en notificaciones),
en vez de añadir un selector de unidad que obligue a navegar entre
bandejas separadas. Motivos:
- Precedente ya validado en el propio código: notificaciones resolvió
  exactamente este dilema así.
- Una publicación es un objeto personal del usuario (igual que una
  notificación), no un recurso "de la unidad" como sí lo es la planilla o
  el buscador de cambios de compañeros — no hay razón funcional para
  esconder las publicaciones de una unidad mientras se mira la otra.
- Menos fricción: un usuario con 2 unidades probablemente publica pocos
  cambios en cada una; forzar a cambiar de selector para verlos todos es
  peor experiencia que una lista corta con etiqueta.
- Es coherente con la filosofía "simplicidad de MVP" de `CLAUDE.md`.

Esta decisión queda como **asunción de partida del Paso 3** de este plan.
Si al ejecutar ese paso se prefiere lo contrario (selector, como en
`/calendario`, `/cambios`, `/planilla`), es una alternativa igual de válida
técnicamente — el borrador de abajo asume la opción recomendada, pero
confírmalo antes de implementar si hay dudas.

## Paso 0 — Confirmar decisiones de diseño antes de tocar código

- [x] Confirmar (o cambiar) la decisión de "Mis cambios publicados" de
  arriba: bandeja única con etiqueta de unidad vs. selector.
  **Decidido: bandeja única con etiqueta de unidad.**
- [x] Decidir el alcance real del bug de `/planilla`: ¿la planilla debe
  seguir siendo **un único calendario personal** (un turno por día,
  independientemente de en qué unidad se trabaje ese día — hoy es así de
  facto porque no hay columna de unidad) y el selector de unidad solo debe
  servir para elegir con qué franjas de qué unidad se rellena cada día; o
  debe pasar a haber **una planilla por unidad** (turnos con su propia
  columna de unidad, pudiendo en teoría solaparse fechas entre unidades)
  como sugiere la petición original ("el usuario debe tener una planilla
  en cada servicio"). Esto determina si el Paso 1 de abajo es solo un
  ajuste de UI/consulta o requiere migración de modelo. **El plan de abajo
  asume la opción "una planilla por unidad" (con columna de unidad en
  `TurnoPlanilla` y compañía) porque es la que pide el enunciado original y
  la que hace falta para que la comprobación de factibilidad de cambios y
  las cuentas de supervisora funcionen correctamente por unidad.**
  **Decidido: una planilla por unidad.**

## Paso 1 — `TurnoPlanilla` (y compañía) por unidad

- [x] Tests de modelo/servicio: un usuario con 2 unidades guarda un turno
  en la unidad A para un día, cambia la unidad activa a B y guarda un
  turno *distinto* para el mismo día; comprobar que `get_turnos_mes`
  filtrado por unidad A solo devuelve el de A, y por B solo el de B.
- [x] Añadir columna `unidad_id` (FK a `unidad.id`) a `TurnoPlanilla`,
  `EstadoDiaPlanilla`, `SalienteDia` y `NotaDia`
  (`app/models/planilla.py`), nullable primero.
- [x] Migración de 3 pasos (`CLAUDE.md`): añadir nullable, backfill con
  `usuario.unidad_id` de cada fila existente (asume que todo lo ya guardado
  pertenece a la unidad principal de su dueño, que es la única que existía
  al crearse), `NOT NULL`. `flask db heads` debe dar `1 (head)`.
- [x] Actualizar `app/services/planilla.py`: todas las funciones que
  escriben (`añadir_turno`, `establecer_estado_dia`, `marcar_saliente`,
  `guardar_nota_dia`, ...) y leen (`get_turnos_mes`, `get_estados_mes`,
  `get_salientes_mes`, `get_notas_mes`, `dias_sin_cumplimentar`,
  `franjas_trabajadas_en_fecha`) para aceptar/filtrar por `unidad` además
  de `usuario`.
- [x] Actualizar `app/routes/planilla.py::index` y el resto de rutas del
  blueprint para pasar `unidad_activa` a esas funciones.
- [x] Revisar `publicar_mes`/`despublicar_mes`/`PlanillaMes` — decidir si
  la publicación de la planilla también pasa a ser por unidad (un
  `PlanillaMes` por `(usuario, anyo, mes, unidad)` en vez de por
  `(usuario, anyo, mes)`) o si sigue siendo global al mes. Dado que
  "publicada" controla si los compañeros ven la disponibilidad, y la
  visibilidad ya es por unidad/grupo, **probablemente también debe pasar a
  ser por unidad** — confírmalo con un test antes de decidir.
- [x] Revisar `app/services/compat_planilla_persistente.py` y
  `app/services/volcar_cambios.py` (dependen de la planilla) por si asumen
  una sola unidad.
- [x] `pytest --testmon` en verde.
- [x] Verificar en navegador: usuario con 2 unidades, rellena planilla
  distinta en cada una, cambia el selector y confirma que el visor
  del mes cambia junto con la unidad activa.

## Paso 2 — Selector de unidad en `documentos-cambio` al crear una hoja de cambio

- [x] Tests de `app/routes/documento_cambio.py::nueva`: usuario con 2
  unidades, comprobar que puede elegir con cuál de ellas crea la hoja
  (`unidad_id` en el form o query string), que los compañeros/franjas
  ofrecidos corresponden a la unidad elegida, y que si envía una unidad a
  la que no pertenece devuelve 403 (mismo patrón que
  `unidad_activa_o_403`).
- [x] Sustituir en `app/routes/documento_cambio.py` los usos de
  `current_user.grupo_intercambio` / `current_user.categoria_id` (12
  apariciones: líneas ~40-41, 79, 95, 208, 263, 291, 310, 390, 472, 526,
  714 en la versión actual) por la unidad elegida/activa, aplicando el
  mismo criterio que dejó documentado el Paso 5 de `USUARIOS_MULTI.md`:
  **7 de los 11 casos originales eran "MUST change" (flujo de cambio
  normal) y 4 eran "DEFER" (código específico de supervisora, pendiente de
  decisión de diseño sobre cómo interactúa multi-unidad con supervisión —
  revisa si esa decisión ya se puede tomar ahora o sigue diferida)**.
  Funciones afectadas: `_companeros_disponibles`,
  `_hojas_pendientes_encadenables`, `_franjas_disponibles`,
  `_get_documento_validado`, `nueva`, `turnos_disponibles`,
  `registrar_papel`.
- [x] Plantilla `app/templates/documento_cambio/nueva.html` (o como se
  llame la del formulario de alta): añadir el mismo patrón de selector de
  unidad que ya existe en `documento_cambio/supervisora.html` /
  `planilla/planilla.html`, visible solo si `unidades|length > 1`, y que
  al cambiar recargue la página con `unidad_id` para refrescar la lista de
  compañeros/franjas ofrecidos.
- [x] `DocumentoCambio.unidad_id` pasa a guardarse con la unidad elegida
  en el formulario (ya existe la columna, solo cambia de dónde sale el
  valor).
- [x] `pytest --testmon` en verde.
- [x] Verificar en navegador: usuario con 2 unidades crea una hoja de
  cambio en cada una y comprueba que cada una queda asociada a la unidad
  correcta (compañeros/franjas ofrecidos, y en la vista de supervisora de
  cada unidad aparece la hoja correspondiente).

## Paso 3 — "Mis cambios publicados": columna de unidad + bandeja única etiquetada

- [ ] Tests: crear publicaciones para un usuario con 2 unidades (una en
  cada una) y comprobar que `main.index` las devuelve todas juntas, cada
  una con su unidad de origen accesible en el contexto de plantilla.
- [ ] Añadir columna `unidad_id` (FK a `unidad.id`, migración de 3 pasos)
  a `PublicacionCambio` (`app/models/publicacion.py`), backfill con
  `usuario.unidad_id`.
- [ ] `app/routes/publicaciones.py`: al crear una publicación (`nueva` y
  cualquier otro punto de creación), guardar `unidad_id` = unidad activa
  del usuario en ese momento (reutilizar `unidad_activa_o_403` /
  `session["unidad_activa_id"]`, mismo patrón que el resto del código
  multi-unidad) en vez de inferirla de `current_user.unidad`.
- [ ] Sustituir el resto de usos de `current_user.unidad` /
  `current_user.categoria_id` en `app/routes/publicaciones.py` (8 casos:
  líneas ~62, 223, 370, 464-465, 604-605, 608 en la versión actual —
  publicar, editar, me-interesa, contraoferta) por la unidad de la
  publicación afectada / la unidad activa del usuario según corresponda en
  cada caso (revisar caso a caso: al *filtrar qué puede ver/aceptar* un
  usuario se usa su unidad activa; al *identificar de qué unidad es una
  publicación ya existente* se usa la columna nueva, no la unidad
  principal del autor).
- [ ] `app/routes/main.py::index` (dashboard): sin cambios de filtrado
  (sigue mostrando todas las publicaciones del usuario, decisión del
  Paso 0), pero pasar a la plantilla la unidad de cada publicación.
- [ ] `app/templates/main/dashboard.html`: mostrar el nombre de la unidad
  junto a cada tarjeta de publicación, **solo si `current_user` pertenece
  a más de una unidad** (mismo criterio que notificaciones).
- [ ] `pytest --testmon` en verde.
- [ ] Verificar en navegador: usuario con 2 unidades publica un cambio en
  cada una desde `/planilla` (tras el Paso 1) o `/cambios`, y comprueba en
  `/` (dashboard) que ambas aparecen con su etiqueta de unidad correcta.

## Paso 4 — Resto de la deuda de la auditoría: `publicaciones.py`, `busquedas.py`, `unidad.py`

(Los 8 casos de `publicaciones.py` ya se cubren en el Paso 3 si se hace en
el mismo paso; si se prefiere separarlo, muévelos aquí.)

- [ ] `app/routes/busquedas.py:32` — validación de franja en búsquedas
  guardadas: sustituir `current_user.grupo_intercambio.id` por la unidad
  activa correspondiente al contexto de la búsqueda guardada.
- [ ] `app/routes/unidad.py` (5 casos: líneas ~27, 38, 46, 74, 87 en la
  versión actual) — configuración de turnos/franjas de la unidad: revisar
  si esta pantalla es "de la unidad activa" (un usuario con 2 unidades
  configura franjas de cada una por separado, necesita selector) o si de
  hecho solo tiene sentido para supervisoras/admin de una unidad concreta
  (en cuyo caso puede que no aplique el patrón de unidad activa sino el de
  `unidad_supervisada_o_403` que ya usa `documento_cambio/supervisora.html`).
- [ ] Tests para cada cambio, `pytest --testmon` en verde.
- [ ] Verificar manualmente los flujos tocados.

## Paso 5 — Cierre

- [ ] Pasar la suite completa una única vez (el resto de pasos usa
  `pytest --testmon`).
- [ ] Actualizar `PROGRESS.md` cerrando esta fase y anotando que los 21
  casos "MUST change" de la auditoría de `docs/USUARIOS_MULTI.md` (Paso 5)
  ya están resueltos, referenciando este documento.
- [ ] Revisar que no queda código muerto de la UI anterior a los
  selectores nuevos.
