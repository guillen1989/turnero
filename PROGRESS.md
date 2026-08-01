# Estado del desarrollo

## Fase actual
Fase 13 — Eliminar publicaciones caducadas desde "Mis cambios", plan completo
en `docs/BORRAR_CADUCADOS.md`.

## Paso actual / siguiente paso
Paso 2 completado. Siguiente: Paso 3 (`docs/BORRAR_CADUCADOS.md`) — frontend:
botones "Eliminar" (individual) y "Eliminar todos" en la pestaña Caducados
de `app/templates/main/dashboard.html`.

## Últimos pasos completados
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
