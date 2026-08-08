# Plan: latencia alta (~10s) al editar una publicación de cambio en producción

## Contexto del problema
En Railway producción, guardar la edición de un cambio (`POST /publicaciones/<id>/editar`)
tarda casi 10 segundos. Caso observado: edición de Guillén del Barrio, 2026-08-07.

## Hipótesis (análisis de código, a confirmar con datos reales — ver Paso 1)

La ruta `editar()` en `app/routes/publicaciones.py:365-420`, tras guardar los turnos,
ejecuta en el mismo request **6 búsquedas de matching** sobre las candidatas activas:

```python
candidatas = candidatas_activas_para(pub)
buscar_matches_para(pub, candidatas)
buscar_cadenas_3_para(pub, candidatas)
buscar_cadenas_4_para(pub, candidatas)
buscar_cadenas_parciales_4_para(pub, candidatas)
buscar_sinteticas_que_coinciden_con(pub)
buscar_avisos_interes_para(pub, candidatas)
```

`candidatas_activas_para` sí calcula la lista de publicaciones candidatas **una sola vez**
con `selectinload` (evita N+1 ahí). Pero **cada una de las 6 funciones vuelve a calcular
desde cero**, para las mismas candidatas, los conjuntos `_cedidos_abiertos(c)` /
`_aceptados(c)` (`app/matching/service.py`) — no hay caché entre funciones dentro del
mismo request.

El punto más sospechoso es `_aceptados()` (`app/matching/service.py:46-64`): por cada
`TurnoAceptado` con `cualquier_franja=True`, llama a `_franjas_del_grupo(pub)`
(`app/matching/service.py:40-43`), que **no tiene ningún caché** y ejecuta dos consultas
nuevas a BD cada vez:
```python
db.session.get(Usuario, pub.usuario_id).unidad   # posible query si no está en sesión
FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id).all()
```
Si hay N candidatas con turnos `cualquier_franja=True` y esto se repite en las 6 funciones
de matching, son potencialmente decenas/cientos de round-trips extra a Postgres. En
Railway (latencia de red real, no localhost) cada round-trip puede costar 20-50ms, lo que
cuadra con los ~10s observados.

Además, `crear_match_cadena_3` / `crear_match_cadena_4` hacen **dos `db.session.commit()`**
cada uno (uno tras crear notificaciones, otro tras `registrar_evento`), sumando round-trips
si en la edición se generan varios matches de golpe.

**Esto es una hipótesis a confirmar con datos, no una conclusión.** El paso 1 es
instrumentar y medir antes de tocar nada.

## Objetivo
Bajar el tiempo de `POST /publicaciones/<id>/editar` a un rango normal (idealmente <1s)
sin cambiar el comportamiento del motor de matching (mismos matches, mismo orden,
mismas notificaciones).

---

## Plan de trabajo

- [x] **Paso 0 — Preparación**
  - Se trabaja en el worktree `worktree-cambios-lentos`, creado desde `main`, en la rama
    `worktree-worktree-cambios-lentos` (el usuario pidió explícitamente worktree para
    esta tarea, sustituyendo la excepción original de commitear directo en `main`).
  - Árbol de trabajo limpio al partir de `main` (commit base `16bb06d`).

- [x] **Paso 1 — Instrumentar y confirmar la causa antes de optimizar** (2026-08-07)
  - Añadir un test (o script puntual) que cuente las queries SQL ejecutadas durante
    `editar_publicacion` + las 6 búsquedas de matching, usando el evento
    `sqlalchemy.event.listen(engine, "before_cursor_execute", ...)` o
    `flask_sqlalchemy` query counting, sobre un escenario con varias candidatas activas
    (algunas con `cualquier_franja=True`).
  - Registrar el número de queries antes de tocar código. Si el número es alto (decenas
    o cientos) para pocas candidatas, confirma la hipótesis de N+1.
  - Si es posible, revisar logs de producción (Railway) del momento de la edición real de
    Guillén del Barrio para corroborar cuántas candidatas activas había en su grupo de
    intercambio ese día (cuantas más candidatas, más se nota el N+1).
  - Documentar el resultado en este archivo (sección "Hallazgos", añadida en este paso).
  - Commit: `test: instrumenta conteo de queries en editar_publicacion para diagnosticar latencia`

- [x] **Paso 2 — Cachear `_franjas_del_grupo` por request** (2026-08-07)
  - Los franjas de un grupo de intercambio no cambian dentro de un mismo request. Cachear
    el resultado de `FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id).all()`
    por `grupo_id`, con un caché simple de proceso/petición (p. ej. diccionario a nivel de
    módulo con reset explícito, o `flask.g`).
  - Test primero: verificar que dos llamadas a `_franjas_del_grupo` con el mismo `grupo_id`
    dentro del mismo request solo ejecutan 1 query (usando el contador del Paso 1).
  - Cuidado: invalidar/no reutilizar el caché entre requests distintos (usar `flask.g`,
    que vive solo durante el request, es la opción más segura).
  - Commit: `perf: cachea franjas del grupo por request para evitar queries repetidas`

- [x] **Paso 3 — Calcular `cedidos`/`aceptados` de todas las candidatas una sola vez por request** (2026-08-07)
  - Extraer a la ruta `editar()` (y a `publicar()` si comparte el mismo patrón — revisar)
    el cálculo de `{pub.id: _cedidos_abiertos(pub)}` y `{pub.id: _aceptados(pub)}` para
    `publicacion` + todas las `candidatas`, una única vez.
  - Pasar esos diccionarios ya calculados a las 6 funciones de búsqueda en vez de que cada
    una vuelva a computarlos. Esto implica cambiar la firma de `buscar_matches_para`,
    `buscar_cadenas_3_para`, `buscar_cadenas_4_para`, `buscar_cadenas_parciales_4_para`,
    `buscar_sinteticas_que_coinciden_con` y `buscar_avisos_interes_para` para aceptar
    (opcionalmente) estos mapas precalculados, con el mismo patrón que ya usan para
    `candidatas` (`_resolver_candidatas`, ver `app/matching/service.py:115-121`).
  - Test primero: mismos matches/avisos que antes del cambio (usar los tests existentes en
    `tests/` de matching, y `pytest --testmon`), y verificar con el contador de queries del
    Paso 1 que el número de queries baja significativamente.
  - Ojo: `buscar_sinteticas_que_coinciden_con` opera sobre una lista de "sintéticas"
    distinta de `candidatas`, no sobre las mismas — su caché de cedidos/aceptados es
    independiente, solo comparte el de `publicacion`.
  - Commit: `perf: reutiliza cedidos/aceptados precalculados entre las búsquedas de matching`

- [x] **Paso 4 — Reducir commits duplicados en creación de matches** (2026-08-07)
  - `crear_match_directo`, `crear_match_cadena_3`, `crear_match_cadena_4` y
    `crear_pub_sintetica` hacen más de un `db.session.commit()` en el mismo flujo
    (p. ej. uno tras crear notificaciones y otro tras `registrar_evento`). Revisar si se
    pueden fusionar en un único commit sin cambiar el comportamiento (mismo orden de
    escritura, mismas garantías si algo falla a mitad).
  - Test primero: los tests existentes de creación de matches deben seguir en verde.
  - Commit: `perf: fusiona commits redundantes al crear matches`

- [x] **Paso 5 — Medir el resultado con datos reales** (2026-08-07)
  - Repetir la instrumentación del Paso 1 sobre el mismo escenario (mismo número de
    candidatas) y comparar el número de queries y el tiempo total antes/después.
  - Si tras los pasos 2-4 la mejora no es suficiente, evaluar mover el recálculo de
    matching a background (ya existe el patrón de `threading.Thread(daemon=True)` para
    push, ver `app/push/sender.py:243-259`) — pero esto es un cambio de comportamiento
    (el usuario ya no vería sus matches al instante tras guardar) y requiere decisión
    explícita del usuario antes de implementarlo. No implementar sin confirmación.
  - Documentar los números en este archivo.

- [ ] **Paso 6 — Verificar en producción**
  - Desplegar a Railway (staging primero si existe, luego producción) y medir el tiempo
    real de `POST /publicaciones/<id>/editar` para un usuario con varias publicaciones
    candidatas activas en su grupo.
  - Confirmar con el usuario que el tiempo baja a un rango aceptable.
  - Actualizar `PROGRESS.md` si esta tarea pasa a formar parte del flujo de trabajo por
    pasos general del proyecto.

---

## Notas
- No tocar el comportamiento del motor de matching (`app/matching/engine.py`): esto es
  una tarea de rendimiento, no de lógica de negocio. Los tests de
  `tests/test_flujos_criticos.py` y los de matching son el criterio de que nada se rompió.
- Ejecutar siempre `pytest --testmon` entre pasos, según la convención del proyecto
  (`CLAUDE.md`).
- Si en el Paso 1 la instrumentación NO muestra un número alto de queries, descartar la
  hipótesis de N+1 y investigar otras causas antes de seguir con los pasos 2-4 (p. ej.
  latencia de red Railway↔Postgres en sí, cold start del worker, otro middleware, etc.).

## Hallazgos

### Paso 1 (2026-08-07)
Test añadido: `tests/test_latencia_editar.py::test_editar_publicacion_selects_crecen_con_candidatas_cualquier_franja`.
Usa el fixture `query_counter` ya existente en `tests/conftest.py` (cuenta
sentencias `SELECT` vía el evento `after_cursor_execute` de SQLAlchemy) sobre
una petición HTTP real `POST /publicaciones/<id>/editar`, variando el número
de candidatas activas (mismo grupo/categoría) con un turno aceptado
`cualquier_franja=True`.

Resultado:
| Candidatas activas (cualquier_franja=True) | SELECTs ejecutados |
|---|---|
| 1 | 31 |
| 6 | 82 |

Crecimiento de ~10.2 SELECTs por candidata adicional (51 SELECTs extra para 5
candidatas extra). **Confirma la hipótesis de N+1**: cada candidata con
`cualquier_franja=True` dispara `_franjas_del_grupo()` (2 queries) de forma
repetida en varias de las 6 funciones de búsqueda de matching, sin ningún
caché entre ellas ni dentro del mismo request. Con el volumen de candidatas
que puede darse en un grupo de intercambio real, esto es coherente con los
~10s observados en producción sobre Railway (latencia de red real por
round-trip, no localhost).

Se procede con el Paso 2 (cachear `_franjas_del_grupo` por request) tal como
estaba previsto — no hace falta descartar la hipótesis ni investigar otras
causas.

### Paso 2 (2026-08-07)
`_franjas_del_grupo` ahora cachea su resultado en `flask.g` (diccionario
`_franjas_del_grupo_cache`, indexado por `grupo_id`), que vive solo durante el
request. Test añadido: `test_franjas_del_grupo_se_cachea_por_request`, que
llama dos veces a `_franjas_del_grupo` con el mismo grupo dentro del mismo
`app.test_request_context()` y comprueba que la segunda llamada no ejecuta
ningún SELECT nuevo.

Resultado en el escenario del Paso 1 (`test_editar_publicacion_selects_crecen_con_candidatas_cualquier_franja`):

| Candidatas activas (cualquier_franja=True) | SELECTs antes del Paso 2 | SELECTs después del Paso 2 |
|---|---|---|
| 1 | 31 | 27 |
| 6 | 82 | 52 |

El crecimiento por candidata adicional baja de ~10.2 a ~5 SELECTs. Sigue
habiendo N+1 (varias de las 6 funciones de búsqueda recalculan `_cedidos_abiertos`/`_aceptados`
para las mismas candidatas), lo que aborda el Paso 3.

### Paso 3 (2026-08-07)
Se añadió `precalcular_cedidos_aceptados(publicacion, candidatas)` en
`app/matching/service.py`, llamado una única vez en la ruta `editar()` (y en
`publicar()` y en la ruta de contraoferta, que comparten el mismo patrón)
justo después de `candidatas_activas_para(...)`, antes de que las 6 búsquedas
de matching empiecen a crear matches. Las 6 funciones (`buscar_matches_para`,
`buscar_cadenas_3_para`, `buscar_cadenas_4_para`,
`buscar_cadenas_parciales_4_para`, `buscar_sinteticas_que_coinciden_con`,
`buscar_avisos_interes_para`) aceptan ahora `cedidos_map`/`aceptados_map`
opcionales (mismo patrón que `_resolver_candidatas`, vía el nuevo helper
`_resolver_mapas`); si no se pasan, cada una los calcula igual que antes, así
que no rompe ningún test ni llamada existente (p. ej. el comando CLI
`rematch` en `app/__init__.py`, que sigue llamando sin estos mapas).

Motivo por el que hacía falta precalcular *antes* de las búsquedas y no solo
compartir el cálculo entre ellas: `db.session.commit()` (que ocurre dentro de
las funciones de creación de matches, ejecutadas entre búsqueda y búsqueda)
expira por defecto las instancias ORM ya cargadas, así que sin este
precálculo cada búsqueda posterior volvía a lanzar queries para releer
`turnos_cedidos`/`turnos_aceptados` de `publicacion` y de cada candidata.

Test añadido: `test_editar_publicacion_selects_crecen_poco_con_candidatas_tras_paso_3`,
que repite el escenario del Paso 1/2 y comprueba que el crecimiento de
SELECTs por candidata adicional es menor que 2.

Resultado en el mismo escenario:

| Candidatas activas (cualquier_franja=True) | SELECTs antes del Paso 3 | SELECTs después del Paso 3 |
|---|---|---|
| 1 | 27 | 23 |
| 6 | 52 | 28 |

El crecimiento por candidata adicional baja de ~5 a **1.0 SELECT**. Suite
completa (`pytest --testmon`) en verde.

### Paso 4 (2026-08-07)
Las 4 funciones de creación de matches hacían 2 `db.session.commit()` cada
una: uno tras crear las notificaciones (y, en las cadenas, tras los envíos de
push), y otro tras el/los `registrar_evento`. Se fusionaron en un único
commit final por función, sin cambiar el orden de escritura:

- `crear_match_directo`, `crear_match_cadena_3`, `crear_match_cadena_4`: se
  eliminó el commit intermedio tras crear las `Notificacion`; el commit final
  (tras `registrar_evento`) queda como único punto de persistencia. Es seguro
  porque SQLAlchemy hace autoflush por defecto (no hay override de
  `autoflush` en el proyecto), así que los objetos añadidos siguen siendo
  visibles para queries posteriores dentro de la misma transacción aunque no
  se haga commit todavía. Además, tanto `enviar_push_condicional`
  (`app/push/sender.py`) como `registrar_evento` (`app/services/eventos.py`)
  atrapan sus propias excepciones y nunca propagan un fallo que dejara la
  transacción a medias.
- `crear_pub_sintetica`: mismo patrón, pero aquí el commit intermedio vivía
  dentro de `notificar_busquedas_guardadas` (`app/services/busquedas_guardadas.py`),
  una función también usada de forma independiente desde `publicar_cambio`
  (que sí debe seguir comiteando ella sola). Se le añadió un parámetro
  `commit=True` (por defecto) para poder llamarla con `commit=False` desde
  `crear_pub_sintetica` y hacer un único commit final después, sin tocar el
  comportamiento de `publicar_cambio`.

Test primero: `tests/test_commits_matching.py`, con un fixture
`commit_counter` que monkeypatchea `sqlalchemy.orm.Session.commit` para
contar invocaciones. Los 4 tests (uno por función) fallaban en rojo
(`assert 2 == 1`) antes del cambio y pasan en verde después, sin tocar
ningún otro test existente.

Suite completa (`pytest --testmon`): 201 passed, 0 failed.

### Paso 5 (2026-08-07)
Test añadido: `tests/test_latencia_editar.py::test_medir_tiempo_editar_con_15_candidatas`,
que mide SELECTs y tiempo de respuesta real de `POST /publicaciones/<id>/editar`
con 15 candidatas activas (`cualquier_franja=True`), un número más cercano a un
grupo de intercambio real que el 1/6 usado en los Pasos 1-3.

Para tener un "antes" comparable, se creó un worktree temporal en el commit
`bda75a9` (justo tras el Paso 1: instrumentación presente, ninguna optimización
aplicada) con el mismo test, y se ejecutó 3 veces en cada versión sobre la
misma BD Postgres local:

| Versión | SELECTs (15 candidatas) | Tiempo (3 ejecuciones) |
|---|---|---|
| Antes (commit `bda75a9`, sin optimizar) | 173 | 129.8 / 136.3 / 143.2 ms |
| Después (commit `0dd867e`, Pasos 2-4 aplicados) | 39 | 64.1 / 69.8 / 64.3 ms |

**Resultado:** 77.5% menos SELECTs (173 → 39) y ~2x menos tiempo en local
(~136 ms → ~66 ms de media). La reducción de tiempo en local es modesta porque
Postgres corre en localhost (round-trip ~submilisegundo); en Railway, donde el
diagnóstico del Paso 1 estimó 20-50 ms por round-trip de red entre el
dyno y Postgres, los 134 SELECTs eliminados suponen entre 2.7 s y 6.7 s menos
solo por ese concepto — coherente con reducir sustancialmente (aunque quizá
no necesariamente por debajo de 1s) los ~10s observados en producción con
Guillén del Barrio.

Suite completa (`pytest --testmon`): en verde, sin regresiones.

**Conclusión:** los Pasos 2-4 reducen el N+1 de forma sustancial y verificable
(SELECTs por candidata adicional: ~10.2 antes → ~1.0 después; ver Hallazgos
Paso 1 y Paso 3). No se dispone de una medición de producción antes/después
porque requeriría desplegar el cambio primero (Paso 6). Si tras el despliegue
el tiempo real en Railway sigue siendo alto, la opción de mover el
recálculo de matching a background sigue en pie como siguiente alternativa,
pero requiere decisión explícita del usuario (cambia el comportamiento
observado: el usuario ya no vería sus matches al instante).
