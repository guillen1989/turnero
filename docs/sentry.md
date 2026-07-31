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
- [ ] Abrir Sentry/Glitchtip y revisar las transacciones más lentas de los últimos días en ambos
      entornos.
- [ ] Comparar duración de los endpoints afectados por el PR #52 antes/después del merge.
- [ ] Si aparecen nuevos cuellos de botella no relacionados con email, documentarlos y decidir
      si merecen un nuevo plan de trabajo (worktree + TDD).
- [ ] Bajar `traces_sample_rate` en `app/__init__.py` de `1.0` a `0.1` (o el valor decidido) y
      hacer el commit/PR correspondiente contra `staging`.
- [ ] Valorar si compensa añadir `--access-logfile` al `Procfile` para tener logs de acceso de
      gunicorn de forma permanente (gap identificado durante el diagnóstico, no implementado).
- [ ] Valorar si el número fijo de workers sync de gunicorn (`--workers 3` en el `Procfile`)
      sigue siendo suficiente, o si conviene revisar el modelo de workers (async/gevent) si
      aparecen más operaciones bloqueantes en el futuro.

## Referencias
- PR del fix de email async + subida de sample rate: #52 (rama `worktree-async-email-sending`
  contra `staging`, commit `3660895`).
- `app/services/email.py`: `enviar_email_async()` — patrón de hilo daemon, igual que
  `enviar_push()` en `app/push/sender.py`.
