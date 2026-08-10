"""Paso 1 y Paso 2 de docs/fix-daemon.md: primero reproduce el mecanismo
sospechoso -- enviar_push lanzaba un hilo daemon nuevo por cada notificación,
sin ningún límite de concurrencia -- y luego confirma que el
ThreadPoolExecutor del Paso 2 acota esa concurrencia."""
import json
import threading
import time
from unittest.mock import patch

from app.models import Categoria, insertar_categorias_semilla
from app.push.sender import MAX_WORKERS_PUSH, enviar_push
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


def test_enviar_push_acota_concurrencia_con_pool(app, db):
    """Llama a enviar_push N_SUSCRIPTORES veces seguidas (simulando el bucle
    de app/services/publicaciones.py:71 sobre suscriptores de búsquedas
    guardadas) y mide cuántas ejecuciones de webpush llegan a estar activas
    a la vez. Tras el Paso 2, el ThreadPoolExecutor compartido acota ese
    pico a MAX_WORKERS_PUSH, en vez de lanzar un hilo sin límite por
    llamada."""
    usuario = _usuario_con_sub(db, "carga@test.es")

    old_key = app.config.get("VAPID_PRIVATE_KEY")
    old_email = app.config.get("VAPID_CLAIM_EMAIL")
    old_testing = app.config.get("TESTING")
    app.config["VAPID_PRIVATE_KEY"] = "fake-key"
    app.config["VAPID_CLAIM_EMAIL"] = "admin@test.es"
    # Bajo TESTING=True (el valor real en el resto de la suite), enviar_push
    # ejecuta _send() síncronamente para que los mocks funcionen sin hilos.
    # Aquí lo desactivamos a propósito para reproducir el camino real de
    # producción (envío al ThreadPoolExecutor compartido).
    app.config["TESTING"] = False

    activos = 0
    pico_activos = 0
    completados = 0
    lock = threading.Lock()

    def _webpush_lento(*args, **kwargs):
        nonlocal activos, pico_activos, completados
        with lock:
            activos += 1
            pico_activos = max(pico_activos, activos)
        time.sleep(DURACION_SIMULADA_WEBPUSH)
        with lock:
            activos -= 1
            completados += 1

    try:
        with patch("app.push.sender.webpush", side_effect=_webpush_lento):
            inicio_bucle = time.monotonic()
            for _ in range(N_SUSCRIPTORES):
                enviar_push(usuario, "Título", "Cuerpo")
            duracion_bucle = time.monotonic() - inicio_bucle

            limite = time.monotonic() + 5
            while completados < N_SUSCRIPTORES and time.monotonic() < limite:
                time.sleep(0.01)
    finally:
        app.config["VAPID_PRIVATE_KEY"] = old_key
        app.config["VAPID_CLAIM_EMAIL"] = old_email
        app.config["TESTING"] = old_testing

    assert completados == N_SUSCRIPTORES, (
        f"solo se completaron {completados} de {N_SUSCRIPTORES} envíos "
        "dentro del tiempo de espera"
    )
    # El pool acota la concurrencia a MAX_WORKERS_PUSH: nunca deberían
    # coincidir más ejecuciones de webpush a la vez que el tamaño del pool.
    assert pico_activos <= MAX_WORKERS_PUSH, (
        f"pico de ejecuciones concurrentes = {pico_activos}, por encima del "
        f"límite del pool ({MAX_WORKERS_PUSH})"
    )
    # Encolar en el pool no bloquea al hilo que hace el bucle (a diferencia
    # de esperar a que cada hilo termine). El bucle debe completarse mucho
    # antes de que todos los envíos simulados terminen.
    assert duracion_bucle < DURACION_SIMULADA_WEBPUSH * N_SUSCRIPTORES
