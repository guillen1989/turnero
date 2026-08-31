"""Tests de integración para el feed de novedades (/novedades)."""
from datetime import date

from flask_login import FlaskLoginClient

from app.extensions import db
from app.models import (
    Categoria, FranjaHoraria, PublicacionCambio, TurnoCedido, TurnoAceptado,
    insertar_categorias_semilla,
)
from app.services.feature_flags import desactivar_global
from app.services.registro import registrar_usuario


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _usuario(email="a@test.es", hospital="H1", unidad="Urgencias", cat_nombre="Enfermería"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre=cat_nombre).first()
    u = registrar_usuario("Test", email, "pass123", hospital, unidad, cat.id)
    db.session.commit()
    return u


def _login(client, email, password="pass123"):
    client.post("/auth/login", data={"email": email, "password": password})


def _publicar(usuario, fecha_cede, fecha_acepta, estado=None):
    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=usuario.unidad.grupo_intercambio_id
    ).first()
    pub = PublicacionCambio(usuario_id=usuario.id)
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=fecha_cede, franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=fecha_acepta, franja_horaria_id=franja.id))
    db.session.commit()
    if estado is not None:
        pub.estado = estado
        db.session.commit()
    return pub


# ---------------------------------------------------------------------------
# Acceso y feature flag
# ---------------------------------------------------------------------------

def test_novedades_requiere_login(client, db):
    resp = client.get("/novedades", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_novedades_accesible_autenticado(client, db):
    u = _usuario()
    _login(client, u.email)
    resp = client.get("/novedades")
    assert resp.status_code == 200


def test_novedades_404_con_flag_inactivo(client, db):
    desactivar_global("novedades")
    u = _usuario()
    _login(client, u.email)
    resp = client.get("/novedades")
    assert resp.status_code == 404


def test_enlace_novedades_ausente_en_nav_con_flag_inactivo(client, db):
    desactivar_global("novedades")
    u = _usuario()
    _login(client, u.email)
    resp = client.get("/")
    assert "/novedades" not in resp.data.decode("utf-8")


def test_enlace_novedades_presente_en_nav_con_flag_activo(client, db):
    u = _usuario()
    _login(client, u.email)
    resp = client.get("/")
    assert "/novedades" in resp.data.decode("utf-8")


# ---------------------------------------------------------------------------
# Visibilidad
# ---------------------------------------------------------------------------

def test_novedades_muestra_publicacion_propia_y_ajena(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)
    _publicar(u1, date(2026, 9, 1), date(2026, 9, 2))
    _publicar(u2, date(2026, 9, 5), date(2026, 9, 6))
    resp = client.get("/novedades")
    assert b"01/09/2026" in resp.data
    assert b"05/09/2026" in resp.data


def test_novedades_no_muestra_publicacion_de_otra_categoria(client, db):
    u1 = _usuario(email="u1@test.es", cat_nombre="Enfermería")
    u2 = _usuario(email="u2@test.es", cat_nombre="Auxiliar de enfermería (TCAE)")
    _login(client, u1.email)
    _publicar(u2, date(2026, 9, 5), date(2026, 9, 6))
    resp = client.get("/novedades")
    assert b"05/09/2026" not in resp.data


def test_novedades_no_muestra_publicacion_de_otro_grupo(client, db):
    u1 = _usuario(email="u1@test.es", hospital="H1", unidad="Urgencias")
    u2 = _usuario(email="u2@test.es", hospital="H2", unidad="UCI")
    _login(client, u1.email)
    _publicar(u2, date(2026, 9, 5), date(2026, 9, 6))
    resp = client.get("/novedades")
    assert b"05/09/2026" not in resp.data


def test_novedades_no_muestra_publicaciones_cerradas_o_caducadas(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)
    _publicar(u2, date(2026, 9, 5), date(2026, 9, 6), estado="confirmada")
    _publicar(u2, date(2026, 9, 7), date(2026, 9, 8), estado="cancelada")
    _publicar(u2, date(2026, 9, 9), date(2026, 9, 10), estado="caducada")
    resp = client.get("/novedades")
    assert b"05/09/2026" not in resp.data
    assert b"07/09/2026" not in resp.data
    assert b"09/09/2026" not in resp.data


# ---------------------------------------------------------------------------
# Orden LIFO y paginación
# ---------------------------------------------------------------------------

def test_novedades_orden_lifo_mas_reciente_primero(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)
    _publicar(u2, date(2026, 9, 1), date(2026, 9, 2))
    _publicar(u2, date(2026, 9, 10), date(2026, 9, 11))
    resp = client.get("/novedades")
    cuerpo = resp.data.decode("utf-8")
    assert cuerpo.index("10/09/2026") < cuerpo.index("01/09/2026")


def test_novedades_mas_devuelve_siguiente_lote(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)
    pubs = [_publicar(u2, date(2026, 9, d), date(2026, 9, d + 1)) for d in range(1, 23, 2)]
    assert len(pubs) >= 11

    resp = client.get("/novedades")
    assert resp.status_code == 200

    resp_mas = client.get(f"/novedades/mas?despues_id={pubs[-1].id}")
    assert resp_mas.status_code == 200
    assert b"01/09/2026" in resp_mas.data


def test_novedades_mas_sin_resultados_devuelve_vacio(client, db):
    u1 = _usuario(email="u1@test.es")
    _login(client, u1.email)
    resp = client.get("/novedades/mas?despues_id=999999")
    assert resp.status_code == 200
    assert resp.data.strip() == b""


# ---------------------------------------------------------------------------
# Botones "Me interesa" / "Contraoferta"
# ---------------------------------------------------------------------------

def test_novedades_muestra_boton_me_interesa_y_contraoferta_para_publicacion_ajena(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)
    pub = _publicar(u2, date(2026, 9, 5), date(2026, 9, 6))
    resp = client.get("/novedades")
    cuerpo = resp.data.decode("utf-8")
    assert "abrirMeInteresaNovedad(this)" in cuerpo
    assert f'data-pub-id="{pub.id}"' in cuerpo
    assert f"/cambios/{pub.id}/contraoferta" in cuerpo


def test_novedades_no_muestra_botones_para_publicacion_propia(client, db):
    u1 = _usuario(email="u1@test.es")
    _login(client, u1.email)
    _publicar(u1, date(2026, 9, 1), date(2026, 9, 2))
    resp = client.get("/novedades")
    cuerpo = resp.data.decode("utf-8")
    assert "abrirMeInteresaNovedad(this)" not in cuerpo


def test_novedades_mas_incluye_boton_me_interesa_en_publicaciones_paginadas(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)
    pubs = [_publicar(u2, date(2026, 9, d), date(2026, 9, d + 1)) for d in range(1, 23, 2)]
    client.get("/novedades")
    resp_mas = client.get(f"/novedades/mas?despues_id={pubs[-1].id}")
    cuerpo = resp_mas.data.decode("utf-8")
    assert "abrirMeInteresaNovedad(this)" in cuerpo
