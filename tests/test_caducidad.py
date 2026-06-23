"""Tests del servicio de caducidad automática de publicaciones (Fase 6, paso 1).

Usa el parámetro `hoy` del servicio para controlar la fecha de referencia
sin depender del reloj real, lo que hace los tests deterministas.
"""
from datetime import date, time

from app.extensions import db
from app.models import (
    Categoria,
    FranjaHoraria,
    PublicacionCambio,
    TurnoCedido,
    TurnoAceptado,
    insertar_categorias_semilla,
)
from app.services.registro import registrar_usuario
from app.services.caducidad import caducar_publicaciones_expiradas

HOY = date(2026, 9, 15)
PASADO = date(2026, 9, 1)   # antes de HOY
FUTURO = date(2026, 9, 30)  # después de HOY


# --- Helpers ---

def _usuario(email="test@test.es"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario("Test", email, "password123", "H1", "Urgencias", cat.id)


def _franja(grupo_id):
    return FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id, nombre="Mañana").first()


def _pub(usuario, fecha_cede, franja):
    pub = PublicacionCambio(usuario_id=usuario.id)
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=fecha_cede, franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=FUTURO, franja_horaria_id=franja.id))
    db.session.commit()
    return pub


# --- Tests ---

def test_caduca_publicacion_con_turno_pasado(db):
    u = _usuario()
    franja = _franja(u.unidad.grupo_intercambio_id)
    pub = _pub(u, PASADO, franja)

    caducar_publicaciones_expiradas(hoy=HOY)

    db.session.refresh(pub)
    assert pub.estado == "caducada"


def test_no_caduca_publicacion_con_turno_futuro(db):
    u = _usuario()
    franja = _franja(u.unidad.grupo_intercambio_id)
    pub = _pub(u, FUTURO, franja)

    caducar_publicaciones_expiradas(hoy=HOY)

    db.session.refresh(pub)
    assert pub.estado == "abierta"


def test_no_caduca_publicacion_con_turno_en_el_dia_hoy(db):
    """El día exacto todavía no ha pasado: no caduca."""
    u = _usuario()
    franja = _franja(u.unidad.grupo_intercambio_id)
    pub = _pub(u, HOY, franja)

    caducar_publicaciones_expiradas(hoy=HOY)

    db.session.refresh(pub)
    assert pub.estado == "abierta"


def test_no_caduca_publicacion_ya_cancelada(db):
    u = _usuario()
    franja = _franja(u.unidad.grupo_intercambio_id)
    pub = _pub(u, PASADO, franja)
    pub.estado = "cancelada"
    db.session.commit()

    caducar_publicaciones_expiradas(hoy=HOY)

    db.session.refresh(pub)
    assert pub.estado == "cancelada"


def test_caduca_cuando_todos_los_turnos_cedidos_son_pasados(db):
    """Con varios turnos cedidos, caduca solo si TODOS son pasados."""
    u = _usuario()
    franja = _franja(u.unidad.grupo_intercambio_id)
    pub = PublicacionCambio(usuario_id=u.id)
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=PASADO, franja_horaria_id=franja.id))
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=date(2026, 9, 5), franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=FUTURO, franja_horaria_id=franja.id))
    db.session.commit()

    caducar_publicaciones_expiradas(hoy=HOY)

    db.session.refresh(pub)
    assert pub.estado == "caducada"


def test_no_caduca_si_algun_turno_cedido_es_futuro(db):
    """Si al menos un turno cedido sigue vigente, la publicación no caduca."""
    u = _usuario()
    franja = _franja(u.unidad.grupo_intercambio_id)
    pub = PublicacionCambio(usuario_id=u.id)
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=PASADO, franja_horaria_id=franja.id))
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=FUTURO, franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=FUTURO, franja_horaria_id=franja.id))
    db.session.commit()

    caducar_publicaciones_expiradas(hoy=HOY)

    db.session.refresh(pub)
    assert pub.estado == "abierta"


def test_devuelve_conteo_de_publicaciones_caducadas(db):
    u = _usuario()
    franja = _franja(u.unidad.grupo_intercambio_id)
    pub_pasada = _pub(u, PASADO, franja)
    pub_futura = _pub(u, FUTURO, franja)

    total = caducar_publicaciones_expiradas(hoy=HOY)

    assert total == 1
    db.session.refresh(pub_pasada)
    db.session.refresh(pub_futura)
    assert pub_pasada.estado == "caducada"
    assert pub_futura.estado == "abierta"


def test_no_caduca_turno_resuelto_aunque_sea_pasado(db):
    """Un turno ya resuelto no hace caducar la publicación."""
    u = _usuario()
    franja = _franja(u.unidad.grupo_intercambio_id)
    pub = PublicacionCambio(usuario_id=u.id)
    db.session.add(pub)
    db.session.flush()
    tc_pasado = TurnoCedido(publicacion_id=pub.id, fecha=PASADO, franja_horaria_id=franja.id,
                            estado="resuelto")
    tc_futuro = TurnoCedido(publicacion_id=pub.id, fecha=FUTURO, franja_horaria_id=franja.id)
    db.session.add(tc_pasado)
    db.session.add(tc_futuro)
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=FUTURO, franja_horaria_id=franja.id))
    db.session.commit()

    caducar_publicaciones_expiradas(hoy=HOY)

    db.session.refresh(pub)
    assert pub.estado == "abierta"
