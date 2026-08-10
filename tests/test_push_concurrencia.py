"""Paso 1 de docs/fix-daemon.md: reproduce de forma determinista y rápida el
mecanismo sospechoso -- enviar_push lanza un hilo daemon nuevo por cada
notificación, sin ningún límite de concurrencia."""
import json
import threading
import time
from unittest.mock import patch

from app.models import Categoria, insertar_categorias_semilla
from app.push.sender import enviar_push
from app.services.registro import registrar_usuario

SUBSCRIPTION = {
    "endpoint": "https://push.example.com/abc123",
    "keys": {"p256dh": "FAKE_P256DH", "auth": "FAKE_AUTH"},
}

# Orden de magnitud de los 47 avisos "410 Gone" vistos en producción junto a
# los picos de total_ms (ver docs/fix-daemon.md).
N_SUSCRIPTORES = 50
DURACION_SIMULADA_WEBPUSH = 0.05


def _usuario_con_sub(db, email):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    u = registrar_usuario("Test", email, "password123", "H1", "Urgencias", cat.id)
    u.push_subscription = json.dumps(SUBSCRIPTION)
    db.session.commit()
    return u


def test_enviar_push_lanza_un_hilo_daemon_sin_limite_por_llamada(app, db):
    """Llama a enviar_push N_SUSCRIPTORES veces seguidas (simulando el bucle
    de app/services/publicaciones.py:71 sobre suscriptores de búsquedas
    guardadas) y mide cuántos de los hilos daemon lanzados llegan a estar
    vivos a la vez. Si no hay límite, casi todos coinciden en el tiempo."""
    usuario = _usuario_con_sub(db, "carga@test.es")

    old_key = app.config.get("VAPID_PRIVATE_KEY")
    old_email = app.config.get("VAPID_CLAIM_EMAIL")
    old_testing = app.config.get("TESTING")
    app.config["VAPID_PRIVATE_KEY"] = "fake-key"
    app.config["VAPID_CLAIM_EMAIL"] = "admin@test.es"
    # Bajo TESTING=True (el valor real en el resto de la suite), enviar_push
    # ejecuta _send() síncronamente para que los mocks funcionen sin hilos.
    # Aquí lo desactivamos a propósito para reproducir el camino real de
    # producción (threading.Thread(daemon=True).start()).
    app.config["TESTING"] = False

    activos = 0
    pico_activos = 0
    lock = threading.Lock()

    def _webpush_lento(*args, **kwargs):
        nonlocal activos, pico_activos
        with lock:
            activos += 1
            pico_activos = max(pico_activos, activos)
        time.sleep(DURACION_SIMULADA_WEBPUSH)
        with lock:
            activos -= 1

    try:
        with patch("app.push.sender.webpush", side_effect=_webpush_lento):
            hilos_antes = set(threading.enumerate())

            inicio_bucle = time.monotonic()
            for _ in range(N_SUSCRIPTORES):
                enviar_push(usuario, "Título", "Cuerpo")
            duracion_bucle = time.monotonic() - inicio_bucle

            hilos_lanzados = set(threading.enumerate()) - hilos_antes

            limite = time.monotonic() + 5
            while any(h.is_alive() for h in hilos_lanzados) and time.monotonic() < limite:
                time.sleep(0.01)
    finally:
        app.config["VAPID_PRIVATE_KEY"] = old_key
        app.config["VAPID_CLAIM_EMAIL"] = old_email
        app.config["TESTING"] = old_testing

    assert len(hilos_lanzados) == N_SUSCRIPTORES, (
        "se esperaba un hilo daemon nuevo por cada llamada a enviar_push"
    )
    # Hoy no hay ningún límite de concurrencia: en el pico, prácticamente
    # todos los hilos lanzados coinciden en el tiempo. Tras el Paso 2 (pool
    # acotado, p. ej. max_workers=4), este número debería bajar drásticamente.
    assert pico_activos >= N_SUSCRIPTORES * 0.8, (
        f"pico de hilos concurrentes = {pico_activos} de {N_SUSCRIPTORES} "
        "lanzados -- se esperaba que casi todos coincidieran en el tiempo, "
        "confirmando que hoy no hay límite de concurrencia"
    )
    # Lanzar un hilo no bloquea al hilo que hace el bucle (a diferencia de un
    # pool acotado, donde llamada nº max_workers+1 esperaría). El bucle debe
    # completarse mucho antes de que el primer hilo termine su sleep.
    assert duracion_bucle < DURACION_SIMULADA_WEBPUSH * N_SUSCRIPTORES
