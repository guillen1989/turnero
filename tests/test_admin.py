"""Tests de integración para el panel de administración."""
import pytest
from datetime import date
from app.models import (
    Usuario, Hospital, Unidad, Categoria, insertar_categorias_semilla,
    PublicacionCambio, TurnoCedido, TurnoAceptado, FranjaHoraria,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cat_id(db):
    insertar_categorias_semilla()
    return Categoria.query.filter_by(nombre="Enfermería").first().id


def _crear_usuario(client, db, email="user@test.es", es_admin=False):
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
    _crear_usuario(client, db, email="admin@test.es", es_admin=True)
    _login(client, "admin@test.es")


def _login_normal(client, db):
    _crear_usuario(client, db, email="normal@test.es", es_admin=False)
    _login(client, "normal@test.es")


# ---------------------------------------------------------------------------
# Acceso y permisos
# ---------------------------------------------------------------------------

def test_admin_redirige_si_no_autenticado(client):
    resp = client.get("/admin/", follow_redirects=False)
    assert resp.status_code == 302


def test_admin_403_para_usuario_normal(client, db):
    _login_normal(client, db)
    resp = client.get("/admin/")
    assert resp.status_code == 403


def test_admin_index_accesible_para_admin(client, db):
    _login_admin(client, db)
    resp = client.get("/admin/")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------

def test_admin_lista_usuarios(client, db):
    _login_admin(client, db)
    resp = client.get("/admin/usuarios")
    assert resp.status_code == 200
    assert b"admin@test.es" in resp.data


def test_admin_crea_usuario(client, db):
    _login_admin(client, db)
    resp = client.post(
        "/admin/usuarios/nuevo",
        data={
            "nombre": "Nuevo Enfermero",
            "email": "nuevo@test.es",
            "password": "contraseña123",
            "hospital_id": "0",
            "hospital_nuevo": "Hospital Admin Test",
            "unidad_id": "0",
            "unidad_nuevo": "UCI",
            "categoria_id": _cat_id(db),
            "categoria_nueva": "",
            "es_admin": False,
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert Usuario.query.filter_by(email="nuevo@test.es").count() == 1


def test_admin_edita_usuario(client, db):
    _login_admin(client, db)
    u = _crear_usuario(client, db, email="editar@test.es")
    from app.extensions import db as _db
    _db.session.refresh(u)
    resp = client.post(
        f"/admin/usuarios/{u.id}/editar",
        data={
            "nombre": "Nombre Modificado",
            "email": "editar@test.es",
            "password": "",
            "hospital_id": "0",
            "hospital_nuevo": "Hospital Admin Test",
            "unidad_id": "0",
            "unidad_nuevo": "Urgencias",
            "categoria_id": _cat_id(db),
            "categoria_nueva": "",
            "es_admin": False,
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    _db.session.refresh(u)
    assert u.nombre == "Nombre Modificado"


def test_admin_elimina_usuario(client, db):
    _login_admin(client, db)
    u = _crear_usuario(client, db, email="borrar@test.es")
    from app.extensions import db as _db
    resp = client.post(
        f"/admin/usuarios/{u.id}/eliminar",
        data={"csrf_token": ""},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert Usuario.query.filter_by(email="borrar@test.es").count() == 0


def test_admin_elimina_usuario_con_publicaciones(client, db):
    """Regression: deleting a user with publications used to raise Internal Server Error."""
    from app.extensions import db as _db
    _login_admin(client, db)
    u = _crear_usuario(client, db, email="con_pubs@test.es")

    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u.unidad.grupo_intercambio_id, nombre="Mañana"
    ).first()
    pub = PublicacionCambio(usuario_id=u.id)
    _db.session.add(pub)
    _db.session.flush()
    _db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id))
    _db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=date(2026, 9, 30), franja_horaria_id=franja.id))
    _db.session.commit()

    resp = client.post(
        f"/admin/usuarios/{u.id}/eliminar",
        data={"csrf_token": ""},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert Usuario.query.filter_by(email="con_pubs@test.es").count() == 0


# ---------------------------------------------------------------------------
# Hospitales
# ---------------------------------------------------------------------------

def test_admin_lista_hospitales(client, db):
    _login_admin(client, db)
    resp = client.get("/admin/hospitales")
    assert resp.status_code == 200
    assert b"Hospital Admin Test" in resp.data


def test_admin_crea_hospital(client, db):
    _login_admin(client, db)
    resp = client.post(
        "/admin/hospitales",
        data={"nuevo-nombre": "Hospital Nuevo Admin", "nuevo-submit": "Guardar"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert Hospital.query.filter_by(nombre="Hospital Nuevo Admin").count() == 1


def test_admin_no_elimina_hospital_con_unidades(client, db):
    _login_admin(client, db)
    h = Hospital.query.filter_by(nombre="Hospital Admin Test").first()
    resp = client.post(
        f"/admin/hospitales/{h.id}/eliminar",
        data={"csrf_token": ""},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert Hospital.query.filter_by(nombre="Hospital Admin Test").count() == 1


# ---------------------------------------------------------------------------
# Categorías
# ---------------------------------------------------------------------------

def test_admin_lista_categorias(client, db):
    _login_admin(client, db)
    insertar_categorias_semilla()
    resp = client.get("/admin/categorias")
    assert resp.status_code == 200
    assert "Enfermer".encode() in resp.data


def test_admin_crea_categoria(client, db):
    _login_admin(client, db)
    resp = client.post(
        "/admin/categorias",
        data={"nuevo-nombre": "Podólogo/a", "nuevo-submit": "Guardar"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert Categoria.query.filter_by(nombre="Podólogo/a").count() == 1


# ---------------------------------------------------------------------------
# Publicaciones
# ---------------------------------------------------------------------------

def test_admin_lista_publicaciones(client, db):
    _login_admin(client, db)
    resp = client.get("/admin/publicaciones")
    assert resp.status_code == 200
