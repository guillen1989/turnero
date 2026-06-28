"""Tests para el panel de analytics del administrador."""
import json
from app.models import Categoria, insertar_categorias_semilla
from app.extensions import db as _db


def _setup_admin(client):
    insertar_categorias_semilla()
    from app.services.registro import registrar_usuario
    u = registrar_usuario(
        nombre="Admin Analytics",
        email="admin@analytics.es",
        password="pass123",
        hospital_nombre="Hospital Analytics",
        unidad_nombre="Urgencias",
        categoria_id=Categoria.query.filter_by(nombre="Enfermería").first().id,
    )
    u.es_admin = True
    _db.session.commit()
    client.post("/auth/login", data={"email": "admin@analytics.es", "password": "pass123"})
    return u


def _setup_normal(client):
    insertar_categorias_semilla()
    from app.services.registro import registrar_usuario
    u = registrar_usuario(
        nombre="Normal Analytics",
        email="normal@analytics.es",
        password="pass123",
        hospital_nombre="Hospital Analytics",
        unidad_nombre="Urgencias",
        categoria_id=Categoria.query.filter_by(nombre="Enfermería").first().id,
    )
    _db.session.commit()
    client.post("/auth/login", data={"email": "normal@analytics.es", "password": "pass123"})
    return u


def test_analytics_accesible_para_admin(client, db):
    _setup_admin(client)
    resp = client.get("/admin/analytics")
    assert resp.status_code == 200


def test_analytics_403_para_usuario_normal(client, db):
    _setup_normal(client)
    resp = client.get("/admin/analytics")
    assert resp.status_code == 403


def test_analytics_data_estructura_json(client, db):
    _setup_admin(client)
    resp = client.get("/admin/analytics/data?granularity=day")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "labels" in data
    assert "datasets" in data
    for key in ("usuarios", "publicaciones", "matches", "confirmados"):
        assert key in data["datasets"]


def test_analytics_data_refleja_usuarios(client, db):
    _setup_admin(client)
    resp = client.get("/admin/analytics/data?granularity=month")
    data = json.loads(resp.data)
    assert sum(data["datasets"]["usuarios"]) == 1


def test_analytics_data_granularidad_invalida_usa_dia(client, db):
    _setup_admin(client)
    resp = client.get("/admin/analytics/data?granularity=invalid")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "labels" in data


def test_analytics_data_filtra_por_unidad(client, db):
    from app.services.registro import registrar_usuario
    insertar_categorias_semilla()
    cat_id = Categoria.query.filter_by(nombre="Enfermería").first().id

    admin = registrar_usuario("Admin", "admin@an.es", "pass", "H1", "UCI", cat_id)
    admin.es_admin = True
    registrar_usuario("Otro", "otro@an.es", "pass", "H2", "Planta", cat_id)
    _db.session.commit()

    client.post("/auth/login", data={"email": "admin@an.es", "password": "pass"})

    resp = client.get(f"/admin/analytics/data?granularity=month&unidad_id={admin.unidad_id}")
    data = json.loads(resp.data)
    # solo el admin pertenece a esa unidad
    assert sum(data["datasets"]["usuarios"]) == 1


def test_analytics_data_cuenta_publicaciones(client, db):
    from app.models import PublicacionCambio
    admin = _setup_admin(client)
    pub = PublicacionCambio(usuario_id=admin.id, tipo="cambio")
    _db.session.add(pub)
    _db.session.commit()

    resp = client.get("/admin/analytics/data?granularity=month")
    data = json.loads(resp.data)
    assert sum(data["datasets"]["publicaciones"]) == 1


def test_analytics_data_no_cuenta_sinteticas(client, db):
    from app.models import PublicacionCambio
    admin = _setup_admin(client)
    pub_normal = PublicacionCambio(usuario_id=admin.id, tipo="cambio", es_sintetica=False)
    pub_sintetica = PublicacionCambio(usuario_id=admin.id, tipo="cambio", es_sintetica=True)
    _db.session.add_all([pub_normal, pub_sintetica])
    _db.session.commit()

    resp = client.get("/admin/analytics/data?granularity=month")
    data = json.loads(resp.data)
    assert sum(data["datasets"]["publicaciones"]) == 1


def test_analytics_data_incluye_totals(client, db):
    _setup_admin(client)
    resp = client.get("/admin/analytics/data?granularity=day")
    data = json.loads(resp.data)
    assert "totals" in data
    for key in ("usuarios", "hospitales", "unidades", "categorias",
                "publicaciones", "sinteticas", "matches", "confirmados", "eliminadas"):
        assert key in data["totals"]


def test_analytics_data_totals_cuenta_sinteticas(client, db):
    from app.models import PublicacionCambio
    admin = _setup_admin(client)
    _db.session.add(PublicacionCambio(usuario_id=admin.id, tipo="cambio", es_sintetica=True))
    _db.session.add(PublicacionCambio(usuario_id=admin.id, tipo="cambio", es_sintetica=True))
    _db.session.commit()

    resp = client.get("/admin/analytics/data?granularity=month")
    data = json.loads(resp.data)
    assert data["totals"]["sinteticas"] == 2


def test_analytics_data_totals_cuenta_eliminadas(client, db):
    from app.models import PublicacionCambio
    from app.services.publicaciones import eliminar_publicacion
    admin = _setup_admin(client)
    pub = PublicacionCambio(usuario_id=admin.id, tipo="cambio")
    _db.session.add(pub)
    _db.session.commit()
    eliminar_publicacion(pub)

    resp = client.get("/admin/analytics/data?granularity=month")
    data = json.loads(resp.data)
    assert data["totals"]["eliminadas"] == 1


def test_analytics_data_totals_filtrados_por_unidad(client, db):
    from app.services.registro import registrar_usuario
    insertar_categorias_semilla()
    cat_id = Categoria.query.filter_by(nombre="Enfermería").first().id

    admin = registrar_usuario("Admin", "admin2@an.es", "pass", "H1", "UCI", cat_id)
    admin.es_admin = True
    otro = registrar_usuario("Otro", "otro2@an.es", "pass", "H2", "Planta", cat_id)
    _db.session.commit()

    client.post("/auth/login", data={"email": "admin2@an.es", "password": "pass"})

    resp = client.get(f"/admin/analytics/data?granularity=month&unidad_id={admin.unidad_id}")
    data = json.loads(resp.data)
    assert data["totals"]["usuarios"] == 1
    assert data["totals"]["unidades"] == 1
    assert data["totals"]["hospitales"] == 1
