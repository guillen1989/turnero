from flask_login import FlaskLoginClient

from app.services.feature_flags import crear_flag, activar_global


def _create_supervisora_and_login(app, db, suffix):
    from tests.helpers_documento_cambio import _setup
    from app.models import UnidadSupervisada

    app.test_client_class = FlaskLoginClient
    crear_usuario, manyana, tarde = _setup(db, suffix)
    u = crear_usuario("Marta", f"marta@{suffix}.test")
    u.es_supervisora = True
    db.session.add(UnidadSupervisada(usuario_id=u.id, unidad_id=u.unidad_id))
    from app.extensions import db as _db
    _db.session.commit()
    client = app.test_client(user=u)
    return client, u


def test_rutas_importar_planilla_devuelven_404_con_flag_inactivo(app, db):
    crear_flag("importacion_planilla")
    client, _ = _create_supervisora_and_login(app, db, "ip1")

    for ruta in ["/planilla/importar/", "/planilla/importar/codigos"]:
        resp = client.get(ruta)
        assert resp.status_code == 404, f"{ruta} deberia devolver 404, dio {resp.status_code}"


def test_rutas_importar_planilla_funcionan_con_flag_activo(app, db):
    crear_flag("importacion_planilla")
    activar_global("importacion_planilla")
    client, _ = _create_supervisora_and_login(app, db, "ip2")

    assert client.get("/planilla/importar/").status_code == 200


def test_enlace_importar_planilla_ausente_con_flag_inactivo(app, db):
    crear_flag("importacion_planilla")
    client, _ = _create_supervisora_and_login(app, db, "ip3")

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "/planilla/importar" not in html


def test_enlace_importar_planilla_presente_con_flag_activo(app, db):
    crear_flag("importacion_planilla")
    activar_global("importacion_planilla")
    client, _ = _create_supervisora_and_login(app, db, "ip4")

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "/planilla/importar" in html
