import logging
import time

from flask import g, has_request_context, request

logger = logging.getLogger("db_timing")


def init_db_timing(app, engine):
    """Instrumentación temporal de diagnóstico (docs/rapido_cambio.md, Paso 1).

    Separa, por petición, el tiempo de crear una conexión física nueva a
    Postgres (TLS handshake) del resto del tiempo de la petición, para
    confirmar si la reconexión es el coste dominante en producción.
    Se activa con DB_TIMING_ENABLED=true; retirar tras el Paso 3 del plan.
    """
    if not app.config.get("DB_TIMING_ENABLED"):
        return

    # La app no configura logging.basicConfig ni handlers propios, así que
    # sin esto los mensajes INFO se descartan silenciosamente por el nivel
    # WARNING por defecto del logger raíz (nunca llegarían a los logs de
    # Railway/gunicorn).
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    original_creator = engine.pool._creator

    def timed_creator(*args, **kwargs):
        start = time.monotonic()
        conn = original_creator(*args, **kwargs)
        elapsed_ms = (time.monotonic() - start) * 1000
        if has_request_context():
            g.db_connect_ms = getattr(g, "db_connect_ms", 0.0) + elapsed_ms
        logger.info("db_timing physical_connect_ms=%.1f", elapsed_ms)
        return conn

    engine.pool._creator = timed_creator

    original_connect = engine.pool.connect

    def timed_connect(*args, **kwargs):
        start = time.monotonic()
        conn = original_connect(*args, **kwargs)
        elapsed_ms = (time.monotonic() - start) * 1000
        if has_request_context():
            g.db_checkout_ms = getattr(g, "db_checkout_ms", 0.0) + elapsed_ms
        return conn

    engine.pool.connect = timed_connect

    @app.before_request
    def _db_timing_start():
        g.request_start = time.monotonic()
        g.db_connect_ms = 0.0
        g.db_checkout_ms = 0.0

    @app.after_request
    def _db_timing_end(response):
        start = getattr(g, "request_start", None)
        if start is not None:
            total_ms = (time.monotonic() - start) * 1000
            connect_ms = getattr(g, "db_connect_ms", 0.0)
            checkout_ms = getattr(g, "db_checkout_ms", 0.0)
            logger.info(
                "db_timing endpoint=%s total_ms=%.1f connect_ms=%.1f "
                "checkout_ms=%.1f rest_ms=%.1f",
                request.endpoint, total_ms, connect_ms, checkout_ms,
                total_ms - connect_ms,
            )
        return response
