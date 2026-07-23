from datetime import time
from app.models import Hospital, GrupoIntercambio, Unidad, Categoria, Usuario


def _crear_usuario(db, es_supervisora, email, sufijo="a"):
    hospital = Hospital(nombre=f"H-{sufijo}")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    unidad = Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo)
    categoria = Categoria(nombre=f"Cat-{sufijo}")
    db.session.add_all([unidad, categoria])
    db.session.commit()

    usuario = Usuario(
        nombre="Ana", email=email, unidad=unidad, categoria=categoria,
        es_supervisora=es_supervisora,
    )
    usuario.set_password("pass")
    db.session.add(usuario)
    db.session.commit()
    return usuario, grupo


def _login(client, email):
    client.post("/auth/login", data={"email": email, "password": "pass"})


def test_grupo_intercambio_tiene_limite_de_8_dias_consecutivos_por_defecto(db):
    grupo = GrupoIntercambio()
    db.session.add(grupo)
    db.session.commit()
    assert grupo.limite_dias_consecutivos == 8


def test_get_reglas_requiere_supervisora(client, db):
    usuario, _ = _crear_usuario(db, es_supervisora=False, email="normal@test.es")
    _login(client, usuario.email)
    resp = client.get("/planilla/supervision/reglas")
    assert resp.status_code == 403


def test_get_reglas_muestra_el_limite_actual(client, db):
    usuario, grupo = _crear_usuario(db, es_supervisora=True, email="sup@test.es")
    _login(client, usuario.email)
    resp = client.get("/planilla/supervision/reglas")
    assert resp.status_code == 200
    assert b"8" in resp.data


def test_post_reglas_actualiza_el_limite(client, db):
    usuario, grupo = _crear_usuario(db, es_supervisora=True, email="sup2@test.es")
    _login(client, usuario.email)
    resp = client.post("/planilla/supervision/reglas", data={
        "limite_dias_consecutivos": "10",
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(grupo)
    assert grupo.limite_dias_consecutivos == 10


def test_post_reglas_rechaza_valores_no_positivos(client, db):
    usuario, grupo = _crear_usuario(db, es_supervisora=True, email="sup3@test.es")
    _login(client, usuario.email)
    resp = client.post("/planilla/supervision/reglas", data={
        "limite_dias_consecutivos": "0",
    }, follow_redirects=True)
    assert resp.status_code == 200
    db.session.refresh(grupo)
    assert grupo.limite_dias_consecutivos == 8
