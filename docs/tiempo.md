# Plan de trabajo — latencia en producción (2026-08-05)

> Origen: reporte de usuario ("rechazar un cambio a 3", aplicar tipo de día a
> varios días en `/planilla`, y abrir "Mis cambios" van muy lentos en
> producción; peor en Android que en PC; el tiempo varía mucho para la misma
> operación). Investigación hecha en `main` (rama con acceso a Railway
> production) el 2026-08-05.

## Cómo usar este plan
- Cada paso indica: contexto mínimo a leer, criterio de aceptación (test) y
  alcance del commit.
- Antes de empezar un paso: crea un worktree desde `staging`.
- Al terminar un paso: todos los tests en verde (`pytest --testmon`), commit
  atómico, PR contra `staging`, marca la casilla aquí y añade la fecha.
- No hace falta leer los demás pasos ni el resto de este documento para
  ejecutar uno — cada uno se basta a sí mismo, salvo que se indique lo
  contrario.

## Decisión de diseño ya tomada — no usar procesamiento en segundo plano
Se evaluó mover alguna de estas operaciones a background jobs (p. ej. con una
cola) en vez de bloquear al usuario. Se descarta como primera línea de
solución: los cuellos de botella identificados abajo son arreglables de forma
síncrona (ver Paso 2 y Paso 4) y añadir infraestructura de cola sería
sobre-ingeniería para el volumen de tráfico actual (~6.5 peticiones/día según
los datos de Sentry). El envío de email y de push ya son asíncronos (hilo
daemon) desde el fix anterior — no hace falta más async por ahora. Si tras
completar este plan alguna operación sigue siendo pesada de forma inherente
(no por un bug), se puede reconsiderar puntualmente para esa operación
concreta, no como patrón general.

## Datos de partida (Sentry, producción, ventana 90 días, 2026-08-03)
| Endpoint | Peticiones | p50 | p95 | p99 |
|---|---|---|---|---|
| `main.index` (dashboard) | 47 | 192ms | **5078ms** | 8009ms |
| `main.cambios` ("Mis cambios") | 28 | 341ms | **3982ms** | 4226ms |
| `planilla.index` | 3 | 205ms | **2978ms** | 3224ms |
| `matches.rechazar` | 1 | 2525ms | 2525ms | 2525ms |
| `auth.api_unidades` (lookup simple) | 12 | 28ms | 660ms | 662ms |
| `auth.api_ciudades` (lookup simple) | 9 | 81ms | 1050ms | 1258ms |
| `static` / `pwa.manifest` (sin lógica) | 217 / 75 | 0ms | 0-1ms | 0-3.5ms |

Dato clave: incluso endpoints triviales (`auth.api_unidades`, `auth.api_ciudades`,
simples SELECT de catálogo) tienen p95 de 660-1250ms, muy por encima de su p50.
Esto no se explica por consultas lentas ni por falta de índices (ver Paso 4):
apunta a un coste de **establecer conexión a la base de datos** que se paga en
picos, coherente con el tráfico tan bajo de la app (huecos largos entre
peticiones > `pool_recycle=280`) y con la queja de "el tiempo varía mucho para
la misma operación".

---

## Paso 1 — Arreglar `PYTHONUNBUFFERED` para que los access logs lleguen a Railway
- [ ] Completado (fecha: ______)

**Contexto a leer:** `Procfile` (línea `--access-logfile - --access-logformat
...`), variables de entorno del servicio `web` en producción.

**Problema:** el `Procfile` ya emite un log de acceso por petición con tiempo
de respuesta (`%(D)s`us), pero **no aparece nunca en `railway logs`**. Se
verificó haciendo `curl` a `/health` y comprobando que la petición nunca
aparece en los logs, segundos después. La causa más probable es que Python
usa buffering de bloque en stdout cuando la salida no es una TTY (el caso de
Railway), así que gunicorn escribe las líneas pero no se vacían al collector
de logs. No se encontró la variable `PYTHONUNBUFFERED` configurada en el
servicio `web` de producción.

**Qué hacer:** añadir `PYTHONUNBUFFERED=1` a las variables de entorno del
servicio `web` en producción (y en staging, por consistencia) vía
`railway variables --service web --environment production --set PYTHONUNBUFFERED=1`
(confirmar con el usuario antes de aplicar, es un cambio de config en
producción). Redeploy y verificar con un `curl` de prueba que la petición
aparece en `railway logs` con su tiempo de respuesta.

**Por qué este paso primero:** sin esto no hay forma barata de conseguir
datos reales de latencia por petición en producción (que hacen falta para
verificar el Paso 4 y para monitorizar el resultado de los Pasos 2 y 3). Es
un cambio de configuración, no de código: no necesita worktree ni tests.

**Alcance del commit:** ninguno (solo config de Railway). Si se decide fijar
la variable también en `Procfile` o en algún script de arranque para que
quede versionado, ese cambio va en un commit aparte, mínimo.

---

## Paso 2 — Elimina los commits N+1 al aplicar un tipo de día a varios días en `/planilla`
- [ ] Completado (fecha: ______)

**Contexto a leer:** `app/routes/planilla.py` (`rango_aplicar`,
`multiples_aplicar`), `app/services/planilla.py` (`añadir_turno`,
`establecer_estado_dia`).

**Problema (causa raíz confirmada por lectura de código):** `rango_aplicar` y
`multiples_aplicar` iteran sobre la lista de días seleccionados y llaman a
`establecer_estado_dia()` / `añadir_turno()` una vez por día. Cada una de esas
funciones hace su propio `db.session.commit()` dentro del bucle: aplicar un
tipo de día a, por ejemplo, 20 días dispara 20 commits (20 round-trips a la
base de datos, cada uno con su propio `fsync` de WAL), en vez de 1. Esto
explica directamente la lentitud reportada en `/planilla` y por qué **varía
tanto** (escala con el número de días seleccionados).

**Criterio de aceptación:**
- Test que selecciona varios días (p. ej. 10) y aplica un tipo de día vía
  `rango_aplicar` (o `multiples_aplicar`), y verifica que `db.session.commit`
  se llama **una sola vez** para toda la operación (usar un mock/spy sobre
  `db.session.commit`, o medir el número de queries con
  `sqlalchemy.event` / `assert_num_queries` si ya existe ese helper en el
  proyecto).
- Test de regresión: aplicar el tipo de día a un solo día sigue funcionando
  igual que antes (mismo resultado en `estado_dia_planilla` / `turno_planilla`).
- Test de que un fallo a mitad del lote (p. ej. un día inválido) no deja
  cambios a medias (o decide y documenta el comportamiento esperado: todo o
  nada, vs. mejor esfuerzo — revisar qué espera `especificacion-app-cambio-turnos.md`
  si dice algo al respecto; si no dice nada, todo-o-nada es lo más seguro).

**Cómo:** mover el `db.session.commit()` fuera del bucle, a `rango_aplicar` /
`multiples_aplicar` (un solo commit al final, tras procesar todos los días).
`añadir_turno()` y `establecer_estado_dia()` dejan de comitear internamente
cuando se llaman desde estos flujos — revisar si se llaman también desde
otros sitios que sí necesiten su propio commit (p. ej. aplicar un solo día
suelto) para no romperlos; si es así, puede hacer falta un parámetro tipo
`commit=True` por defecto, o extraer una variante interna sin commit
reutilizada por ambos casos. Mantenlo simple: no introduzcas una capa de
"unit of work" genérica si con mover el commit basta.

**Alcance del commit:** solo `app/services/planilla.py` y
`app/routes/planilla.py`, y sus tests.

---

## Paso 3 — `matches.rechazar` (y `confirmar`/`desconfirmar`) no deberían pagar el coste completo de `main.index` en el redirect
- [ ] Completado (fecha: ______)

**Contexto a leer:** `app/routes/matches.py` (`rechazar`, `confirmar`,
`desconfirmar`), `app/routes/main.py::index` (la vista a la que redirigen).

**Problema:** rechazar/confirmar/desconfirmar un match terminan con
`redirect(url_for("main.index"))`. `main.index` es, con diferencia, el
endpoint más lento de toda la app (p95=5078ms, p99=8009ms — ver tabla de
Sentry arriba). Parte de la lentitud percibida al "rechazar un cambio a 3" es
en realidad la recarga completa del dashboard después, no la operación de
rechazo en sí (que en la lectura de código no muestra un cuello de botella
propio: un bucle sobre pocas participaciones, notificaciones vía push ya
asíncrono, un único commit).

**Este paso depende de que `main.index` ya sea rápido.** Si el Paso 4 (más
abajo) reduce su p95 significativamente, puede que este paso deje de ser
necesario — medir primero con datos reales del Paso 1 antes de invertir aquí.
Si sigue siendo lento tras el Paso 4, opciones a valorar (no decidir a priori,
evaluar cuál encaja mejor con la especificación y el resto de la UI):
- Redirigir a una vista más ligera (p. ej. solo la pestaña relevante) en vez
  de recalcular todo `main.index`.
- Responder con una redirección que el navegador pueda pintar con caché breve
  o con un fragmento actualizado vía JS, evitando el full-page reload.

**Criterio de aceptación:** definir una vez elegida la opción — como mínimo,
un test de que la latencia de `matches.rechazar` end-to-end (incluyendo lo
que carga después) baja de forma medible, y que la UX sigue mostrando
confirmación del rechazo.

**Alcance del commit:** a definir según la opción elegida; evitar tocar la
lógica de negocio de `rechazar_match`/`confirmar_participacion` si el
problema es solo el destino del redirect.

---

## Paso 4 — Confirmar y mitigar el coste de reconexión a la base de datos
- [ ] Completado (fecha: ______)

**Depende de:** Paso 1 (necesita logs de acceso reales para medir antes/después).

**Contexto a leer:** `config.py` (`ProductionConfig.SQLALCHEMY_ENGINE_OPTIONS`:
`pool_pre_ping=True`, `pool_recycle=280`), tabla de latencias de Sentry
arriba (nota el patrón en `auth.api_unidades`/`auth.api_ciudades`: consultas
triviales con p95 10-20x su p50).

**Hipótesis a verificar:** con tráfico tan bajo (~6.5 peticiones/día), los
huecos entre peticiones consecutivas casi siempre superan `pool_recycle=280`
segundos, así que casi cada petición paga el coste de abrir una conexión
nueva a Postgres (potencialmente con handshake TLS) en vez de reutilizar una
conexión cálida del pool. Esto explicaría por qué **hasta consultas triviales**
tienen p95 muy por encima de su p50, y por qué la variación de latencia es tan
grande "para el mismo tipo de operación" (depende de si tocó reconectar o no).

**Cómo verificar (usar los datos del Paso 1, no repetir con curl manual):**
comparar en los access logs el tiempo de respuesta de peticiones que llegan
tras un hueco largo de inactividad vs. peticiones que llegan poco después de
otra. Si la hipótesis es correcta, las primeras serán sistemáticamente más
lentas independientemente del endpoint.

**Si se confirma, mitigaciones a valorar (elegir la más simple que resuelva
el problema, no combinar todas):**
- Subir `pool_recycle` (Railway solo cierra conexiones ociosas "pasado un
  rato" — confirmar el umbral real en vez de asumir 280s; puede que un valor
  mayor siga siendo seguro y reduzca reconexiones).
- Un *warm-up* ligero: un ping periódico a la base de datos (p. ej. cron de
  Railway cada pocos minutos) para mantener al menos una conexión viva y
  evitar que el pool completo quede frío. Ojo: esto no es "background job"
  de negocio (no está prohibido por la decisión de diseño de arriba), es solo
  mantenimiento de infraestructura.
- Revisar si el plan de Postgres en Railway tiene algún comportamiento de
  bajo consumo/cold start propio (poco probable en plan Pro, pero
  descartarlo con datos antes de seguir).

**Criterio de aceptación:** no es un fix de código con TDD tradicional —
es un cambio de configuración validado con datos de latencia reales
(access logs del Paso 1) antes/después. Documentar la comparación en este
mismo archivo o en `docs/sentry.md` al cerrar el paso.

**Alcance del commit:** cambio de configuración (`config.py` y/o variables de
Railway) y, si aplica, un pequeño script/cron de warm-up. Nada más.

---

## Paso 5 — Revisar si 3 workers sync de gunicorn siguen siendo suficientes
- [ ] Completado (fecha: ______)

**Nota:** `docs/plan-fixes-auditoria-sentry.md` (Paso 7) ya cerró una primera
revisión de este punto el 2026-08-03, concluyendo que no había datos
suficientes (Sentry acababa de empezar a recoger eventos). Con más tráfico
acumulado y con los access logs ya funcionando (Paso 1), retomarlo con datos
reales en vez de cerrarlo por falta de datos otra vez.

**Contexto a leer:** `Procfile`, sección "Pendiente"/comparación de latencia
en `docs/sentry.md`, access logs de gunicorn del Paso 1.

**Qué mirar:** si hay picos de tráfico concurrente (p. ej. cambios de turno a
la misma hora, varios usuarios a la vez) que satura los 3 workers y hace que
unas peticiones esperen detrás de otras — eso explicaría que la misma
operación tarde muy distinto según el momento del día, independientemente de
los fixes de los Pasos 2-4.

**Criterio de aceptación:** con datos de al menos una semana de access logs,
concluir si hay evidencia de cola/saturación (peticiones que se solapan en el
tiempo y una de ellas tarda mucho más de lo esperado para su tipo). Si la hay,
definir el siguiente paso concreto (subir el número de workers es la opción
más simple — verificar antes que la memoria/CPU del plan de Railway lo
soporta). Si no la hay, cerrar el punto documentando la conclusión.

**Alcance del commit:** solo documentación si se cierra sin cambios; si se
sube el número de workers, cambio mínimo en `Procfile`.

---

## Paso 6 — Diferencia de latencia Android vs. PC
- [ ] Completado (fecha: ______)

**Contexto a leer:** `app/static/sw.js` (service worker), plantillas
`dashboard.html` y `cambios.html`.

**Nota:** esta es la única causa reportada que probablemente **no** sea un
problema de backend/Railway — los Pasos 1-5 deberían mejorar la latencia para
todos los dispositivos por igual. Si tras completarlos la diferencia
Android/PC persiste, esto apunta a algo del lado del cliente (parseo/render
en un dispositivo menos potente, o red móvil con más latencia/jitter que
wifi/cable).

**Cómo investigar (solo si persiste tras los pasos anteriores):**
- Medir el tamaño de la respuesta HTML de `main.index` y `main.cambios`
  renderizada (puede ser grande si incluye muchas publicaciones inline).
- Revisar si hay JS pesado ejecutándose de forma síncrona en el load de esas
  páginas.
- Si es viable, reproducir con las devtools de Chrome en modo "Remote
  debugging" desde un Android real conectado por USB, comparando el timeline
  de red vs. el de PC.

**Criterio de aceptación:** a definir según lo que se encuentre — puede que
este paso termine siendo solo un documento de conclusión ("no hay diferencia
significativa una vez arreglado el backend") en vez de un cambio de código.

**Alcance del commit:** a definir.

---

## Paso 7 — Índice que falta en `turno_cedido.publicacion_id` (impacto bajo, coste bajo)
- [ ] Completado (fecha: ______)

**Contexto a leer:** modelo `TurnoCedido` en `app/models.py`, uso en
`main.cambios()` (`app/routes/main.py`).

**Problema:** `turno_cedido` no tiene índice en `publicacion_id`, columna que
se usa para el join con `publicacion_cambio` en "Mis cambios". Con el volumen
actual (7148 filas) un seq scan es barato en sí mismo, así que **no se espera
que este índice, por sí solo, resuelva la lentitud reportada** — el resto de
índices relevantes (`publicacion_cambio.usuario_id`, `.estado`, `.tipo`,
`turno_planilla` con su índice compuesto, `usuario.categoria_id`) ya existen
y están bien puestos. Aun así, es una mejora barata y sin riesgo que conviene
aplicar igualmente, sobre todo pensando en que el volumen de datos crecerá.

**Criterio de aceptación:** migración Alembic (`flask db migrate`, seguir el
flujo obligatorio de `CLAUDE.md`: nunca escribir el archivo a mano, verificar
`flask db heads` = 1) que añade el índice. No hace falta test de
comportamiento (es un índice, no cambia resultados), pero sí verificar que
`flask db upgrade`/`downgrade` funcionan limpios.

**Alcance del commit:** solo la migración.

---

## Resumen de prioridad sugerida
1. Paso 1 (barato, desbloquea medir todo lo demás)
2. Paso 2 (causa raíz confirmada, mayor impacto directo sobre la queja de `/planilla`)
3. Paso 4 (hipótesis con más indicios, afecta a *toda* la app, no solo a un endpoint)
4. Paso 5 (con datos reales del Paso 1)
5. Paso 3 (puede que ya no haga falta si el Paso 4 baja `main.index`)
6. Paso 7 (barato, sin prisa)
7. Paso 6 (solo si el problema persiste tras el resto)
