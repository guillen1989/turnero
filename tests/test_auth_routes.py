"""
Tests de integración HTTP para registro, login y logout.
"""
from app.models import Usuario, Hospital, Unidad, Categoria, GrupoIntercambio, insertar_categorias_semilla


def _cat_id(db):
    insertar_categorias_semilla()
    return Categoria.query.filter_by(nombre="Enfermería").first().id


def _datos_registro(db, **overrides):
    datos = {
        "nombre": "Ana García",
        "email": "ana@test.es",
        "password": "contraseña123",
        "password2": "contraseña123",
        "hospital_nombre": "Hospital Test",
        "unidad_nombre": "Urgencias",
        "categoria_id": _cat_id(db),
        "categoria_nueva": "",
    }
    datos.update(overrides)
    return datos


def test_get_registro_devuelve_200(client):
    resp = client.get("/auth/registro")
    assert resp.status_code == 200


def test_registro_exitoso_redirige(client, db):
    resp = client.post("/auth/registro", data=_datos_registro(db), follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")


def test_registro_crea_usuario_en_bd(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    assert Usuario.query.filter_by(email="ana@test.es").count() == 1


def test_registro_crea_hospital_nuevo(client, db):
    client.post("/auth/registro", data=_datos_registro(db, hospital_nombre="Hospital Nuevo"))
    assert Hospital.query.filter_by(nombre="Hospital Nuevo").count() == 1


def test_registro_crea_unidad_nueva_con_grupo(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    unidad = Unidad.query.filter_by(nombre="Urgencias").first()
    assert unidad is not None
    assert unidad.grupo_intercambio is not None


def test_registro_email_duplicado_muestra_error(client, db):
    datos = _datos_registro(db)
    client.post("/auth/registro", data=datos)
    client.get("/auth/logout")  # el registro hace login_user; hay que salir antes del segundo intento
    resp = client.post("/auth/registro", data=datos, follow_redirects=True)
    assert resp.status_code == 200
    assert "ya está registrado".encode() in resp.data


def test_registro_con_categoria_nueva(client, db):
    insertar_categorias_semilla()
    datos = _datos_registro(db)
    datos["categoria_id"] = 0
    datos["categoria_nueva"] = "Técnico/a de farmacia"
    client.post("/auth/registro", data=datos)
    assert Categoria.query.filter_by(nombre="Técnico/a de farmacia").count() == 1


def test_get_login_devuelve_200(client, db):
    resp = client.get("/auth/login")
    assert resp.status_code == 200


def test_login_exitoso_redirige(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    resp = client.post(
        "/auth/login",
        data={"email": "ana@test.es", "password": "contraseña123"},
        follow_redirects=False,
    )
    assert resp.status_code == 302


def test_login_credenciales_incorrectas(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    client.get("/auth/logout")  # el registro hace login_user; salir para probar login con mal password
    resp = client.post(
        "/auth/login",
        data={"email": "ana@test.es", "password": "mal"},
        follow_redirects=True,
    )
    assert "incorrectos".encode() in resp.data


def test_logout_requiere_autenticacion(client, db):
    resp = client.get("/auth/logout", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_logout_cierra_sesion(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    resp = client.get("/auth/logout", follow_redirects=True)
    assert "cerrado sesión".encode() in resp.data


# --- API de unidades ---

def test_api_unidades_sin_hospital_devuelve_lista_vacia(client):
    resp = client.get("/auth/api/unidades")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_api_unidades_hospital_inexistente_devuelve_lista_vacia(client):
    resp = client.get("/auth/api/unidades?hospital=NoExiste")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_api_unidades_devuelve_unidades_del_hospital(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    resp = client.get("/auth/api/unidades?hospital=Hospital Test")
    assert resp.status_code == 200
    nombres = resp.get_json()
    assert "Urgencias" in nombres


# --- Perfil ---

def test_get_perfil_requiere_autenticacion(client):
    resp = client.get("/auth/perfil", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_get_perfil_devuelve_200(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    resp = client.get("/auth/perfil")
    assert resp.status_code == 200


def test_perfil_prerellena_datos_actuales(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    resp = client.get("/auth/perfil")
    assert b"Hospital Test" in resp.data
    assert b"Urgencias" in resp.data


def test_perfil_actualiza_hospital_y_unidad(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    usuario = Usuario.query.filter_by(email="ana@test.es").first()
    resp = client.post(
        "/auth/perfil",
        data={
            "hospital_nombre": "Hospital Nuevo",
            "unidad_nombre": "UCI",
            "categoria_id": _cat_id(db),
            "categoria_nueva": "",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    from app.extensions import db as _db
    _db.session.refresh(usuario)
    assert usuario.unidad.nombre == "UCI"
    assert usuario.unidad.hospital.nombre == "Hospital Nuevo"
