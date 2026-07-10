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


# ---------------------------------------------------------------------------
# me_interesa events
# ---------------------------------------------------------------------------

def test_analytics_data_incluye_me_interesa_en_datasets(client, db):
    _setup_admin(client)
    resp = client.get("/admin/analytics/data?granularity=day")
    data = json.loads(resp.data)
    assert "me_interesa" in data["datasets"]
    assert "me_interesa" in data["totals"]


def test_me_interesa_click_registra_evento(client, db):
    """POST a /cambios/<id>/me-interesa registra un Event de tipo me_interesa."""
    from app.models import Event, FranjaHoraria, PublicacionCambio, TurnoCedido, TurnoAceptado
    from app.services.registro import registrar_usuario
    from datetime import date
    from unittest.mock import patch

    insertar_categorias_semilla()
    cat_id = Categoria.query.filter_by(nombre="Enfermería").first().id
    ana   = registrar_usuario("Ana",   "ana2@ev.es",   "pass", "H1", "Urgencias", cat_id)
    pedro = registrar_usuario("Pedro", "pedro2@ev.es", "pass", "H1", "Urgencias", cat_id)
    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=ana.unidad.grupo_intercambio_id, nombre="Mañana"
    ).first()
    pub = PublicacionCambio(usuario_id=ana.id, tipo="cambio")
    _db.session.add(pub)
    _db.session.flush()
    tc = TurnoCedido(publicacion_id=pub.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id)
    ta = TurnoAceptado(publicacion_id=pub.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id)
    _db.session.add_all([tc, ta])
    _db.session.commit()

    client.post("/auth/login", data={"email": "pedro2@ev.es", "password": "pass"})
    with patch("app.push.sender.webpush"):
        client.post(f"/cambios/{pub.id}/me-interesa",
                    data={"turno_cedido_id": tc.id, "turno_aceptado_id": ta.id})

    ev = Event.query.filter_by(event_type="me_interesa", user_id=pedro.id).first()
    assert ev is not None
    assert ev.entity_id == pub.id


def test_analytics_totals_cuenta_me_interesa(client, db):
    """El total de me_interesa en analytics refleja los eventos registrados."""
    from app.models import Event
    admin = _setup_admin(client)
    _db.session.add(Event(user_id=admin.id, event_type="me_interesa", entity_id=1))
    _db.session.add(Event(user_id=admin.id, event_type="me_interesa", entity_id=2))
    _db.session.commit()

    resp = client.get("/admin/analytics/data?granularity=month")
    data = json.loads(resp.data)
    assert data["totals"]["me_interesa"] == 2


# ---------------------------------------------------------------------------
# activas acumuladas en datasets
# ---------------------------------------------------------------------------

def test_analytics_data_incluye_activas_en_datasets(client, db):
    _setup_admin(client)
    resp = client.get("/admin/analytics/data?granularity=day")
    data = json.loads(resp.data)
    assert "activas" in data["datasets"]


def test_analytics_data_incluye_eliminadas_en_datasets(client, db):
    _setup_admin(client)
    resp = client.get("/admin/analytics/data?granularity=day")
    data = json.loads(resp.data)
    assert "eliminadas" in data["datasets"]


def test_analytics_eliminadas_dataset_cuenta_eliminaciones(client, db):
    from app.models import PublicacionCambio
    from app.services.publicaciones import eliminar_publicacion
    admin = _setup_admin(client)
    pub = PublicacionCambio(usuario_id=admin.id, tipo="cambio")
    _db.session.add(pub)
    _db.session.commit()
    eliminar_publicacion(pub)

    resp = client.get("/admin/analytics/data?granularity=month")
    data = json.loads(resp.data)
    assert sum(data["datasets"]["eliminadas"]) == 1


def test_analytics_data_incluye_planillas_publicadas_en_datasets(client, db):
    _setup_admin(client)
    resp = client.get("/admin/analytics/data?granularity=day")
    data = json.loads(resp.data)
    assert "planillas_publicadas" in data["datasets"]
    assert "planillas_publicadas" in data["totals"]


def test_analytics_planillas_publicadas_dataset_cuenta_eventos(client, db):
    from app.models import Event
    admin = _setup_admin(client)
    _db.session.add(Event(user_id=admin.id, event_type="planilla_publicada", entity_id=1))
    _db.session.add(Event(user_id=admin.id, event_type="planilla_publicada", entity_id=2))
    _db.session.commit()

    resp = client.get("/admin/analytics/data?granularity=month")
    data = json.loads(resp.data)
    assert sum(data["datasets"]["planillas_publicadas"]) == 2


def test_analytics_activas_crece_con_publicaciones(client, db):
    """El acumulado de activas sube cuando se publican cambios."""
    from app.models import PublicacionCambio
    admin = _setup_admin(client)
    _db.session.add(PublicacionCambio(usuario_id=admin.id, tipo="cambio"))
    _db.session.add(PublicacionCambio(usuario_id=admin.id, tipo="cambio"))
    _db.session.commit()

    resp = client.get("/admin/analytics/data?granularity=month")
    data = json.loads(resp.data)
    # El acumulado al final del único bucket debe ser 2
    assert max(data["datasets"]["activas"]) == 2


def test_analytics_activas_baja_al_cancelar(client, db):
    """El acumulado de activas baja cuando se cancela una publicación."""
    from app.models import PublicacionCambio
    from app.services.publicaciones import cancelar_publicacion
    admin = _setup_admin(client)
    pub1 = PublicacionCambio(usuario_id=admin.id, tipo="cambio")
    pub2 = PublicacionCambio(usuario_id=admin.id, tipo="cambio")
    _db.session.add_all([pub1, pub2])
    _db.session.commit()
    cancelar_publicacion(pub1)

    resp = client.get("/admin/analytics/data?granularity=month")
    data = json.loads(resp.data)
    # Neto: 2 creadas - 1 cerrada = 1 activa
    assert max(data["datasets"]["activas"]) == 1


def test_publicacion_fecha_cierre_se_setea_al_cancelar(client, db):
    """fecha_cierre se asigna automáticamente al cancelar una publicación."""
    from app.models import PublicacionCambio
    from app.services.publicaciones import cancelar_publicacion
    admin = _setup_admin(client)
    pub = PublicacionCambio(usuario_id=admin.id, tipo="cambio")
    _db.session.add(pub)
    _db.session.commit()
    assert pub.fecha_cierre is None
    cancelar_publicacion(pub)
    assert pub.fecha_cierre is not None
