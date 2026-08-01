# Estado del desarrollo

## Fase actual
Fase 13 — Eliminar publicaciones caducadas desde "Mis cambios", plan completo
en `docs/BORRAR_CADUCADOS.md`.

## Paso actual / siguiente paso
Paso 1 completado. Siguiente: Paso 2 (`docs/BORRAR_CADUCADOS.md`) — ruta
backend `POST /publicaciones/eliminar-caducadas` (`eliminar_caducadas`) que
borra todas las publicaciones caducadas del usuario reutilizando
`eliminar_publicacion`, con tests de aislamiento por usuario y de
convivencia con publicaciones `abierta`.

## Últimos pasos completados
- [x] Paso 1 (`docs/BORRAR_CADUCADOS.md`) — test
  `test_eliminar_borra_publicacion_caducada` en
  `tests/test_editar_eliminar_publicacion.py`: confirma que
  `POST /publicaciones/<id>/eliminar` ya borra correctamente una
  publicación en estado `caducada` (la ruta no comprueba `estado`, solo
  propiedad). No hizo falta tocar backend. `pytest --testmon` en verde (16
  tests en el archivo).

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
