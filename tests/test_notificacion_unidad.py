"""Tests para Paso 6: Notificaciones con unidad de origen."""
from datetime import date
from unittest.mock import patch

from app.extensions import db
from app.models import (
    Categoria,
    FranjaHoraria,
    Hospital,
    GrupoIntercambio,
    Notificacion,
    Unidad,
    Usuario,
    UsuarioUnidad,
    insertar_categorias_semilla,
)
from app.services.publicaciones import publicar_cambio
from app.services.registro import registrar_usuario
from app.services.unidad_usuario import (
    unidades_de,
    sincronizar_unidades,
)
from app.routes.notificaciones import _colegas_del_usuario


def _garantizar_semilla():
    """Llama a insertar_categorias_semilla de forma idempotente."""
    try:
        Categoria.query.filter_by(nombre="Enfermería").first().id
    except (AttributeError, Exception):
        insertar_categorias_semilla()


def _crear_usuario_multiumidad(db):
    """Crea un usuario con unidad principal UCI y secundaria Urgencias."""
    _garantizar_semilla()
    cat_enfermeria = Categoria.query.filter_by(nombre="Enfermería").first()
    cat_aux = Categoria.query.filter_by(nombre="Auxiliar de enfermería (TCAE)").first()

    usuario = registrar_usuario(
        "Ana Multi", "ana.multi@test.es", "password123",
        "H1", "UCI", cat_enfermeria.id,
    )
    hospital = Hospital.query.filter_by(nombre="H1").first()
    grupo = usuario.unidad.grupo_intercambio
    unidad_urgencias = Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo)
    db.session.add(unidad_urgencias)
    db.session.commit()

    sincronizar_unidades(usuario, {
        usuario.unidad_id: cat_enfermeria.id,
        unidad_urgencias.id: cat_aux.id,
    })
    db.session.commit()
    return usuario, cat_enfermeria, cat_aux


# --- Model tests ---

def test_notificacion_guarda_unidad_id(db):
    _garantizar_semilla()
    usuario = registrar_usuario("Test", "test@test.es", "pass", "H1", "UCI",
                                Categoria.query.filter_by(nombre="Enfermería").first().id)
    unidad = usuario.unidad

    notif = Notificacion(
        usuario_id=usuario.id,
        unidad_id=unidad.id,
        tipo="nueva_publicacion_seguido",
    )
    db.session.add(notif)
    db.session.commit()

    recuperada = Notificacion.query.filter_by(usuario_id=usuario.id).first()
    assert recuperada is not None
    assert recuperada.unidad_id == unidad.id
    assert recuperada.unidad.nombre == "UCI"


# --- Publicacion notificacion con unidad_id ---

def test_notificacion_suscriptor_lleva_unidad_de_la_publicacion(app, db):
    _garantizar_semilla()
    u1 = registrar_usuario("Pub", "pub@test.es", "pass", "H1", "UCI",
                           Categoria.query.filter_by(nombre="Enfermería").first().id)
    u2 = registrar_usuario("Sub", "sub@test.es", "pass", "H1", "UCI",
                           Categoria.query.filter_by(nombre="Enfermería").first().id)
    from app.models import SuscripcionPublicaciones
    db.session.add(SuscripcionPublicaciones(suscriptor_id=u2.id, publicador_id=u1.id))
    db.session.commit()

    franja = u1.unidad.grupo_intercambio.franjas_horarias.first().id
    with patch("app.push.sender.webpush"):
        publicar_cambio(u1.id, [(date(2025, 6, 1), franja)], [(date(2025, 6, 2), franja)])

    notif = Notificacion.query.filter_by(usuario_id=u2.id, tipo="nueva_publicacion_seguido").first()
    assert notif is not None
    assert notif.unidad_id == u1.unidad_id


# --- Match notificacion con unidad_id ---

def test_notificacion_match_lleva_unidad_de_la_publicacion(app, db):
    _garantizar_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario("Ana", "ana.m@test.es", "pass", "H1", "UCI", cat.id)
    pedro = registrar_usuario("Pedro", "pedro.m@test.es", "pass", "H1", "UCI", cat.id)

    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=ana.unidad.grupo_intercambio_id, nombre="Mañana"
    ).first()
    from app.models import PublicacionCambio, TurnoCedido, TurnoAceptado
    from app.matching.service import crear_match_directo

    pub_ana = PublicacionCambio(usuario_id=ana.id)
    db.session.add(pub_ana)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub_ana.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub_ana.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id))

    pub_pedro = PublicacionCambio(usuario_id=pedro.id)
    db.session.add(pub_pedro)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id))
    db.session.commit()

    with patch("app.push.sender.webpush"):
        crear_match_directo(pub_ana, pub_pedro)

    notif_ana = Notificacion.query.filter_by(usuario_id=ana.id, tipo="nuevo_match").first()
    assert notif_ana is not None
    assert notif_ana.unidad_id == ana.unidad_id


# --- Documento cambio notificacion con unidad_id ---

def test_notificacion_documento_cambio_lleva_unidad_del_documento(app, db):
    _garantizar_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    creador = registrar_usuario("Creador", "creador@test.es", "pass", "H1", "UCI", cat.id)
    companero = registrar_usuario("Comp", "comp@test.es", "pass", "H1", "UCI", cat.id)

    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=creador.unidad.grupo_intercambio_id, nombre="Mañana"
    ).first()
    from app.services.documento_cambio import crear_documento_cambio

    with patch("app.push.sender.webpush"):
        doc = crear_documento_cambio(
            creado_por=creador,
            companero=companero,
            turno_cede_fecha=date(2026, 9, 1),
            turno_cede_franja_id=franja.id,
            turno_recibe_fecha=date(2026, 9, 2),
            turno_recibe_franja_id=franja.id,
        )

    notif = Notificacion.query.filter_by(
        usuario_id=companero.id,
        tipo="documento_cambio_pendiente_firma",
    ).first()
    assert notif is not None
    assert notif.unidad_id == doc.unidad_id


# --- Bandeja única (no filtra por unidad activa) ---

def test_avisos_muestra_todas_las_unidades_juntas(client, db):
    u1, _, _ = _crear_usuario_multiumidad(db)
    unidad_uci = u1.unidad
    unidad_urg = [u for u in unidades_de(u1) if u.id != unidad_uci.id][0]

    db.session.add(Notificacion(
        usuario_id=u1.id, unidad_id=unidad_uci.id,
        tipo="contrasena_restablecida",
        mensaje="Aviso en UCI",
    ))
    db.session.add(Notificacion(
        usuario_id=u1.id, unidad_id=unidad_urg.id,
        tipo="contrasena_restablecida",
        mensaje="Aviso en Urgencias",
    ))
    db.session.commit()

    client.post("/auth/login", data={"email": "ana.multi@test.es", "password": "password123"})
    resp = client.get("/avisos")
    html = resp.data.decode()
    assert "Aviso en UCI" in html
    assert "Aviso en Urgencias" in html


# --- Template: nombre de unidad en cada aviso (solo si >1 unidad) ---

def test_avisos_muestra_unidad_solo_si_usuario_tiene_mas_de_una(client, db):
    u1, _, _ = _crear_usuario_multiumidad(db)
    unidad_uci = u1.unidad
    unidad_urg = [u for u in unidades_de(u1) if u.id != unidad_uci.id][0]

    db.session.add(Notificacion(
        usuario_id=u1.id, unidad_id=unidad_uci.id,
        tipo="contrasena_restablecida",
        mensaje="Password reset UCI",
    ))
    db.session.add(Notificacion(
        usuario_id=u1.id, unidad_id=unidad_urg.id,
        tipo="contrasena_restablecida",
        mensaje="Password reset Urgencias",
    ))
    db.session.commit()

    client.post("/auth/login", data={"email": "ana.multi@test.es", "password": "password123"})
    resp = client.get("/avisos")
    html = resp.data.decode()
    assert "UCI" in html
    assert "Urgencias" in html


def test_avisos_no_muestra_unidad_si_usuario_tiene_una_sola(client, db):
    _garantizar_semilla()
    u = registrar_usuario("Solo", "solo@test.es", "pass", "H1", "UCI",
                          Categoria.query.filter_by(nombre="Enfermería").first().id)
    db.session.add(Notificacion(
        usuario_id=u.id, unidad_id=u.unidad_id,
        tipo="contrasena_restablecida",
        mensaje="Password reset",
    ))
    db.session.commit()

    client.post("/auth/login", data={"email": "solo@test.es", "password": "pass"})
    resp = client.get("/avisos")
    html = resp.data.decode()

    assert len(unidades_de(u)) == 1
    assert "aviso-unidad" not in html


# --- _colegas_del_usuario multi-unidad ---

def test_colegas_multiunidad_incluye_de_todas_las_unidades(db):
    _garantizar_semilla()
    hospital = Hospital.query.first()
    if not hospital:
        hospital = Hospital(nombre="H1")
        db.session.add(hospital)
        db.session.commit()

    grupo = GrupoIntercambio.query.first()
    if not grupo:
        grupo = GrupoIntercambio()
        db.session.add(grupo)
        db.session.commit()

    unidad_uci = Unidad.query.filter_by(nombre="UCI").first()
    if not unidad_uci:
        unidad_uci = Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo)
        db.session.add(unidad_uci)

    unidad_urgencias = Unidad.query.filter_by(nombre="Urgencias").first()
    if not unidad_urgencias:
        unidad_urgencias = Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo)
        db.session.add(unidad_urgencias)
    db.session.commit()

    cat_enfermeria = Categoria.query.filter_by(nombre="Enfermería").first()

    ana = Usuario(nombre="Ana", email="ana.c@test.es", unidad=unidad_uci, categoria=cat_enfermeria)
    ana.set_password("pass")
    db.session.add(ana)
    db.session.flush()
    ana_id = ana.id
    db.session.add(UsuarioUnidad(usuario_id=ana_id, unidad_id=unidad_uci.id, categoria_id=cat_enfermeria.id))
    db.session.add(UsuarioUnidad(usuario_id=ana_id, unidad_id=unidad_urgencias.id, categoria_id=cat_enfermeria.id))
    db.session.commit()

    colega_uci = Usuario(nombre="Colega UCI", email="c.uci@test.es", unidad=unidad_uci, categoria=cat_enfermeria)
    colega_uci.set_password("pass")
    db.session.add(colega_uci)

    colega_urg = Usuario(nombre="Colega Urg", email="c.urg@test.es", unidad=unidad_urgencias, categoria=cat_enfermeria)
    colega_urg.set_password("pass")
    db.session.add(colega_urg)
    db.session.commit()

    colegas = _colegas_del_usuario(ana)
    nombres = {c.nombre for c in colegas}
    assert "Colega UCI" in nombres
    assert "Colega Urg" in nombres
    assert "Ana" not in nombres
