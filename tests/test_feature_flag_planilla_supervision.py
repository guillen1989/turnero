from flask_login import FlaskLoginClient

from app.services.feature_flags import desactivar_global


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


def test_rutas_planilla_supervision_devuelven_404_con_flag_inactivo(app, db):
    desactivar_global("planilla_supervision_multiunidad")
    client, _ = _create_supervisora_and_login(app, db, "ps1")

    for ruta in ["/planilla/supervision/", "/planilla/supervision/reglas"]:
        resp = client.get(ruta)
        assert resp.status_code == 404, f"{ruta} deberia devolver 404, dio {resp.status_code}"


def test_rutas_planilla_supervision_funcionan_con_flag_activo(app, db):
    client, _ = _create_supervisora_and_login(app, db, "ps2")

    assert client.get("/planilla/supervision/").status_code == 200
    assert client.get("/planilla/supervision/reglas").status_code == 200


def test_enlaces_planilla_supervision_ausentes_con_flag_inactivo(app, db):
    desactivar_global("planilla_supervision_multiunidad")
    client, _ = _create_supervisora_and_login(app, db, "ps3")

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "/planilla/supervision" not in html
    assert "/planilla/supervision/reglas" not in html


def test_enlaces_planilla_supervision_presentes_con_flag_activo(app, db):
    client, _ = _create_supervisora_and_login(app, db, "ps4")

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "/planilla/supervision" in html
