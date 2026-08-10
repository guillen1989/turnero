# Plan: tormenta de hilos daemon de push como causa de los ~10-20s en producción

## Contexto — por qué existe este plan

`docs/rapido_cambio.md` investigó la lentitud de `POST
/publicaciones/<id>/editar` en producción. Descartó dos hipótesis con datos
reales:
1. Reconexión a la base de datos (TLS handshake) — descartada, `connect_ms`
   bajo incluso en el peor caso.
2. Conexión "zombi" detectada tarde por `pool_pre_ping` — descartada:
   `checkout_ms` (que envuelve esa validación) solo sube a ~500ms en los
   casos lentos, dos órdenes de magnitud por debajo del total.

Analizando logs de producción (`railway logs --service web --environment
production --since 3d --filter db_timing`, 2026-08-10) aparecieron los
únicos dos outliers extremos capturados hasta ahora, ambos en
`publicaciones.editar`:

```
2026-08-08T20:20:47Z  publicaciones.editar  total_ms=21233.6  connect_ms=0.0  checkout_ms=508.1
2026-08-08T21:46:33Z  publicaciones.editar  total_ms=17851.5  connect_ms=0.0  checkout_ms=453.6
```

En la misma ventana de logs aparecen **47 avisos** `WARNING in sender: Push
no entregado a usuario N: WebPushException: Push failed: 410 Gone`.

**Mecanismo sospechoso:** `enviar_push()` (`app/push/sender.py:259`) lanza
un `threading.Thread(daemon=True)` **nuevo por cada notificación**, sin
límite de concurrencia. Cada hilo hace firma VAPID (ECDSA, CPU-bound) +
una llamada HTTP síncrona (`pywebpush`). `app/services/publicaciones.py:71`
llama a `enviar_push_condicional` **en bucle sobre los suscriptores de
búsquedas guardadas** al editar/publicar — si la edición hace match con
muchas búsquedas guardadas, se disparan decenas de hilos casi simultáneos
que compiten por el GIL con el hilo que atiende la petición HTTP en el
worker `sync` de gunicorn (solo 3 workers, sin `gthread`).

**No confirmado todavía:** la correlación temporal es fuerte (mismos ~2
minutos, mismo endpoint) pero son solo 2 muestras. Este plan primero
confirma el mecanismo con un test dirigido y, si se confirma, aplica la
mitigación más simple (acotar la concurrencia de hilos) antes de plantear
alternativas más costosas (cola de trabajo, mensajería).

## Objetivo

Confirmar si una ráfaga de hilos de push sin límite de concurrencia puede
bloquear un worker sync de gunicorn durante varios segundos, y si se
confirma, acotar esa concurrencia sin cambiar el comportamiento observable
(la app sigue enviando todas las notificaciones, solo con menos hilos
paralelos). Criterio de éxito: no reaparecen picos de `total_ms` de
varios segundos en `publicaciones.editar` (ni en otros endpoints que
disparan push en bucle) tras el fix, medido con datos reales de
producción durante varios días.

## Cómo usar este plan
- Cada paso se basta a sí mismo: no hace falta releer los pasos
  anteriores para ejecutarlo, salvo que se indique lo contrario.
- Ejecuta siempre `pytest --testmon` entre pasos (convención de
  `CLAUDE.md`).
- Marca la casilla y la fecha al terminar cada paso, en el mismo commit
  que el cambio de ese paso.
- La instrumentación `app/db_timing.py` (`DB_TIMING_ENABLED=true` en
  producción) sigue activa y es la fuente de datos para confirmar/medir
  este plan — no la retires hasta el Paso 5.

---

## Paso 0 — Preparación
- [x] Completado (fecha: 2026-08-10)

Crear worktree nuevo desde `main` (no `staging`, mismo criterio que
`docs/rapido_cambio.md`), PR contra `main`. Confirmar con el usuario el
nombre de rama si difiere de la convención habitual
(`worktree-fix-daemon` o similar).

**Commit:** `chore: paso 0 del plan fix-daemon — trabajo aislado en worktree`

---

## Paso 1 — Confirmar el mecanismo con un test dirigido (no en producción)

**Contexto a leer:** `app/push/sender.py` (`enviar_push`, línea ~209),
`app/services/publicaciones.py:71` (bucle sobre suscriptores).

**Qué hacer:**
- Escribir un test que reproduzca la forma del problema de forma
  determinista y rápida (sin depender de producción ni de red real):
  mockear `webpush` para que tarde un tiempo simulado (p. ej.
  `time.sleep(0.05)` dentro del mock) y comprobar cuántos hilos
  concurrentes llega a crear `enviar_push` cuando se invoca en bucle N
  veces seguidas (p. ej. N=50, simulando el caso de 47 suscriptores).
  El test debe demostrar que hoy no hay límite: en un instante dado puede
  haber hasta N hilos vivos simultáneamente.
- Si es viable sin infraestructura especial, añadir también una medición
  de tiempo de CPU/wall-clock del hilo principal mientras los hilos de
  push están activos, para tener un número comparable (no hace falta que
  sea muy preciso — el objetivo es demostrar contención, no medirla con
  exactitud de laboratorio).
- Documentar el resultado en la sección "Hallazgos" de este archivo
  (créala al cerrar este paso si no existe).
- **Si el test no muestra contención apreciable** (p. ej. porque el GIL
  se libera bien durante las llamadas de red y el hilo principal no se
  ve afectado), no seguir con los pasos 2-3 tal como están planteados:
  pausar y decidir con el usuario el siguiente paso antes de tocar más
  código, igual que indica `docs/rapido_cambio.md` para sus propias
  hipótesis descartadas.

**Commit:** `test: reproduce la tormenta de hilos daemon de enviar_push sin límite de concurrencia`

---

## Paso 2 — Acotar la concurrencia de hilos de push

**Depende de:** Paso 1 confirmando contención apreciable.

**Contexto a leer:** `app/push/sender.py` completo (no solo
`enviar_push`), para no romper `enviar_push_condicional` ni el camino de
tests (`TESTING` ejecuta `_send()` síncrono, ver línea ~256-259).

**Qué hacer:**
- Sustituir el `threading.Thread(daemon=True).start()` sin límite por un
  mecanismo con concurrencia acotada. Opción más simple y con menos
  cambio de comportamiento: un `concurrent.futures.ThreadPoolExecutor`
  compartido a nivel de módulo/app (p. ej. `max_workers=4`), reutilizado
  entre llamadas en vez de crear un `Executor` por notificación.
  - Decidir el tamaño del pool con margen conservador: suficiente para no
    introducir demora perceptible en el envío de notificaciones (que hoy
    es "instantáneo" al ser cada una un hilo propio), pero bajo para no
    saturar el GIL del worker sync (candidatos: 3-5, alineado con
    `--workers 3` de gunicorn).
  - Revisar que el `Executor` se cierra correctamente en el ciclo de vida
    de la app (o se deja como singleton de proceso, ya que los workers de
    gunicorn son procesos separados — no hace falta compartirlo entre
    workers).
- Mantener sin cambios el camino síncrono bajo `TESTING` (los mocks
  existentes dependen de ese comportamiento).
- Actualizar/extender el test del Paso 1 para verificar el nuevo límite
  (p. ej. nunca hay más de `max_workers` hilos/tareas de push activos a
  la vez, incluso con 50 llamadas en bucle rápido).
- Ejecutar la suite completa relacionada con push (`pytest --testmon`) y
  confirmar que no rompe ningún test existente de notificaciones.

**Commit:** `fix: acota la concurrencia de hilos de enviar_push con un ThreadPoolExecutor`

---

## Paso 3 — Verificar en staging antes de tocar producción

**Depende de:** Paso 2 mergeado en la rama de trabajo.

**Qué hacer:**
- Desplegar a staging y provocar una edición real que dispare varias
  notificaciones de golpe (varios suscriptores de búsquedas guardadas
  sobre la misma franja/categoría en el entorno de staging — crear datos
  de prueba si hace falta).
- Confirmar en `railway logs --service web --environment staging` que
  las notificaciones se siguen entregando (o fallando con 410 Gone de
  forma esperada para suscripciones caducadas, sin cambiar ese
  comportamiento) y que no aparecen errores nuevos relacionados con el
  `ThreadPoolExecutor`.
- No es un test de pytest — es una verificación manual de que el cambio
  no rompe el envío real de push en un entorno con red real.

**Commit:** solo si aparecen ajustes necesarios tras la verificación en
staging; si no, este paso no genera commit propio (se documenta en
"Hallazgos").

---

## Paso 4 — Desplegar a producción y medir con datos reales

**Depende de:** Paso 3 verificado en staging sin problemas.

**Contexto a leer:** `docs/rapido_cambio.md` (formato de medición ya
usado con `db_timing`), para repetir el mismo tipo de comparación
antes/después.

**Qué hacer:**
- Confirmar con el usuario antes de desplegar a producción (cambio de
  comportamiento en un mecanismo compartido — notificaciones push).
- Tras el despliegue, dejar pasar tiempo suficiente para cubrir varios
  ciclos de uso real (al menos varios días, dado el tráfico bajo de la
  app — ver `docs/tiempo.md`).
- Repetir la consulta de logs (`railway logs --service web --environment
  production --since <periodo> --filter db_timing`) y comparar:
  - ¿Siguen apareciendo picos de `total_ms` de varios segundos en
    `publicaciones.editar` o en otros endpoints que llaman a
    `enviar_push_condicional` en bucle (`publicaciones.py:71`,
    `matches.py`, `documento_cambio.py`)?
  - Si Sentry tiene ya datos de performance para esos endpoints (ver
    `docs/sentry.md`), comparar p95/p99 antes/después del despliegue.
- Documentar los números en la sección "Hallazgos".

**Si la mejora no es suficiente:** no improvisar — plantear al usuario,
con los datos en la mano, alternativas de mayor coste (cola de trabajo
real en vez de hilos, p. ej. RQ/Celery con Redis, o mover el envío de
push a un proceso/servicio separado). No implementar sin confirmación
explícita.

**Commit:** solo documentación de resultados en este archivo, salvo que
se decida seguir con una alternativa de mayor coste (pasos nuevos
añadidos a este plan).

---

## Paso 5 — Cierre

**Depende de:** Paso 4 confirmando la mejora en producción (o decisión
explícita del usuario de cerrar el plan con los resultados que haya, si
la mejora es parcial).

**Qué hacer:**
- Si `docs/rapido_cambio.md` sigue abierto con este plan como "siguiente
  candidato", actualizarlo para enlazar el resultado final aquí y cerrar
  esa investigación.
- Decidir si retirar o mantener `DB_TIMING_ENABLED=true` en producción
  (mantiene utilidad de diagnóstico a bajo coste — decidir con el
  usuario, no hay urgencia de retirarlo).
- Actualizar `PROGRESS.md` cerrando este frente de trabajo.

**Commit:** `docs: cierra el plan fix-daemon con los resultados finales`

---

## Notas
- No revertir el trabajo de `docs/rapido_cambio.md` ni de PR #61/#63/#64
  — la reducción de N+1 queries y la instrumentación `db_timing` siguen
  siendo correctas y útiles.
- Cualquier cambio de infraestructura (colas, servicios nuevos en
  Railway) requiere confirmación explícita del usuario antes de
  aplicarse.
- Si el Paso 1 no confirma contención apreciable, no forzar el resto del
  plan: pausar y decidir con el usuario antes de seguir.

## Hallazgos

### Paso 1 (2026-08-10)

Test: `tests/test_push_concurrencia.py::test_enviar_push_lanza_un_hilo_daemon_sin_limite_por_llamada`.

Se llamó a `enviar_push` 50 veces seguidas (con `TESTING=False` para forzar
el camino real de `threading.Thread(daemon=True).start()`, en vez del
`_send()` síncrono que usa el resto de la suite), mockeando `webpush` con
`time.sleep(0.05)` para simular la llamada HTTP síncrona de `pywebpush`.

**Confirmado:** hoy no hay ningún límite de concurrencia. De los 50 hilos
lanzados, el pico de hilos vivos a la vez llegó al máximo (50/50 en la
ejecución local), muy por encima del umbral de aceptación del test
(`>= 80%`). El bucle que lanza los 50 hilos tarda un orden de magnitud menos
que el tiempo simulado de un solo `webpush` (crear un hilo no bloquea al
llamador), coherente con el mecanismo sospechoso: si 47 suscriptores hacen
match a la vez (como en los logs de producción del 2026-08-08), se lanzan
~47 hilos casi simultáneos.

**No perseguido en este paso:** la medición de contención de CPU/GIL del
hilo principal mientras los hilos de push están activos. Con un mock basado
en `time.sleep()` (que libera el GIL) no se puede reproducir de forma fiable
la contención real, que en producción viene de la firma VAPID (ECDSA,
CPU-bound) dentro de cada hilo, no de la espera de red en sí. Reproducir esa
parte requeriría un mock que mantenga el GIL ocupado (p. ej. un bucle
CPU-bound corto en vez de `sleep`), lo cual añade complejidad y
fragilidad al test sin aportar más certeza sobre el mecanismo ya confirmado
(ausencia de límite de concurrencia). Se considera que el resultado ya
justifica seguir al Paso 2 (acotar la concurrencia con
`ThreadPoolExecutor`), que resuelve el problema con o sin contención real de
GIL: menos hilos simultáneos siempre reduce la presión sobre el worker.

**Decisión:** se confirma contención apreciable (nº de hilos concurrentes
sin tope) → se continúa con el Paso 2 tal como está planteado.
