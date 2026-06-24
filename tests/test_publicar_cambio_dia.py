"""Tests del tipo de publicación 'cambio de turno en el día'."""
from datetime import date, timedelta

from app.extensions import db
from app.models import (
    Categoria, FranjaHoraria, PublicacionCambio,
    TurnoCedido, TurnoAceptado, insertar_categorias_semilla,
)
from app.services.publicaciones import publicar_cambio
from app.services.registro import registrar_usuario
from app.services.caducidad import caducar_publicaciones_expiradas


def _setup(client, email="u1@test.es", nombre="Ana"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    u = registrar_usuario(nombre, email, "pass1234", "H", "U", cat.id)
    client.post("/auth/login", data={"email": email, "password": "pass1234"})
    return u


def _franjas(usuario):
    return (
        FranjaHoraria.query
        .filter_by(grupo_intercambio_id=usuario.unidad.grupo_intercambio_id)
        .order_by(FranjaHoraria.hora_inicio)
        .all()
    )


def _post_cambio_dia(client, fecha, franja_cedida_id, franja_aceptada_id):
    return client.post("/publicar", data={
        "tipo": "cambio_dia",
        "fecha_cambio_dia": fecha.isoformat(),
        "franja_cedida_dia": str(franja_cedida_id),
        "franja_aceptada_dia": str(franja_aceptada_id),
    }, follow_redirects=False)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_cambio_dia_crea_publicacion(client, db):
    u = _setup(client)
    fs = _franjas(u)
    fecha = date.today() + timedelta(days=3)
    resp = _post_cambio_dia(client, fecha, fs[0].id, fs[1].id)
    assert resp.status_code == 302
    pub = PublicacionCambio.query.filter_by(usuario_id=u.id).first()
    assert pub is not None
    assert pub.tipo == "cambio_dia"


def test_cambio_dia_un_cedido_y_un_aceptado_misma_fecha(client, db):
    u = _setup(client)
    fs = _franjas(u)
    fecha = date.today() + timedelta(days=3)
    _post_cambio_dia(client, fecha, fs[0].id, fs[1].id)
    pub = PublicacionCambio.query.filter_by(usuario_id=u.id).first()
    assert len(pub.turnos_cedidos) == 1
    assert len(pub.turnos_aceptados) == 1
    assert pub.turnos_cedidos[0].fecha == fecha
    assert pub.turnos_aceptados[0].fecha == fecha
    assert pub.turnos_cedidos[0].franja_horaria_id == fs[0].id
    assert pub.turnos_aceptados[0].franja_horaria_id == fs[1].id


# ---------------------------------------------------------------------------
# Validaciones
# ---------------------------------------------------------------------------

def test_cambio_dia_rechaza_misma_franja(client, db):
    u = _setup(client)
    fs = _franjas(u)
    fecha = date.today() + timedelta(days=3)
    resp = _post_cambio_dia(client, fecha, fs[0].id, fs[0].id)
    assert resp.status_code == 200
    assert PublicacionCambio.query.filter_by(usuario_id=u.id).first() is None


def test_cambio_dia_rechaza_fecha_pasada(client, db):
    u = _setup(client)
    fs = _franjas(u)
    ayer = date.today() - timedelta(days=1)
    resp = _post_cambio_dia(client, ayer, fs[0].id, fs[1].id)
    assert resp.status_code == 200
    assert PublicacionCambio.query.filter_by(usuario_id=u.id).first() is None


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def test_cambio_dia_match_simetrico(client, db):
    """A cede franja-0 y quiere franja-1; B cede franja-1 y quiere franja-0 → match."""
    u1 = _setup(client, "u1@test.es", "Ana")
    client.get("/auth/logout")
    u2 = _setup(client, "u2@test.es", "Bea")

    fs = _franjas(u2)
    fecha = date.today() + timedelta(days=5)

    pub1 = publicar_cambio(u1.id, [(fecha, fs[0].id)], [(fecha, fs[1].id)], tipo="cambio_dia")
    db.session.commit()
    pub2 = publicar_cambio(u2.id, [(fecha, fs[1].id)], [(fecha, fs[0].id)], tipo="cambio_dia")
    db.session.commit()

    from app.matching.service import buscar_matches_para
    assert pub1 in buscar_matches_para(pub2)
    assert pub2 in buscar_matches_para(pub1)


def test_cambio_dia_no_match_franjas_no_cruzadas(client, db):
    """A cede franja-0, quiere franja-2; B cede franja-1, quiere franja-0 → sin match."""
    u1 = _setup(client, "u1@test.es", "Ana")
    client.get("/auth/logout")
    u2 = _setup(client, "u2@test.es", "Bea")

    fs = _franjas(u2)
    assert len(fs) >= 3, "Este test necesita al menos 3 franjas"
    fecha = date.today() + timedelta(days=5)

    pub1 = publicar_cambio(u1.id, [(fecha, fs[0].id)], [(fecha, fs[2].id)], tipo="cambio_dia")
    db.session.commit()
    pub2 = publicar_cambio(u2.id, [(fecha, fs[1].id)], [(fecha, fs[0].id)], tipo="cambio_dia")
    db.session.commit()

    from app.matching.service import buscar_matches_para
    assert pub1 not in buscar_matches_para(pub2)


def test_cambio_dia_no_hace_match_con_cambio_normal(client, db):
    """cambio_dia solo casa con otro cambio_dia, no con 'cambio' normal."""
    u1 = _setup(client, "u1@test.es", "Ana")
    client.get("/auth/logout")
    u2 = _setup(client, "u2@test.es", "Bea")

    fs = _franjas(u2)
    fecha = date.today() + timedelta(days=5)

    pub_cambio = publicar_cambio(u1.id, [(fecha, fs[1].id)], [(fecha, fs[0].id)], tipo="cambio")
    db.session.commit()
    pub_dia = publicar_cambio(u2.id, [(fecha, fs[0].id)], [(fecha, fs[1].id)], tipo="cambio_dia")
    db.session.commit()

    from app.matching.service import buscar_matches_para
    assert pub_cambio not in buscar_matches_para(pub_dia)
    assert pub_dia not in buscar_matches_para(pub_cambio)


# ---------------------------------------------------------------------------
# Caducidad
# ---------------------------------------------------------------------------

def test_cambio_dia_caduca_cuando_fecha_pasa(db):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    u = registrar_usuario("Test", "t@t.es", "pass1234", "H", "U", cat.id)
    fs = _franjas(u)

    fecha_pasada = date(2026, 8, 1)
    pub = publicar_cambio(u.id, [(fecha_pasada, fs[0].id)], [(fecha_pasada, fs[1].id)], tipo="cambio_dia")
    db.session.commit()

    caducar_publicaciones_expiradas(hoy=date(2026, 9, 1))
    db.session.refresh(pub)
    assert pub.estado == "caducada"
