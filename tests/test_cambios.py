"""Tests de integración para el visor de cambios publicados (/cambios)."""
from datetime import date, timedelta

from app.extensions import db
from app.models import (
    Categoria, FranjaHoraria, PublicacionCambio, TurnoCedido, TurnoAceptado,
    insertar_categorias_semilla,
)
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


def _publicar(usuario, fecha_cede, fecha_acepta):
    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=usuario.unidad.grupo_intercambio_id
    ).first()
    pub = PublicacionCambio(usuario_id=usuario.id)
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=fecha_cede, franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=fecha_acepta, franja_horaria_id=franja.id))
    db.session.commit()
    return pub


# ---------------------------------------------------------------------------
# Acceso
# ---------------------------------------------------------------------------

def test_cambios_requiere_login(client, db):
    resp = client.get("/cambios", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_cambios_accesible_autenticado(client, db):
    u = _usuario()
    _login(client, u.email)
    resp = client.get("/cambios")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Visibilidad
# ---------------------------------------------------------------------------

def test_cambios_no_muestra_publicaciones_propias(client, db):
    u = _usuario()
    _login(client, u.email)
    _publicar(u, date(2026, 9, 1), date(2026, 9, 2))
    resp = client.get("/cambios")
    assert b"Test" not in resp.data or resp.data.count(b"Test") == 1  # solo el nav
    assert PublicacionCambio.query.count() == 1  # hay publicación pero no se muestra


def test_cambios_muestra_publicacion_de_mismo_grupo_y_categoria(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")  # mismo hospital/unidad → mismo grupo
    _login(client, u1.email)
    _publicar(u2, date(2026, 9, 5), date(2026, 9, 6))
    resp = client.get("/cambios")
    assert resp.status_code == 200
    assert b"05/09/2026" in resp.data


def test_cambios_no_muestra_publicacion_de_otra_categoria(client, db):
    u1 = _usuario(email="u1@test.es", cat_nombre="Enfermería")
    u2 = _usuario(email="u2@test.es", cat_nombre="Auxiliar de enfermería (TCAE)")
    _login(client, u1.email)
    _publicar(u2, date(2026, 9, 5), date(2026, 9, 6))
    resp = client.get("/cambios")
    assert b"05/09/2026" not in resp.data


def test_cambios_no_muestra_publicacion_de_otro_grupo(client, db):
    u1 = _usuario(email="u1@test.es", hospital="H1", unidad="Urgencias")
    u2 = _usuario(email="u2@test.es", hospital="H2", unidad="UCI")  # grupo diferente
    _login(client, u1.email)
    _publicar(u2, date(2026, 9, 5), date(2026, 9, 6))
    resp = client.get("/cambios")
    assert b"05/09/2026" not in resp.data


# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------

def test_cambios_filtro_mes(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)
    _publicar(u2, date(2026, 9, 5), date(2026, 9, 6))   # septiembre
    _publicar(u2, date(2026, 10, 5), date(2026, 10, 6))  # octubre

    resp_sep = client.get("/cambios?mes=9")
    assert b"05/09/2026" in resp_sep.data
    assert b"05/10/2026" not in resp_sep.data

    resp_oct = client.get("/cambios?mes=10")
    assert b"05/10/2026" in resp_oct.data
    assert b"05/09/2026" not in resp_oct.data


def test_cambios_filtro_dia(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)
    _publicar(u2, date(2026, 9, 5), date(2026, 9, 6))   # día 5
    _publicar(u2, date(2026, 9, 15), date(2026, 9, 16))  # día 15

    resp = client.get("/cambios?dia=5")
    assert b"05/09/2026" in resp.data
    assert b"15/09/2026" not in resp.data


def test_cambios_filtro_mes_y_dia(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)
    _publicar(u2, date(2026, 9, 5), date(2026, 9, 6))
    _publicar(u2, date(2026, 10, 5), date(2026, 10, 6))

    resp = client.get("/cambios?mes=9&dia=5")
    assert b"05/09/2026" in resp.data
    assert b"05/10/2026" not in resp.data


def test_cambios_sin_filtro_muestra_todas_del_grupo(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)
    _publicar(u2, date(2026, 9, 1), date(2026, 9, 2))
    _publicar(u2, date(2026, 10, 1), date(2026, 10, 2))

    resp = client.get("/cambios")
    assert b"01/09/2026" in resp.data
    assert b"01/10/2026" in resp.data


def test_cambios_filtro_usuario_por_nombre(client, db):
    from app.services.registro import registrar_usuario as reg
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    u1 = reg("Ana García", "u1@test.es", "pass123", "H1", "Urgencias", cat.id)
    u2 = reg("Pedro López", "u2@test.es", "pass123", "H1", "Urgencias", cat.id)
    db.session.commit()
    _login(client, u1.email)
    _publicar(u2, date(2026, 9, 1), date(2026, 9, 2))

    resp = client.get("/cambios?usuario=Pedro")
    assert b"01/09/2026" in resp.data

    resp2 = client.get("/cambios?usuario=Ana")
    assert b"01/09/2026" not in resp2.data


def test_cambios_filtro_usuario_insensible_a_mayusculas(client, db):
    from app.services.registro import registrar_usuario as reg
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    u1 = reg("Ana García", "u1@test.es", "pass123", "H1", "Urgencias", cat.id)
    u2 = reg("Pedro López", "u2@test.es", "pass123", "H1", "Urgencias", cat.id)
    db.session.commit()
    _login(client, u1.email)
    _publicar(u2, date(2026, 9, 1), date(2026, 9, 2))

    assert b"01/09/2026" in client.get("/cambios?usuario=pedro").data
    assert b"01/09/2026" in client.get("/cambios?usuario=PEDRO").data
    assert b"01/09/2026" in client.get("/cambios?usuario=pEdRo").data


def test_cambios_filtro_dia_incluye_turno_aceptado(client, db):
    """El filtro por día muestra publicaciones cuyo turno aceptado coincide, no solo el cedido."""
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)
    # u2 quiere librar el día 5, se ofrece a trabajar el día 10
    _publicar(u2, date(2026, 9, 5), date(2026, 9, 10))

    resp = client.get("/cambios?dia=10")
    assert b"05/09/2026" in resp.data


def test_cambios_filtro_mes_incluye_turno_aceptado(client, db):
    """El filtro por mes muestra publicaciones cuyo turno aceptado coincide."""
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)
    # u2 quiere librar en septiembre, se ofrece a trabajar en octubre
    _publicar(u2, date(2026, 9, 5), date(2026, 10, 1))

    resp = client.get("/cambios?mes=10")
    assert b"05/09/2026" in resp.data


def test_cambios_filtro_mes_y_dia_incluye_turno_aceptado(client, db):
    """El filtro combinado mes+día también busca en el turno aceptado."""
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)
    # cedido: 5 sep | aceptado: 1 oct
    _publicar(u2, date(2026, 9, 5), date(2026, 10, 1))

    resp = client.get("/cambios?mes=10&dia=1")
    assert b"05/09/2026" in resp.data


def test_cambios_filtro_tipo_cambio(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)

    pub_cambio = _publicar(u2, date(2026, 9, 1), date(2026, 9, 2))

    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u2.unidad.grupo_intercambio_id
    ).first()
    pub_regalo = PublicacionCambio(usuario_id=u2.id, tipo="regalo")
    db.session.add(pub_regalo)
    db.session.flush()
    db.session.add(TurnoAceptado(publicacion_id=pub_regalo.id, fecha=date(2026, 9, 3), franja_horaria_id=franja.id))
    db.session.commit()

    resp = client.get("/cambios?tipo=cambio")
    assert b"01/09/2026" in resp.data
    assert b"03/09/2026" not in resp.data


def test_cambios_filtro_tipo_regalo(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)

    _publicar(u2, date(2026, 9, 1), date(2026, 9, 2))  # cambio normal

    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u2.unidad.grupo_intercambio_id
    ).first()
    pub_regalo = PublicacionCambio(usuario_id=u2.id, tipo="regalo")
    db.session.add(pub_regalo)
    db.session.flush()
    db.session.add(TurnoAceptado(publicacion_id=pub_regalo.id, fecha=date(2026, 9, 10), franja_horaria_id=franja.id))
    db.session.commit()

    resp = client.get("/cambios?tipo=regalo")
    assert b"10/09/2026" in resp.data
    assert b"01/09/2026" not in resp.data


def test_cambios_sin_filtro_tipo_muestra_todos(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)

    _publicar(u2, date(2026, 9, 1), date(2026, 9, 2))

    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u2.unidad.grupo_intercambio_id
    ).first()
    pub_regalo = PublicacionCambio(usuario_id=u2.id, tipo="regalo")
    db.session.add(pub_regalo)
    db.session.flush()
    db.session.add(TurnoAceptado(publicacion_id=pub_regalo.id, fecha=date(2026, 9, 10), franja_horaria_id=franja.id))
    db.session.commit()

    resp = client.get("/cambios")
    assert b"01/09/2026" in resp.data
    assert b"10/09/2026" in resp.data


def test_cambios_filtro_franja(client, db):
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)

    grupo_id = u2.unidad.grupo_intercambio_id
    franjas = FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id).order_by(FranjaHoraria.hora_inicio).all()
    assert len(franjas) >= 2, "Se necesitan al menos 2 franjas para este test"
    franja_a, franja_b = franjas[0], franjas[1]

    # Publicación con franja_a como cedido y franja_b como aceptado
    pub = PublicacionCambio(usuario_id=u2.id)
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=date(2026, 9, 1), franja_horaria_id=franja_a.id))
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=date(2026, 9, 2), franja_horaria_id=franja_b.id))
    db.session.commit()

    # La publicación aparece al filtrar por franja_a (está en cedidos)
    resp_a = client.get(f"/cambios?franja={franja_a.id}")
    assert b"01/09/2026" in resp_a.data

    # También aparece al filtrar por franja_b (está en aceptados — incluye regalos)
    resp_b = client.get(f"/cambios?franja={franja_b.id}")
    assert b"02/09/2026" in resp_b.data

    # Una franja que no aparece en ninguna parte no devuelve la publicación
    if len(franjas) >= 3:
        franja_c = franjas[2]
        resp_c = client.get(f"/cambios?franja={franja_c.id}")
        assert b"01/09/2026" not in resp_c.data


def test_cambios_junte_muestra_resumen_noches_y_dias(client, db):
    """En /cambios, un junte de noches muestra el número de noches del autor
    y los días de la semana que busca trabajar y librar tras el junte."""
    # Javier publica el junte
    javier = _usuario(email="javier@test.es")
    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=javier.unidad.grupo_intercambio_id
    ).first()
    # 2026-08-03 es lunes (comprobado: 2026 empieza jueves, +213 días = lunes)
    lunes = date(2026, 8, 3)
    pub = PublicacionCambio(usuario_id=javier.id, tipo="junte")
    db.session.add(pub)
    db.session.flush()
    # LMVD: cede Viernes(+4) y Domingo(+6)
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=lunes + timedelta(days=4), franja_horaria_id=franja.id))
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=lunes + timedelta(days=6), franja_horaria_id=franja.id))
    # Recibe Martes(+1) y Jueves(+3)
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=lunes + timedelta(days=1), franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=lunes + timedelta(days=3), franja_horaria_id=franja.id))
    db.session.commit()

    # Ana (mismo grupo y categoría) ve la publicación en /cambios
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario("Ana", "ana@test.es", "pass123", "H1", "Urgencias", cat.id)
    db.session.commit()
    _login(client, "ana@test.es")

    resp = client.get("/cambios")
    html = resp.data.decode()

    # Número de noches (LMVD = 4)
    assert "4 noches" in html
    # Busca trabajar: lunes y miércoles (LMVD que guarda) + martes y jueves (MJS que recibe)
    assert "Busca trabajar" in html
    assert "lunes" in html
    assert "martes" in html
    assert "miércoles" in html
    assert "jueves" in html
    # Busca librar: viernes y domingo (LMVD cedidos) + sábado (MJS no recibido)
    assert "Busca librar" in html
    assert "viernes" in html
    assert "sábado" in html
    assert "domingo" in html


# ---------------------------------------------------------------------------
# Filtro tipo_fecha (cedido / aceptado)
# ---------------------------------------------------------------------------

def _setup_dos_pubs(db):
    """
    u1 y u2 en el mismo grupo/categoría.
    pub_a (de u2): cede el día 10, acepta el día 25 → aparece con tipo_fecha=cedido&dia=10
    pub_b (de u2): cede el día 25, acepta el día 10 → aparece con tipo_fecha=aceptado&dia=10
    Sin tipo_fecha: ambas aparecen (una tiene cedido=10, la otra aceptado=10).
    La fecha del cedido exclusivo de pub_b (25/09) solo aparece en HTML si pub_b se muestra.
    """
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _publicar(u2, date(2026, 9, 10), date(2026, 9, 25))  # pub_a
    _publicar(u2, date(2026, 9, 25), date(2026, 9, 10))  # pub_b
    return u1


def test_tipo_fecha_cedido_excluye_pubs_sin_cedido_en_esa_fecha(client, db):
    """tipo_fecha=cedido filtra pubs cuyo cedido NO está en la fecha — pub_b debe desaparecer."""
    u1 = _setup_dos_pubs(db)
    _login(client, u1.email)
    resp = client.get("/cambios?dia=10&mes=9&tipo_fecha=cedido")
    html = resp.data.decode()
    # pub_a (cedido=10) debe aparecer; pub_b (cedido=25, aceptado=10) debe desaparecer.
    # "25/09/2026" aparece máx 2 veces si solo pub_a está (card + JSON inline).
    # Si pub_b también está habría 4 apariciones (2 de pub_a aceptado + 2 de pub_b cedido).
    assert "10/09/2026" in html
    assert html.count("25/09/2026") <= 2


def test_tipo_fecha_aceptado_excluye_pubs_sin_aceptado_en_esa_fecha(client, db):
    """tipo_fecha=aceptado filtra pubs cuyo aceptado NO está en la fecha — pub_a debe desaparecer."""
    u1 = _setup_dos_pubs(db)
    _login(client, u1.email)
    resp = client.get("/cambios?dia=10&mes=9&tipo_fecha=aceptado")
    html = resp.data.decode()
    # pub_b (aceptado=10) debe aparecer; pub_a (cedido=10, aceptado=25) debe desaparecer.
    assert "10/09/2026" in html
    assert html.count("25/09/2026") <= 2


def test_tipo_fecha_sin_valor_muestra_ambas_pubs(client, db):
    """Sin tipo_fecha: comportamiento original — cedido OR aceptado (ambas aparecen)."""
    u1 = _setup_dos_pubs(db)
    _login(client, u1.email)
    resp = client.get("/cambios?dia=10&mes=9")
    html = resp.data.decode()
    # Ambas aparecen → "25/09/2026" aparece al menos 4 veces (card+JSON × 2 pubs)
    assert html.count("25/09/2026") >= 4


def test_cambios_filtro_tipo_sintetica(client, db):
    """tipo=sintetica muestra solo publicaciones sintéticas y excluye las normales."""
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    _login(client, u1.email)

    pub_normal = _publicar(u2, date(2026, 9, 1), date(2026, 9, 2))

    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u2.unidad.grupo_intercambio_id
    ).first()
    pub_sint = PublicacionCambio(usuario_id=u2.id, es_sintetica=True, sintetica_pub_a_id=pub_normal.id)
    db.session.add(pub_sint)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub_sint.id, fecha=date(2026, 9, 10), franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub_sint.id, fecha=date(2026, 9, 20), franja_horaria_id=franja.id))
    db.session.commit()

    resp = client.get("/cambios?tipo=sintetica")
    html = resp.data.decode()
    assert "10/09/2026" in html
    assert "01/09/2026" not in html


def test_cambios_muestra_oportunidad_a_4_para_sintetica_con_intermedio(client, db):
    """Una sintética de cadena_4 (con banda intermedia) se etiqueta 'Oportunidad
    a 4' en el buscador, distinta de la 'Oportunidad a 3' genérica."""
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    u3 = _usuario(email="u3@test.es")
    u4 = _usuario(email="u4@test.es")
    _login(client, u1.email)

    pub_a = _publicar(u2, date(2026, 9, 1), date(2026, 9, 2))
    pub_intermedio = _publicar(u3, date(2026, 9, 5), date(2026, 9, 6))
    pub_c = _publicar(u4, date(2026, 9, 7), date(2026, 9, 8))

    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u2.unidad.grupo_intercambio_id
    ).first()
    pub_sint = PublicacionCambio(
        usuario_id=u2.id, es_sintetica=True,
        sintetica_pub_a_id=pub_a.id, sintetica_pub_b_id=pub_c.id,
        sintetica_pub_intermedio_id=pub_intermedio.id,
    )
    db.session.add(pub_sint)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub_sint.id, fecha=date(2026, 9, 10), franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub_sint.id, fecha=date(2026, 9, 20), franja_horaria_id=franja.id))
    db.session.commit()

    resp = client.get("/cambios?tipo=sintetica_4")
    html = resp.data.decode()
    assert "Oportunidad a 4" in html

    # El resto de la cadena (A cede a B, B cede a C) también debe verse,
    # no solo los dos extremos (lo que el viewer trabajaría/le trabajarían).
    assert "01/09/2026" in html  # turno cedido de pub_a (A libra, B trabaja)
    assert "05/09/2026" in html  # turno cedido de pub_intermedio (B libra, C trabaja)


def test_cambios_filtro_tipo_sintetica_4(client, db):
    """tipo=sintetica_4 muestra solo sintéticas de cadena_4 (con banda
    intermedia) y excluye las de cadena_3."""
    u1 = _usuario(email="u1@test.es")
    u2 = _usuario(email="u2@test.es")
    u3 = _usuario(email="u3@test.es")
    _login(client, u1.email)

    intermedio = _publicar(u3, date(2026, 9, 3), date(2026, 9, 4))

    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u2.unidad.grupo_intercambio_id
    ).first()

    sint_3 = PublicacionCambio(usuario_id=u2.id, es_sintetica=True)
    db.session.add(sint_3)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=sint_3.id, fecha=date(2026, 9, 11), franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=sint_3.id, fecha=date(2026, 9, 21), franja_horaria_id=franja.id))

    sint_4 = PublicacionCambio(usuario_id=u2.id, es_sintetica=True, sintetica_pub_intermedio_id=intermedio.id)
    db.session.add(sint_4)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=sint_4.id, fecha=date(2026, 9, 12), franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=sint_4.id, fecha=date(2026, 9, 22), franja_horaria_id=franja.id))
    db.session.commit()

    resp = client.get("/cambios?tipo=sintetica_4")
    html = resp.data.decode()
    assert "12/09/2026" in html
    assert "11/09/2026" not in html
