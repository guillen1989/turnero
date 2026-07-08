"""Tests E2E del flujo de autenticación."""


def test_login_correcto_redirige_al_inicio(page, live_server, usuario):
    page.goto(f"{live_server}/auth/login")
    page.locator('input[name="email"]').fill(usuario["email"])
    page.locator('input[name="password"]').fill(usuario["password"])
    page.locator('[type="submit"]').click()

    page.wait_for_url(f"{live_server}/calendario/")
    assert "Turnero" in page.title()


def test_login_incorrecto_muestra_error(page, live_server, usuario):
    page.goto(f"{live_server}/auth/login")
    page.locator('input[name="email"]').fill(usuario["email"])
    page.locator('input[name="password"]').fill("contraseña_incorrecta")
    page.locator('[type="submit"]').click()

    assert "/login" in page.url
    assert "incorrectos" in page.content()


def test_ruta_protegida_redirige_al_login(page, live_server):
    page.goto(f"{live_server}/publicar")
    assert "/login" in page.url
