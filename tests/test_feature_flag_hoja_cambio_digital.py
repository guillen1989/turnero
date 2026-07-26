from flask_login import FlaskLoginClient

from app.services.feature_flags import crear_flag, activar_global


def _create_and_login(app, db, suffix):
    from tests.helpers_documento_cambio import _setup

    app.test_client_class = FlaskLoginClient
    crear_usuario, manyana, tarde = _setup(db, suffix)
    u = crear_usuario("Ana", f"ana@{suffix}.test")
    client = app.test_client(user=u)
    return client, u


def test_rutas_documento_cambio_devuelven_404_con_flag_inactivo(app, db):
    crear_flag("hoja_cambio_digital")
    client, _ = _create_and_login(app, db, "flag1")

    for ruta in ["/documentos-cambio/", "/documentos-cambio/nuevo",
                 "/documentos-cambio/1", "/documentos-cambio/1/pdf"]:
        resp = client.get(ruta)
        assert resp.status_code == 404, f"{ruta} deberia devolver 404, dio {resp.status_code}"


def test_rutas_documento_cambio_funcionan_con_flag_activo(app, db):
    crear_flag("hoja_cambio_digital")
    activar_global("hoja_cambio_digital")
    client, _ = _create_and_login(app, db, "flag2")

    assert client.get("/documentos-cambio/").status_code == 200
    assert client.get("/documentos-cambio/nuevo").status_code == 200


def test_enlace_hoja_cambio_ausente_en_nav_con_flag_inactivo(app, db):
    crear_flag("hoja_cambio_digital")
    client, _ = _create_and_login(app, db, "flag3")

    resp = client.get("/")
    assert resp.status_code == 200
    assert "/documentos-cambio" not in resp.data.decode("utf-8")


def test_enlace_hoja_cambio_presente_en_nav_con_flag_activo(app, db):
    crear_flag("hoja_cambio_digital")
    activar_global("hoja_cambio_digital")
    client, _ = _create_and_login(app, db, "flag4")

    resp = client.get("/")
    assert resp.status_code == 200
    assert "/documentos-cambio" in resp.data.decode("utf-8")
