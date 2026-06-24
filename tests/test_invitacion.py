"""Tests del sistema de invitación de compañeros."""
from app.extensions import db
from app.models import Categoria, insertar_categorias_semilla
from app.services.registro import registrar_usuario


def _usuario(nombre="Ana", email="ana@test.es"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario(
        nombre, email, "password123", "Hospital T", "Urgencias", cat.id,
        pais_nombre="España", provincia_nombre="Madrid", ciudad_nombre="Madrid",
    )


def _login(client, email="ana@test.es", password="password123"):
    client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=True)


# --- perfil/cuenta muestra la sección de invitación ---

def test_perfil_cuenta_contiene_enlace_whatsapp(client, db):
    """La página Mi perfil > Cuenta incluye un enlace wa.me de invitación."""
    _usuario()
    _login(client)
    resp = client.get("/auth/perfil/cuenta")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "wa.me" in html


def test_perfil_cuenta_enlace_contiene_url_registro(client, db):
    """El enlace de invitación apunta al formulario de registro."""
    _usuario()
    _login(client)
    resp = client.get("/auth/perfil/cuenta")
    html = resp.data.decode()
    assert "registro" in html
    assert "inv_hospital" in html


def test_perfil_cuenta_enlace_incluye_hospital_y_unidad(client, db):
    """El enlace contiene los IDs del hospital y la unidad del usuario."""
    usuario = _usuario()
    _login(client)
    resp = client.get("/auth/perfil/cuenta")
    html = resp.data.decode()
    hospital_id = str(usuario.unidad.hospital.id)
    unidad_id = str(usuario.unidad_id)
    categoria_id = str(usuario.categoria_id)
    assert f"inv_hospital={hospital_id}" in html
    assert f"inv_unidad={unidad_id}" in html
    assert f"inv_categoria={categoria_id}" in html


# --- /registro acepta params de invitación ---

def test_registro_con_invitacion_incluye_data_selected_hospital(client, db):
    """GET /registro?inv_hospital=X incluye data-selected-hospital en el HTML."""
    usuario = _usuario()
    hospital_id = usuario.unidad.hospital.id
    resp = client.get(f"/auth/registro?inv_hospital={hospital_id}&inv_unidad={usuario.unidad_id}&inv_categoria={usuario.categoria_id}")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert f'data-selected-hospital="{hospital_id}"' in html


def test_registro_con_invitacion_incluye_data_selected_unidad(client, db):
    """GET /registro con inv_unidad incluye data-selected-unidad."""
    usuario = _usuario()
    resp = client.get(f"/auth/registro?inv_hospital={usuario.unidad.hospital.id}&inv_unidad={usuario.unidad_id}&inv_categoria={usuario.categoria_id}")
    html = resp.data.decode()
    assert f'data-selected-unidad="{usuario.unidad_id}"' in html


def test_registro_con_invitacion_preselecciona_pais(client, db):
    """GET /registro con inv_hospital preselecciona el país en el select estático."""
    usuario = _usuario()
    hospital = usuario.unidad.hospital
    pais_id = hospital.ciudad.provincia.pais.id
    resp = client.get(f"/auth/registro?inv_hospital={hospital.id}")
    html = resp.data.decode()
    assert f'data-selected-pais="{pais_id}"' in html


def test_registro_sin_invitacion_no_tiene_data_selected(client, db):
    """Un GET /registro normal sin params inv_* no incluye data-selected."""
    _usuario()
    resp = client.get("/auth/registro")
    html = resp.data.decode()
    assert "data-selected-hospital" not in html
    assert "data-selected-unidad" not in html


def test_registro_con_inv_hospital_inexistente_no_da_error(client, db):
    """Un inv_hospital con ID inválido no provoca un error 500."""
    _usuario()
    resp = client.get("/auth/registro?inv_hospital=99999")
    assert resp.status_code == 200
