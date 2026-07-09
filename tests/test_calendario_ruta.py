"""Tests de la ruta /calendario (Paso 2): navegación mensual + wiring con
el servicio construir_calendario_mes. Sin drill-down todavía (Paso 4)."""
from datetime import date

from app.extensions import db
from app.models import (
    Categoria,
    FranjaHoraria,
    PublicacionCambio,
    TurnoAceptado,
    TurnoCedido,
    insertar_categorias_semilla,
)
from app.services.registro import registrar_usuario


def _usuario(nombre, email, hospital="H1", unidad="Urgencias"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario(nombre, email, "password123", hospital, unidad, cat.id)


def _login(client, email):
    client.post("/auth/login", data={"email": email, "password": "password123"})


def _franja(grupo_id, nombre="Mañana"):
    return FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id, nombre=nombre).first()


def test_calendario_requiere_login(client, db):
    resp = client.get("/calendario/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_calendario_get_default_devuelve_200(client, db):
    u = _usuario("Ana", "ana@test.es")
    _login(client, u.email)
    resp = client.get("/calendario/")
    assert resp.status_code == 200


def test_calendario_navegacion_mes_siguiente_y_anterior(client, db):
    u = _usuario("Ana", "ana@test.es")
    _login(client, u.email)
    resp = client.get("/calendario/?anyo=2026&mes=7")
    assert resp.status_code == 200
    assert b"anyo=2026&amp;mes=8" in resp.data or b"mes=8" in resp.data
    assert b"mes=6" in resp.data


def test_calendario_modo_invalido_usa_ofertas_por_defecto(client, db):
    u = _usuario("Ana", "ana@test.es")
    _login(client, u.email)
    resp = client.get("/calendario/?modo=noexiste")
    assert resp.status_code == 200
    assert b'data-modo-actual="ofertas"' in resp.data


def test_calendario_modo_ofertas_muestra_franja_del_turno_aceptado(client, db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = ana.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")

    pub = PublicacionCambio(usuario_id=pedro.id, tipo="regalo")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=date(2026, 7, 3), franja_horaria_id=manana.id))
    db.session.commit()

    _login(client, ana.email)
    resp = client.get("/calendario/?anyo=2026&mes=7&modo=ofertas")
    assert resp.status_code == 200
    assert "Mañana".encode("utf-8") in resp.data


def test_calendario_modo_peticiones_muestra_franja_del_turno_cedido(client, db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = ana.unidad.grupo_intercambio_id
    tarde = _franja(gid, "Tarde")

    pub = PublicacionCambio(usuario_id=pedro.id, tipo="peticion")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=date(2026, 7, 5), franja_horaria_id=tarde.id))
    db.session.commit()

    _login(client, ana.email)
    resp = client.get("/calendario/?anyo=2026&mes=7&modo=peticiones")
    assert resp.status_code == 200
    assert "Tarde".encode("utf-8") in resp.data


def test_calendario_modo_juntes_muestra_franja_de_junte(client, db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = ana.unidad.grupo_intercambio_id
    noche = _franja(gid, "Noche")

    pub = PublicacionCambio(usuario_id=pedro.id, tipo="junte")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=date(2026, 7, 3), franja_horaria_id=noche.id))
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=date(2026, 7, 1), franja_horaria_id=noche.id))
    db.session.commit()

    _login(client, ana.email)
    resp = client.get("/calendario/?anyo=2026&mes=7&modo=juntes")
    assert resp.status_code == 200
    assert "Noche".encode("utf-8") in resp.data

    import json
    import re
    html = resp.data.decode("utf-8")
    datos_mes = json.loads(re.search(
        r'<script type="application/json" id="calendario-datos-mes">(.*?)</script>', html, re.S
    ).group(1))
    assert datos_mes["2026-07-01"][str(noche.id)] == [pub.id]
    assert datos_mes["2026-07-03"][str(noche.id)] == [pub.id]


def test_calendario_modo_juntes_etiqueta_publicacion_como_junte(client, db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = ana.unidad.grupo_intercambio_id
    noche = _franja(gid, "Noche")

    pub = PublicacionCambio(usuario_id=pedro.id, tipo="junte")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=date(2026, 7, 1), franja_horaria_id=noche.id))
    db.session.commit()

    _login(client, ana.email)
    resp = client.get("/calendario/?anyo=2026&mes=7&modo=juntes")
    assert resp.status_code == 200

    import json
    import re
    html = resp.data.decode("utf-8")
    datos_pubs = json.loads(re.search(
        r'<script type="application/json" id="calendario-datos-publicaciones">(.*?)</script>', html, re.S
    ).group(1))
    assert datos_pubs[str(pub.id)]["tipo_label"] == "Junte de noches"


def test_calendario_modo_ofertas_no_muestra_juntes(client, db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = ana.unidad.grupo_intercambio_id
    noche = _franja(gid, "Noche")

    pub = PublicacionCambio(usuario_id=pedro.id, tipo="junte")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=date(2026, 7, 1), franja_horaria_id=noche.id))
    db.session.commit()

    _login(client, ana.email)
    resp = client.get("/calendario/?anyo=2026&mes=7&modo=ofertas")
    assert resp.status_code == 200
    assert "Noche".encode("utf-8") not in resp.data


def test_calendario_no_muestra_publicaciones_de_categoria_distinta(client, db):
    insertar_categorias_semilla()
    cat_enf = Categoria.query.filter_by(nombre="Enfermería").first()
    cat_aux = Categoria.query.filter_by(nombre="Auxiliar de enfermería (TCAE)").first()
    ana = registrar_usuario("Ana", "ana@test.es", "password123", "H1", "Urgencias", cat_enf.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "H1", "Urgencias", cat_aux.id)

    gid = ana.unidad.grupo_intercambio_id
    noche = _franja(gid, "Noche")
    pub = PublicacionCambio(usuario_id=pedro.id, tipo="regalo")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=date(2026, 7, 9), franja_horaria_id=noche.id))
    db.session.commit()

    _login(client, ana.email)
    resp = client.get("/calendario/?anyo=2026&mes=7&modo=ofertas")
    assert resp.status_code == 200
    assert "Noche".encode("utf-8") not in resp.data


def test_calendario_embebe_datos_para_drilldown(client, db):
    """Paso 4: los datos del mes (día→franja→pubs, resumen por pub) se embeben
    como JSON en la página para el drill-down en JS, sin llamadas adicionales."""
    import json
    import re

    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = ana.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")

    pub = PublicacionCambio(usuario_id=pedro.id, tipo="regalo")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=date(2026, 7, 3), franja_horaria_id=manana.id))
    db.session.commit()

    _login(client, ana.email)
    resp = client.get("/calendario/?anyo=2026&mes=7&modo=ofertas")
    assert resp.status_code == 200

    html = resp.data.decode("utf-8")
    m_calendario = re.search(
        r'<script type="application/json" id="calendario-datos-mes">(.*?)</script>', html, re.S
    )
    m_pubs = re.search(
        r'<script type="application/json" id="calendario-datos-publicaciones">(.*?)</script>', html, re.S
    )
    assert m_calendario is not None
    assert m_pubs is not None

    datos_mes = json.loads(m_calendario.group(1))
    datos_pubs = json.loads(m_pubs.group(1))

    assert datos_mes["2026-07-03"][str(manana.id)] == [pub.id]
    assert datos_pubs[str(pub.id)]["usuario_nombre"] == "Pedro"
    assert datos_pubs[str(pub.id)]["tipo_label"]


def test_calendario_muestra_boton_publicar_cambio_fijo(client, db):
    """Ronda 2, Paso 3: botón fijo de publicar bajo el calendario."""
    u = _usuario("Ana", "ana@test.es")
    _login(client, u.email)
    resp = client.get("/calendario/")
    assert resp.status_code == 200
    assert b'href="/publicar"' in resp.data
    assert "Publicar cambio".encode("utf-8") in resp.data


def test_calendario_titulo_corto_y_boton_ayuda(client, db):
    """Ronda 2, Paso 4: título corto + icono ⓘ con banner de ayuda inline."""
    u = _usuario("Ana", "ana@test.es")
    _login(client, u.email)
    resp = client.get("/calendario/")
    assert resp.status_code == 200
    assert b"<h1>Calendario</h1>" in resp.data
    assert b"Calendario de cambios" not in resp.data
    assert b'id="calendario-onboarding"' in resp.data
    assert "¿Cómo funciona?".encode("utf-8") in resp.data


def test_calendario_muestra_oportunidad_a_3_para_sintetica(client, db):
    """Las publicaciones sintéticas (oportunidades a 3 bandas) se etiquetan
    de forma distinta en los datos del drill-down, no como "Cambio" normal."""
    import json
    import re

    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = ana.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")

    sint = PublicacionCambio(usuario_id=pedro.id, tipo="cambio", es_sintetica=True)
    db.session.add(sint)
    db.session.flush()
    # Para una sintética, 'ofertas' se alimenta de turno_cedido (ver
    # crear_pub_sintetica: su cedido copia el aceptado real de pub_a).
    db.session.add(TurnoCedido(publicacion_id=sint.id, fecha=date(2026, 7, 3), franja_horaria_id=manana.id))
    db.session.commit()

    _login(client, ana.email)
    resp = client.get("/calendario/?anyo=2026&mes=7&modo=ofertas")
    assert resp.status_code == 200

    html = resp.data.decode("utf-8")
    m_pubs = re.search(
        r'<script type="application/json" id="calendario-datos-publicaciones">(.*?)</script>', html, re.S
    )
    datos_pubs = json.loads(m_pubs.group(1))
    assert datos_pubs[str(sint.id)]["tipo_label"] == "Oportunidad a 3"
