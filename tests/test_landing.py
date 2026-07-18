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


def test_landing_enlaza_a_como_funciona_completo(client, db):
    resp = client.get("/")
    assert "Ver todos los detalles".encode() in resp.data


def test_landing_no_aparece_para_usuario_autenticado(client, db):
    _crear_usuario_y_login(client)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Así de fácil".encode() not in resp.data
