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
- Decidir si el modelo de `--workers 3` sync de gunicorn sigue siendo suficiente.
- Con Sentry en producción ya funcionando, revisar en unos días si aparecen datos de
  performance/transactions reales para poder repetir la comparación de latencia que esta
  auditoría no pudo hacer por falta de datos.

## Referencias
- PR del fix de email async + subida de sample rate: #52 (rama `worktree-async-email-sending`
  contra `staging`, commit `3660895`).
- `app/services/email.py`: `enviar_email_async()` — patrón de hilo daemon, igual que
  `enviar_push()` en `app/push/sender.py`.
