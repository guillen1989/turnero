# Plan: la edición de un cambio sigue tardando ~10s en producción tras el PR #61

## Por qué este plan reemplaza a `docs/cambio.md`

`docs/cambio.md` (fusionado en PR #61, ver commits `0dd867e`, `54c0857`,
`7b2d67f`) partía de la hipótesis de que el problema era **N+1 queries**
dentro de las 6 búsquedas de matching de `editar()`. Esa hipótesis se
confirmó y se arregló: el propio plan documentó la mejora medida en local
(173 → 39 SELECTs, 136ms → 66ms). **Pero el usuario confirma que en
producción el tiempo de `POST /publicaciones/<id>/editar` sigue sin bajar.**
Esto descarta el número de queries como causa dominante en producción — hay
que buscar en otro sitio.

### La pista que ya teníamos y no se conectó con `cambio.md`

`docs/tiempo.md` (plan anterior, más amplio, del 2026-08-05) ya investigó la
lentitud general de la app en producción con datos reales de Sentry y
encontró algo que apunta directamente a la causa real:

> "Dato clave: incluso endpoints triviales (`auth.api_unidades`,
> `auth.api_ciudades`, simples SELECT de catálogo) tienen p95 de
> 660-1250ms, muy por encima de su p50. Esto no se explica por consultas
> lentas ni por falta de índices: apunta a un coste de **establecer
> conexión a la base de datos** que se paga en picos."

Es decir: **el coste dominante en producción no es "cuántas queries", es
"cuántas veces hay que abrir una conexión nueva (TLS handshake) a
Postgres"**. Con tráfico tan bajo (~6.5 peticiones/día, gap medio entre
peticiones de ~3.7 horas según ese mismo documento), casi cada petición
paga ese coste de reconexión, sea de 1 query o de 173.

El Paso 4 de `docs/tiempo.md` ya proponía mitigar esto y **se aplicó a
medias**: `config.py` (`ProductionConfig.SQLALCHEMY_ENGINE_OPTIONS`) subió
`pool_recycle` de 280s a 3600s (1h) con `pool_pre_ping=True`. El propio
comentario en el código ya deja constancia de que **esto es insuficiente**:

```python
# ... pool_recycle=3600 mantiene las conexiones vivas hasta 1 h en el pool...
# El valor anterior de 280s forzaba reconexión en casi cada petición porque
# el gap medio entre peticiones es de ~3.7 h.
```

3600s (1h) sigue siendo **muy inferior** a 3.7h de gap medio entre
peticiones. Subir `pool_recycle` no resuelve nada si casi ninguna petición
llega dentro de esa ventana: la conexión ya se ha cerrado (por el lado de
Postgres/Railway, no por SQLAlchemy) mucho antes de que llegue la siguiente
petición. `pool_pre_ping` detecta la conexión muerta y abre una nueva —
pero eso es exactamente el coste que queríamos evitar.

**Esto explica perfectamente por qué el PR #61 no cambió nada medible en
producción:** reducir queries de 173 a 39 solo ahorra el tiempo de las
queries en sí (round-trips sobre una conexión ya abierta). Si el coste
real son ~10s de establecer la conexión (TLS handshake + autenticación
contra Postgres gestionado de Railway) que se paga **una vez por
petición** independientemente de cuántas queries se ejecuten después,
reducir queries no toca esa parte del tiempo total.

## Objetivo

Confirmar con datos reales de producción (no benchmarks locales) que el
coste dominante es la reconexión a la base de datos, y aplicar una
mitigación que sí sea eficaz para el patrón de tráfico real de esta app
(muy bajo, picos espaciados). Criterio de éxito: `POST
/publicaciones/<id>/editar` baja de forma medible y sostenida en
producción (no solo en local), idealmente a menos de 1-2s.

## Cómo usar este plan
- Cada paso se basta a sí mismo: no hace falta releer los pasos
  anteriores para ejecutar uno, salvo que se indique lo contrario.
- Ejecuta siempre `pytest --testmon` entre pasos (convención de
  `CLAUDE.md`).
- Marca la casilla y la fecha al terminar cada paso, en el mismo commit
  que el cambio de ese paso.
- No revertir el trabajo del PR #61 (la reducción de N+1 sigue siendo
  correcta y barata de mantener); este plan añade la mitigación que
  faltaba, no sustituye la anterior.

---

## Paso 0 — Preparación
- [x] Completado (fecha: 2026-08-08)

Confirmado con el usuario: esta tarea se trabaja en un worktree nuevo
desde `main` (no `staging`), con PR contra `main`. Worktree creado en
`.claude/worktrees/worktree-rapido-cambio`, rama
`worktree-worktree-rapido-cambio`.

---

## Paso 1 — Confirmar con datos reales que el coste es la conexión, no las queries ni el matching
- [x] Completado (fecha: 2026-08-08) — hipótesis **descartada**, ver sección "Hallazgos" al final de este documento. Pausa para decidir siguiente paso con el usuario.

**Contexto a leer:** `config.py` (`ProductionConfig.SQLALCHEMY_ENGINE_OPTIONS`),
`docs/tiempo.md` (Paso 1 y Paso 4), `docs/cambio.md` en el historial de git
(`git show a188c71:docs/cambio.md`) para no repetir el diagnóstico de N+1
ya hecho.

**Qué hacer:**
- Añadir instrumentación temporal (logging, no un test — esto se mide en
  producción/staging real) que separe, dentro de `POST
  /publicaciones/<id>/editar`, dos tiempos distintos:
  1. Tiempo de **obtener una conexión del pool** (checkout). SQLAlchemy
     expone los eventos `checkout`/`checkin`/`connect` de
     `sqlalchemy.event` sobre el engine — usar `connect` y `checkout` para
     medir cuánto se tarda en abrir una conexión física nueva vs.
     reutilizar una del pool.
  2. Tiempo del resto de la petición (queries + matching + template).
  Loguear ambos con suficiente contexto (timestamp, endpoint) para poder
  correlacionarlos después.
- Desplegar este logging a **staging** primero (`railway logs --service
  web --environment staging` para verificar que llegan), y si hace falta
  reproducir el patrón de tráfico bajo, a producción (confirmar con el
  usuario antes de desplegar a producción, aunque sea solo logging).
- Provocar una edición real (o varias, espaciadas varias horas, para que
  se parezca al patrón real de tráfico) y comparar: ¿el tiempo de
  `connect` es el que domina, o no?
- Documentar los números en la sección "Hallazgos" de este archivo
  (añadirla al cerrar este paso).
- Si la hipótesis **no** se confirma (el tiempo de conexión es bajo y el
  resto domina), no seguir con los pasos 2-3 tal cual: parar aquí,
  documentar qué se descarta y decidir con el usuario el siguiente paso
  antes de tocar más código.

**Commit:** `test: instrumenta tiempo de conexión vs. resto de la petición en editar_publicacion` (o `chore:` si es solo logging temporal sin test formal — decidir según si el logging se queda o se retira después).

---

## Paso 2 — Mitigar la reconexión con un warm-up periódico

**Depende de:** Paso 1 confirmando la hipótesis.

**Contexto a leer:** `docs/tiempo.md` (Paso 4, opciones de mitigación ya
evaluadas), `Procfile`, `app/routes/main.py` (endpoint `/health` — ya
existe pero no toca la base de datos, ver línea ~35).

**Por qué warm-up y no solo subir `pool_recycle` más:** subir
`pool_recycle` a un valor aún mayor no ayuda de fondo — el problema no es
cuánto tiempo SQLAlchemy *permite* que viva una conexión en su pool, sino
que **Postgres/Railway cierra las conexiones ociosas por su lado** mucho
antes de que llegue la siguiente petición real (gap medio ~3.7h). La
única forma de evitar pagar el coste de reconexión en la petición del
usuario es que **algo mantenga al menos una conexión viva de forma
proactiva**, independientemente del tráfico real de usuarios.

**Qué hacer:**
- Añadir un endpoint ligero que fuerce un round-trip real a la base de
  datos (p. ej. `SELECT 1`), distinto de `/health` (que no toca la BD) —
  o modificar `/health` para que sí lo haga, si no se usa para otra cosa
  que dependa de que sea instantáneo. Decidir cuál de las dos opciones
  encaja mejor revisando si `/health` se usa como healthcheck de Railway
  (en ese caso, no tocarlo: crear uno nuevo, p. ej. `/health/warmup` o
  similar).
- Configurar un **Cron Job de Railway** (servicio de tipo cron en el
  proyecto `turnero`) que llame a ese endpoint cada pocos minutos (elegir
  un intervalo bien por debajo del timeout real de Postgres/Railway del
  lado servidor — si no se conoce ese valor, usar algo conservador como
  cada 3-4 minutos y ajustar con datos si hace falta). Confirmar con el
  usuario antes de crear infraestructura nueva en Railway (esto es un
  cambio de infraestructura compartida, no solo código).
- Verificar que el cron efectivamente llega (`railway logs`) y que las
  conexiones no vuelven a quedar frías entre pings.

**Criterio de aceptación:** no es un test de pytest — es una verificación
de infraestructura. Documentar en este archivo que el cron está desplegado
y corriendo con éxito.

**Commit:** `feat: añade endpoint de warm-up para mantener viva la conexión a Postgres` (el cron en sí se configura en Railway, no en el repo, salvo que el proyecto use `railway.json` para definirlo — comprobar si aplica).

---

## Paso 3 — Medir el resultado en producción con datos reales

**Depende de:** Paso 2 desplegado y corriendo un tiempo razonable (al
menos varias horas, para cubrir varios ciclos del cron y alguna petición
real de usuario).

**Qué hacer:**
- Repetir la medición del Paso 1 (tiempo de conexión vs. resto) tras el
  warm-up, comparando antes/después con los mismos números.
- Si hay acceso a Sentry (ver `docs/tiempo.md`, tabla de latencias),
  comparar el p95/p99 de `publicaciones.editar` (y de paso, de
  `auth.api_unidades`/`auth.api_ciudades`, que también mostraban el mismo
  patrón) antes y después.
- Confirmar con el usuario que la edición de un cambio real en producción
  ya no tarda ~10s.
- Documentar los números finales en la sección "Hallazgos".

**Si la mejora no es suficiente:** no improvisar aquí — plantear al
usuario, con los datos en la mano, las alternativas de mayor coste que
`docs/tiempo.md` y `docs/cambio.md` ya dejaron identificadas y
explícitamente pendientes de decisión:
- Un *connection pooler* gestionado (p. ej. PgBouncer, si Railway lo
  ofrece como add-on) delante de Postgres, para que el "handshake caro"
  se pague una vez entre el pooler y Postgres, no en cada conexión de
  la app.
- Mover el recálculo de matching (las 6 búsquedas + creación de matches)
  a un hilo daemon en segundo plano, como ya se hace con push/email (ver
  `app/push/sender.py`), devolviendo la respuesta al usuario antes de que
  termine el matching. **Esto cambia el comportamiento observable** (el
  usuario ya no ve sus matches al instante tras guardar) — no
  implementar sin confirmación explícita, tal y como ya advertía
  `docs/cambio.md`.

**Commit:** solo documentación de los resultados en este archivo, salvo
que se decida seguir con una de las alternativas de arriba (en ese caso,
seguirían como pasos nuevos añadidos a este plan, no como parte de este
commit).

---

## Notas
- No revertir ni deshacer el trabajo del PR #61: la reducción de N+1
  queries sigue siendo una mejora real y barata de mantener, solo que no
  era la causa dominante del problema reportado.
- Cualquier cambio de infraestructura en Railway (cron, add-ons) requiere
  confirmación explícita del usuario antes de aplicarse — no son cambios
  de código reversibles con un `git revert`.
- Si en el Paso 1 la instrumentación contradice la hipótesis de
  conexión, no forzar el resto del plan: pausar y decidir con el usuario
  antes de seguir, igual que indicaba `docs/cambio.md` para su propia
  hipótesis de N+1.

## Hallazgos

### Paso 1 (2026-08-08) — Hipótesis de reconexión **descartada**

Instrumentación desplegada en staging (`app/db_timing.py`, envuelve
`engine.pool._creator` para medir `connect_ms` — tiempo de abrir una
conexión física nueva — por separado de `rest_ms` — resto de la
petición). Datos reales capturados vía `railway logs` tras provocar
peticiones GET reales a `/publicaciones/<id>/editar` (endpoint
`publicaciones.editar`) con sesión autenticada (cuenta demo de staging):

```
db_timing endpoint=publicaciones.editar total_ms=26.5  connect_ms=0.0  rest_ms=26.5
db_timing endpoint=publicaciones.editar total_ms=17.1  connect_ms=0.0  rest_ms=17.1
db_timing endpoint=publicaciones.editar total_ms=14.5  connect_ms=0.0  rest_ms=14.5
db_timing endpoint=publicaciones.editar total_ms=154.0 connect_ms=33.7 rest_ms=120.3
db_timing endpoint=publicaciones.editar total_ms=20.5  connect_ms=0.0  rest_ms=20.5
db_timing endpoint=publicaciones.editar total_ms=17.2  connect_ms=0.0  rest_ms=17.2
db_timing endpoint=publicaciones.editar total_ms=14.5  connect_ms=0.0  rest_ms=14.5
db_timing endpoint=publicaciones.editar total_ms=16.1  connect_ms=0.0  rest_ms=16.1
```

También se capturó una conexión física nueva aislada (`auth.login`, tras
redeploy con el pool vacío):

```
db_timing physical_connect_ms=8.3
```

**Conclusión:** incluso el caso con reconexión física real
(`connect_ms=33.7`) tarda decenas de milisegundos, no segundos. El
`total_ms` más alto observado es 154ms — dos órdenes de magnitud por
debajo de los ~10s reportados en producción. La hipótesis de
`docs/tiempo.md` ("el coste dominante es el TLS handshake/reconexión a
Postgres") **no se sostiene** con estos datos: abrir una conexión nueva
contra la Postgres gestionada de Railway es barato.

**Nota de contexto:** las peticiones de prueba se hicieron poco después
de un redeploy (pool recién creado), no tras un gap de ~3.7h como el
tráfico real. Aun así, el dato de `physical_connect_ms=8.3` mide
directamente el coste de abrir una conexión física — que es la misma
operación que ocurriría tras un gap largo — y ese coste es bajo
independientemente de cuándo se dispare. No hay margen realista para que
ese mismo `connect()` tarde ~10s solo por haber esperado más tiempo antes
de ejecutarse.

**Se descartan** los pasos 2-3 de este plan (warm-up periódico) tal como
estaban planteados, porque atacarían un coste que estos datos muestran
que no es el dominante. **Pendiente de decidir con el usuario** cuál es
el siguiente paso: los ~10s reportados en producción siguen sin
explicación confirmada — candidatos a investigar (no descartados ni
confirmados todavía): tiempo de cola/arranque de un worker de gunicorn
tras estar inactivo (cold start del proceso, no de la conexión),
latencia de red/DNS específica de producción vs. staging, o algo
específico del entorno de producción que no se reproduce en staging.
