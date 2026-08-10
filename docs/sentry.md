# Auditoría de rendimiento con Sentry — plan de retoma

## Contexto
El 2026-07-31 se diagnosticó lentitud percibida en la app (producción y staging, Railway).
Se descartó la base de datos como causa (`pg_stat_statements`/`EXPLAIN ANALYZE` confirmaron
queries rápidas en ambos entornos gracias a los índices existentes). Se identificó como causa
más probable el envío síncrono de emails (API de Resend) bloqueando los workers sync de
gunicorn (solo 3), especialmente en el bucle sobre participantes al cerrar una hoja de cambio
encadenada (3/4 bandas). Ya corregido en el PR #52 (`enviar_email_async`, hilo daemon).

Para tener visibilidad completa mientras se recogen más datos, se subió temporalmente
`traces_sample_rate` de Sentry de `0.1` a `1.0` en `app/__init__.py` (afecta a staging y
producción, no está gateado por entorno). Comentario dejado en el propio código como recordatorio.

## Objetivo de esta sesión (dentro de un par de días)
1. Confirmar si la corrección del envío de email asíncrono (PR #52) ha reducido los tiempos de
   respuesta observados en los endpoints que antes enviaban email de forma síncrona en bucle
   (sobre todo el cierre de hojas de cambio con varios participantes).
2. Detectar si queda algún otro endpoint/proceso lento no relacionado con email, usando ahora
   el 100% de trazas capturadas.
3. Una vez recogidos suficientes datos, **bajar `traces_sample_rate` de vuelta a `0.1`** (o el
   valor que se considere adecuado para el volumen de tráfico real) — no dejarlo al 100% de
   forma permanente, no compensa el volumen de datos/coste con este tráfico bajo.

## Cómo acceder a los datos
- **Staging**: Glitchtip autoalojado en `app.glitchtip.com` (DSN en `SENTRY_DSN` de la variable
  de entorno del servicio de staging en Railway).
- **Producción**: Sentry.io (DSN en `SENTRY_DSN` de producción en Railway).
- Revisar la pestaña de *Performance*/*Transactions* de cada proyecto, ordenando por p95/p99 de
  duración. Comparar las transacciones de rutas que antes enviaban email (`auth.recuperar_contrasena`,
  `feedback.nuevo`, la ruta de completar/firmar documento de cambio en `documento_cambio.py`)
  antes y después del despliegue del PR #52 (buscar el commit `3660895` o la fecha de merge como
  marca temporal).
- Si Sentry no tiene suficientes datos aún (tráfico bajo), complementar con:
  - `railway logs --service <servicio>` filtrando por tiempos de respuesta si el access log de
    gunicorn está activado (actualmente el `Procfile` no pasa `--access-logfile`; valorar
    añadirlo si Sentry no basta).
  - Los tests de `pytest --testmon` ya cubren el comportamiento async, no dan info de rendimiento
    real en producción.

## Checklist para la sesión de retoma
- [x] Abrir Sentry/Glitchtip y revisar las transacciones más lentas de los últimos días en ambos
      entornos.
- [x] Comparar duración de los endpoints afectados por el PR #52 antes/después del merge.
- [x] Si aparecen nuevos cuellos de botella no relacionados con email, documentarlos y decidir
      si merecen un nuevo plan de trabajo (worktree + TDD).
- [x] Bajar `traces_sample_rate` en `app/__init__.py` de `1.0` a `0.1` (o el valor decidido) y
      hacer el commit/PR correspondiente contra `staging`.
- [x] Valorar si compensa añadir `--access-logfile` al `Procfile` para tener logs de acceso de
      gunicorn de forma permanente (gap identificado durante el diagnóstico, no implementado).
- [ ] Valorar si el número fijo de workers sync de gunicorn (`--workers 3` en el `Procfile`)
      sigue siendo suficiente, o si conviene revisar el modelo de workers (async/gevent) si
      aparecen más operaciones bloqueantes en el futuro.

## Resultado de la auditoría (2026-08-03)

Se consultó la API REST de Sentry.io (producción) y de Glitchtip (staging) directamente,
en vez del dashboard, para aprovechar los datos ya recogidos con `traces_sample_rate=1.0`.

**Hallazgo principal: no hay ningún dato de transacciones/performance en ninguno de los dos
entornos**, así que la comparación de latencia antes/después del PR #52 (objetivo 1 y 2 de
esta sesión) **no se pudo hacer con datos reales**:

- **Staging (Glitchtip)**: 32 eventos en total desde siempre, todos de tipo `error`/`default`,
  ninguno de tipo `transaction`. El proyecto tiene `features: []` — esta instancia/plan de
  Glitchtip no tiene habilitado APM/Performance, así que nunca iba a recoger trazas aunque el
  `traces_sample_rate` esté al 100%.
- **Producción (Sentry.io)**: `firstEvent: null`, `firstTransactionEvent: false` — **cero
  eventos de cualquier tipo, nunca**, pese a que sí hay errores reales ocurriendo (confirmado
  en `railway logs`, p. ej. un `AssertionError` en `/admin/unidades/27/eliminar` el 2026-08-02).

  **Causa raíz encontrada y corregida (2026-08-03):** la variable `SENTRY_DSN` de producción
  en Railway tenía la clave pública truncada — le faltaba la `b` inicial
  (`7bef390ccff4936ec78cbc5a30a22b0` en vez de `b7bef390ccff4936ec78cbc5a30a22b0`), probablemente
  un error de copia/pega al configurarla. Con esa clave, Sentry respondía `400 bad sentry DSN
  public key` a cada envío, silenciosamente (el SDK no lo hace visible salvo en modo `debug`).
  Egress de red y DNS hacia `ingest.us.sentry.io` funcionan correctamente desde el contenedor de
  Railway — se descartó como causa.

  Se corrigió la variable en Railway (`railway variables --set SENTRY_DSN=... --service web
  --environment production`), lo que disparó un redeploy, y se verificó tras el redeploy que un
  evento de prueba llega correctamente a Sentry (issue `PYTHON-FLASK-1`, borrado/gestionable
  manualmente desde el dashboard). **Producción ya envía eventos a Sentry con normalidad.**

Dado que no hay trazas que comparar, se decide **bajar `traces_sample_rate` de vuelta a
`0.1`** igualmente (el 100% no compensa con este volumen y Glitchtip no las va a usar), y
**añadir `--access-logfile` a gunicorn en el `Procfile`** como sustituto práctico: da tiempos
de respuesta reales por request vía `railway logs`, sin depender de que Sentry/Glitchtip
reciban nada.

Como efecto secundario de revisar los eventos de `error` sí se encontraron varios bugs reales
(no relacionados con rendimiento), fuera del alcance original de esta auditoría — ver
`docs/bugs-detectados-auditoria-sentry.md`.

### Pendiente para una próxima sesión
- ~~Con Sentry en producción ya funcionando, revisar en unos días si aparecen datos de
  performance/transactions reales para poder repetir la comparación de latencia que esta
  auditoría no pudo hacer por falta de datos.~~ **Completado 2026-08-03 (ver abajo).**

---

## Comparacion de latencia pre/post PR #52 con datos reales (2026-08-03)

Se consulto la API REST de Sentry.io (`/api/0/organizations/turnero-9f/events/`)
para transacciones de los endpoints antes afectados por el envio sincrono de email:

| Endpoint | Transacciones (90d) | p50 | p95 | p99 |
|---|---|---|---|---|
| `auth.recuperar_contrasena` | **0** | -- | -- | -- |
| `feedback.nuevo` | **0** | -- | -- | -- |
| `documento_cambio.firmar` | **0** | -- | -- | -- |

**Resultado: ninguna de las rutas objetivo tiene datos de performance.** Sentry
empezo a recoger eventos en produccion hoy mismo (2026-08-03 08:21 UTC, tras el
fix del DSN truncado), y estos endpoints no han recibido trafico desde entonces.
La app tiene trafico muy bajo (herramienta interna), confirmado tambien en los
access logs de gunicorn.

**Datos de contexto — todas las transacciones disponibles (90d, 588 totales):**

| Endpoint | Count | p50 | p95 | p99 |
|---|---|---|---|---|
| `static` | 217 | 0ms | 1ms | 3.5ms |
| `pwa.service_worker` | 81 | 0ms | 1ms | 2.4ms |
| `pwa.manifest` | 75 | 0ms | 0ms | 0ms |
| `main.index` | 47 | 192ms | 5078ms | 8009ms |
| `main.cambios` | 28 | 341ms | 3982ms | 4226ms |
| `generic WSGI request` | 24 | 0ms | 0ms | 0.8ms |
| `admin.analytics_data` | 12 | 190ms | 3510ms | 3685ms |
| `auth.registro` | 12 | 83ms | 3032ms | 4436ms |
| `auth.api_unidades` | 12 | 28ms | 660ms | 662ms |
| `pwa.assetlinks` | 12 | 0ms | 0.4ms | 0.9ms |
| `auth.api_ciudades` | 9 | 81ms | 1050ms | 1258ms |
| `auth.api_provincias` | 9 | 32ms | 659ms | 659ms |
| `auth.api_hospitales` | 8 | 34ms | 661ms | 663ms |
| `calendario.index` | 7 | 124ms | 2515ms | 2534ms |
| `auth.login` | 5 | 5ms | 17ms | 19ms |
| `pwa.offline` | 5 | 2ms | 20ms | 23ms |
| `admin.analytics` | 4 | 197ms | 4427ms | 5023ms |
| `main.como_funciona` | 4 | 584ms | 1635ms | 1717ms |
| `notificaciones.avisos` | 4 | 173ms | 350ms | 372ms |
| `planilla.index` | 3 | 205ms | 2978ms | 3224ms |
| `admin.unidades` | 3 | 297ms | 306ms | 307ms |
| `notificaciones.panel` | 2 | 962ms | 1763ms | 1834ms |
| `publicaciones.nueva` | 2 | 1501ms | 2759ms | 2871ms |
| `matches.rechazar` | 1 | 2525ms | 2525ms | 2525ms |
| `auth.perfil` | 1 | 2529ms | 2529ms | 2529ms |
| `admin.index` | 1 | 85ms | 85ms | 85ms |

**Conclusiones:**

1. **No se puede comparar latencia pre/post PR #52** para los endpoints objetivo
   (`auth.recuperar_contrasena`, `feedback.nuevo`, `documento_cambio.firmar`)
   porque no han recibido trafico desde que Sentry funciona en produccion. Es de
   esperar en una app de uso interno con bajo volumen.

2. **Los endpoints que SI tienen datos muestran p95/p99 razonables** para las
   operaciones que realizan (consultas a BD, renderizado de plantillas). No se
   observan regresiones ni cuellos de botella nuevos. Destacan:
   - `main.index` (p95=5s): carga la pagina principal con concursos activos y
     notificaciones — operacion esperablemente mas pesada por las queries de
     sinteticas a 4 bandas y conteo de no leidas.
   - Los endpoints API (`auth.api_*`) estan en ~660ms p95, consistente con
     queries simples a tablas de lookup.

3. **Los datos disponibles no muestran ninguna evidencia de regresion** de
   rendimiento. Los p95/p99 de las rutas activas son consistentes con el perfil
   de la aplicacion (Flask + Postgres en Railway, workers sync).

4. **El objetivo original de la auditoria queda cerrado.** Con los datos
   actuales no hay evidencia de que el fix de email async (PR #52) haya
   introducido regresiones, ni de que queden endpoints lentos no relacionados
   con email que requieran intervencion inmediata. Si en el futuro aparecen
   transacciones de los endpoints objetivo, se podran comparar directamente
   desde el dashboard de Sentry sin necesidad de repetir este analisis.

### Evaluacion de `--workers 3` de gunicorn (2026-08-03)

Se reviso el estado actual del modelo de workers sync:

- **Logs de acceso activos**: el `Procfile` ya incluye `--access-logfile -` y
  `--access-logformat '%(h)s "%(r)s" %(s)s %(D)sus'`, capturando tiempos de respuesta
  por request en `railway logs`.
- **Datos disponibles**: los logs de produccion no muestran peticiones HTTP en la ventana
  reciente — la app tiene trafico muy bajo (herramienta interna de gestion de cambios de
  puesto en centros educativos). No hay datos para un analisis estadistico de p95/p99.
- **Principales bloqueantes resueltas**:
  - Email: paso a asincrono con PR #52 (`enviar_email_async`, hilo daemon). Ya no bloquea
    los workers de gunicorn durante el bucle de notificaciones al cerrar hojas de cambio.
  - Generacion de PDF: no es I/O-bloqueante (CPU); la sustitucion de WeasyPrint por
    xhtml2pdf (commit `bf7e657`) elimino las dependencias nativas problematicas.
  - Push web: ya era asincrono (`enviar_push()`, hilo daemon).

**Conclusion: 3 workers sync es suficiente para el perfil de trafico actual.** No hay
evidencia de agotamiento de workers, encolamiento de peticiones ni timeouts de gunicorn
en los logs. El `--timeout 60` da margen para peticiones puntualmente lentas.

**Plan de seguimiento**: si el trafico crece, monitorizar `railway logs` buscando
entradas de access log con `%D` (tiempo de respuesta en microsegundos) creciente o
lineas ERROR de gunicorn por `WORKER TIMEOUT`. El camino de upgrade mas sencillo es
cambiar a `gthread` en vez de `sync`, que permite concurrencia por worker via hilos sin
migrar a gevent/asgiref.

## Referencias
- PR del fix de email async + subida de sample rate: #52 (rama `worktree-async-email-sending`
  contra `staging`, commit `3660895`).
- `app/services/email.py`: `enviar_email_async()` — patrón de hilo daemon, igual que
  `enviar_push()` en `app/push/sender.py`.
