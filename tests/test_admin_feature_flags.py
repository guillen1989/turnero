from app.models import Usuario, Hospital, Unidad, Categoria, insertar_categorias_semilla, FeatureFlag
from app.services.feature_flags import crear_flag, habilitar_para_unidad


def _cat_id(db):
    insertar_categorias_semilla()
    return Categoria.query.filter_by(nombre="Enfermería").first().id


def _crear_usuario(db, email="user@test.es", es_admin=False):
    insertar_categorias_semilla()
    from app.services.registro import registrar_usuario
    u = registrar_usuario(
        nombre="Usuario Test",
        email=email,
        password="contraseña123",
        hospital_nombre="Hospital Admin Test",
        unidad_nombre="Urgencias",
        categoria_id=_cat_id(db),
    )
    u.es_admin = es_admin
    from app.extensions import db as _db
    _db.session.commit()
    return u


def _login(client, email, password="contraseña123"):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def _login_admin(client, db):
    _crear_usuario(db, email="admin@test.es", es_admin=True)
    _login(client, "admin@test.es")


def _login_normal(client, db):
    _crear_usuario(db, email="normal@test.es", es_admin=False)
    _login(client, "normal@test.es")


def test_requiere_admin_para_ver_la_lista(client, db):
    _login_normal(client, db)
    resp = client.get("/admin/feature-flags")
    assert resp.status_code == 403


def test_lista_muestra_flags_existentes(client, db):
    crear_flag("hoja_cambio_papel", "Registro en papel")
    _login_admin(client, db)

    resp = client.get("/admin/feature-flags")

    assert resp.status_code == 200
    assert b"hoja_cambio_papel" in resp.data
    assert "Registro en papel".encode() in resp.data


def test_activar_global_desde_el_formulario(client, db):
    flag = crear_flag("hoja_cambio_papel")
    _login_admin(client, db)

    resp = client.post(
        f"/admin/feature-flags/{flag.id}",
        data={"activo_global": "y", "unidades_habilitadas": []},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    recuperado = db.session.get(FeatureFlag, flag.id)
    assert recuperado.activo_global is True


def test_desactivar_global_desmarcando_el_checkbox(client, db):
    flag = crear_flag("hoja_cambio_papel")
    from app.services.feature_flags import activar_global
    activar_global("hoja_cambio_papel")
    _login_admin(client, db)

    resp = client.post(
        f"/admin/feature-flags/{flag.id}",
        data={"unidades_habilitadas": []},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    recuperado = db.session.get(FeatureFlag, flag.id)
    assert recuperado.activo_global is False


def test_sincroniza_unidades_habilitadas(client, db):
    hospital = Hospital(nombre="Hospital Test")
    from app.models import GrupoIntercambio
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()
    unidad1 = Unidad(nombre="Urgencias 2", hospital=hospital, grupo_intercambio=grupo)
    unidad2 = Unidad(nombre="UCI 2", hospital=hospital, grupo_intercambio=grupo)
    db.session.add_all([unidad1, unidad2])
    db.session.commit()

    flag = crear_flag("hoja_cambio_papel")
    habilitar_para_unidad("hoja_cambio_papel", unidad1)
    _login_admin(client, db)

    resp = client.post(
        f"/admin/feature-flags/{flag.id}",
        data={"unidades_habilitadas": [str(unidad2.id)]},
        follow_redirects=True,
    )

    assert resp.status_code == 200
    recuperado = db.session.get(FeatureFlag, flag.id)
    ids = {u.id for u in recuperado.unidades_habilitadas}
    assert ids == {unidad2.id}


def test_multi_unidad_no_muestra_selector_unidades(client, db):
    """El flag multi_unidad no debe mostrar el <select> de unidades habilitadas.
    El resto de flags sí deben mostrarlo."""
    crear_flag("multi_unidad", "Usuarios en varios servicios")
    flag_normal = crear_flag("otro_flag", "Un flag cualquiera")
    _login_admin(client, db)

    resp = client.get("/admin/feature-flags")
    assert resp.status_code == 200

    html = resp.data.decode()

    assert 'name="unidades_habilitadas"' in html

    import re
    formularios = re.findall(
        r'<form[^>]*action="[^"]*feature-flags/\d+"[^>]*>.*?</form>',
        html, re.DOTALL,
    )

    form_multi = None
    form_otro = None
    for f in formularios:
        if "multi_unidad" in f:
            form_multi = f
        elif "otro_flag" in f:
            form_otro = f

    assert form_multi is not None, "No se encontró el formulario de multi_unidad"
    assert form_otro is not None, "No se encontró el formulario de otro_flag"

    assert 'name="unidades_habilitadas"' not in form_multi, (
        "El formulario de multi_unidad NO debe contener el selector de unidades"
    )
    assert 'name="unidades_habilitadas"' in form_otro, (
        "El formulario de otro_flag SÍ debe contener el selector de unidades"
    )
    assert "Este flag es global" in form_multi, (
        "Debe aparecer el texto indicando que es un flag global"
    )
    assert "admite activación por unidad" in form_multi, (
        "Debe aparecer el texto indicando que no admite activación por unidad"
    )
