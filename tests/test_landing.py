from app.models import Categoria, insertar_categorias_semilla
from app.services.registro import registrar_usuario


def _crear_usuario_y_login(client, email="landing@test.es"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    usuario = registrar_usuario("Landing", email, "pass1234", "H1", "Urgencias", cat.id)
    client.post("/auth/login", data={"email": email, "password": "pass1234"})
    return usuario


def test_landing_muestra_como_funciona_y_propuesta_de_valor(client, db):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Así de fácil".encode() in resp.data
    assert "Por qué Turnero".encode() in resp.data
    assert "categoría y unidad".encode() in resp.data
    assert "cambios a tres bandas".encode() in resp.data
    assert "Hoja de cambio digital".encode() in resp.data


def test_landing_enlaza_a_funcionalidades_completo(client, db):
    resp = client.get("/")
    assert "Ver todos los detalles".encode() in resp.data
    assert b'href="/funcionalidades"' in resp.data


def test_landing_no_aparece_para_usuario_autenticado(client, db):
    _crear_usuario_y_login(client)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Así de fácil".encode() not in resp.data


def test_funcionalidades_accesible_sin_login(client, db):
    resp = client.get("/funcionalidades")
    assert resp.status_code == 200
    assert "Cómo funciona Turnero".encode() in resp.data


def test_funcionalidades_muestra_las_secciones_clave(client, db):
    resp = client.get("/funcionalidades")
    assert "Descubre cambios en el calendario".encode() in resp.data
    assert "Publica tu cambio".encode() in resp.data
    assert "Publica tu planilla mensual".encode() in resp.data
    assert "Si hay match, te avisamos".encode() in resp.data
    assert "cambios a tres bandas".encode() in resp.data
    assert "Instala Turnero en tu móvil".encode() in resp.data


def test_funcionalidades_invita_a_crear_cuenta_no_a_paginas_privadas(client, db):
    resp = client.get("/funcionalidades")
    assert resp.status_code == 200
    contenido = resp.data.split(b'<div class="card">', 1)[1]
    # El contenido propio de la página no debe enlazar a páginas que
    # requieren login (redirigirían a login, una experiencia confusa para
    # un visitante que aún no tiene cuenta). El header compartido sí puede
    # enlazar al calendario desde el logo; eso queda fuera del contenido.
    assert b'href="/planilla' not in contenido
    assert b'href="/cambios' not in contenido
    assert b'href="/publicaciones' not in contenido
    assert b'href="/calendario' not in contenido
    assert resp.data.count(b'href="/auth/registro"') >= 1


def test_funcionalidades_no_marca_onboarding_ni_requiere_usuario(client, db):
    # A diferencia de /como-funciona, esta página pública no debe tocar
    # current_user (no autenticado) ni redirigir a login.
    resp = client.get("/funcionalidades", follow_redirects=False)
    assert resp.status_code == 200
