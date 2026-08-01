# Estado del desarrollo

## Fase actual
Fase 13 — Eliminar publicaciones caducadas desde "Mis cambios", plan completo
en `docs/BORRAR_CADUCADOS.md`.

## Paso actual / siguiente paso
Plan completado. PR #55 contra staging creado.

## Últimos pasos completados
- [x] Paso 5 (`docs/BORRAR_CADUCADOS.md`) — PR #55 contra staging: https://github.com/guillen1989/turnero/pull/55
- [x] Paso 4 (`docs/BORRAR_CADUCADOS.md`) — tests de integración: `test_dashboard_caducada_muestra_botones_eliminar` y `test_dashboard_activos_no_muestra_botones_eliminar_caducadas` en `tests/test_dashboard.py`
- [x] Paso 3 (`docs/BORRAR_CADUCADOS.md`) — frontend en
  `app/templates/main/dashboard.html`: botón "Eliminar todos" en el header
  (visible solo en pestaña caducada con publicaciones), modal de confirmación
  `modal-eliminar-todos-caducadas` con su JS. El bloque `pub-acciones`
  ahora se muestra también en caducadas (`{% if pub.esta_activa() or estado_filtro == 'caducada' %}`),
  pero los botones "Editar" y "Compartir" solo aparecen para publicaciones activas.
- [x] Paso 2 (`docs/BORRAR_CADUCADOS.md`) — ruta backend
  `POST /publicaciones/eliminar-caducadas` (`eliminar_caducadas` en
  `app/routes/publicaciones.py`): borra todas las publicaciones `caducada`
  del usuario autenticado reutilizando `eliminar_publicacion`, y redirige a
  `main.index` con `?estado=caducada`. Tests nuevos en
  `tests/test_editar_eliminar_publicacion.py`: requiere login, y aislamiento
  por usuario (borra solo las caducadas propias, deja intactas las
  `abierta` propias y las `caducada` de otro usuario). `pytest --testmon` en
  verde.
- [x] Paso 1 (`docs/BORRAR_CADUCADOS.md`) — test
  `test_eliminar_borra_publicacion_caducada` en
  `tests/test_editar_eliminar_publicacion.py`: confirma que
  `POST /publicaciones/<id>/eliminar` ya borra correctamente una
  publicación en estado `caducada` (la ruta no comprueba `estado`, solo
  propiedad). No hizo falta tocar backend.

## Historial completo
El registro detallado de fases y pasos anteriores está en
`PROGRESS_ARCHIVE.md`.

## Notas / decisiones / asunciones pendientes
- Contexto técnico completo del plan (rutas/plantillas existentes a
  reutilizar, precedente de "borrar todos" en avisos) está en la cabecera
  de `docs/BORRAR_CADUCADOS.md` — leer antes de cada paso.
- Nombre final de ruta/endpoint (`eliminar_caducadas`,
  `/publicaciones/eliminar-caducadas`) es orientativo, ajustable al
  implementar el Paso 2 si hace falta.
