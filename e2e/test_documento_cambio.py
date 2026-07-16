"""Golden-path visual: hoja de cambio digital con firma dibujada a mano.

Ana crea una hoja de cambio con Pedro (mismo hospital/unidad/categoría),
firma ella misma en el canvas, pasa el móvil y firma Pedro, y comprueba
que aparecen las notas para copiar en ilog.

Ejecución (headed, con pausa visual):
  pytest e2e/test_documento_cambio.py --headed --slowmo=400 -s
"""
from app.extensions import db
from app.models import Categoria, insertar_categorias_semilla
from app.services.registro import registrar_usuario


def _login(page, base, email, password="pass1234"):
    page.goto(f"{base}/auth/login")
    page.locator('input[name="email"]').fill(email)
    page.locator('input[name="password"]').fill(password)
    page.locator('[type="submit"]').click()
    page.wait_for_url(f"{base}/calendario/")


def _dibujar_firma(page):
    canvas = page.locator("canvas.firma-canvas")
    canvas.scroll_into_view_if_needed()
    box = canvas.bounding_box()
    x0, y0 = box["x"] + 20, box["y"] + box["height"] / 2
    page.mouse.move(x0, y0)
    page.mouse.down()
    for i in range(1, 6):
        page.mouse.move(x0 + i * 60, y0 + (20 if i % 2 == 0 else -20), steps=5)
    page.mouse.up()


def test_hoja_de_cambio_golden_path_completa(e2e_app, page, live_server, clean_e2e_db):
    with e2e_app.app_context():
        insertar_categorias_semilla()
        cat = Categoria.query.filter_by(nombre="Enfermería").first()
        ana = registrar_usuario(
            "Ana García", "ana.doc@test.es", "pass1234",
            "Hospital E2E Doc", "Urgencias Doc", cat.id,
        )
        pedro = registrar_usuario(
            "Pedro Ruiz", "pedro.doc@test.es", "pass1234",
            "Hospital E2E Doc", "Urgencias Doc", cat.id,
        )
        ana.onboarding_visto = True
        pedro.onboarding_visto = True
        db.session.commit()

    console_errors = []
    dialogs = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))

    _login(page, live_server, "ana.doc@test.es")

    page.goto(f"{live_server}/documentos-cambio/nuevo")
    page.locator("#companero_id").select_option(label="Pedro Ruiz")
    page.locator("#turno_cede_fecha").fill("2026-08-07")
    page.locator("#turno_cede_franja_id").select_option(label="Mañana")
    page.locator("#turno_recibe_fecha").fill("2026-08-28")
    page.locator("#turno_recibe_franja_id").select_option(label="Mañana")
    page.locator("form button[type=submit]").click()

    page.wait_for_url(lambda url: "/documentos-cambio/" in url and "nuevo" not in url)
    page.screenshot(path="/tmp/doc_cambio_1_creado.png")

    assert page.locator("text=Firma de Ana García").count() == 1
    _dibujar_firma(page)
    page.locator("button:has-text('Guardar firma')").click()
    page.wait_for_selector("text=Firma de Pedro Ruiz")
    page.screenshot(path="/tmp/doc_cambio_2_una_firma.png")

    _dibujar_firma(page)
    page.locator("button:has-text('Guardar firma')").click()
    page.wait_for_selector("text=Notas para ilog")
    page.screenshot(path="/tmp/doc_cambio_3_completo.png")

    cajas_notas = page.locator(".nota-ilog-texto")
    assert cajas_notas.count() == 4
    notas = [cajas_notas.nth(i).input_value() for i in range(4)]
    for texto in notas:
        print("NOTA ILOG:", texto)
        assert texto  # no vacío: confirma que la lectura vía input_value() es correcta

    assert "Las dos firmas" in page.locator(".documento-completo-banner").inner_text()
    assert console_errors == [], f"Errores de consola: {console_errors}"
    assert dialogs == [], f"Alertas JS inesperadas (firma no detectada): {dialogs}"
