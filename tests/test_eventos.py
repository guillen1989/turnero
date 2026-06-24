"""Tests del sistema de eventos de funnel."""
from datetime import date

from app.extensions import db
from app.models import Categoria, Event, FranjaHoraria, MatchCambio, insertar_categorias_semilla
from app.services.eventos import registrar_evento
from app.services.publicaciones import publicar_cambio, cancelar_publicacion
from app.services.registro import registrar_usuario
from app.matching.service import crear_match_directo, buscar_matches_para
from app.services.matches import confirmar_participacion, rechazar_match


def _usuario(nombre, email, hospital="H1", unidad="U1"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario(nombre, email, "pass123", hospital, unidad, cat.id)


def _franja(grupo_id):
    return FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id, nombre="Mañana").first()


def _pub(usuario, fecha_cede, fecha_acepta):
    franja = _franja(usuario.unidad.grupo_intercambio_id)
    return publicar_cambio(
        usuario.id,
        turnos_cedidos=[(fecha_cede, franja.id)],
        turnos_aceptados=[(fecha_acepta, franja.id)],
    )


def test_registrar_evento_guarda_en_bd(db):
    ana = _usuario("Ana", "ana@test.es")
    registrar_evento(ana.id, "test_event", entity_id=99)
    db.session.commit()

    ev = Event.query.filter_by(event_type="test_event").first()
    assert ev is not None
    assert ev.user_id == ana.id
    assert ev.entity_id == 99


def test_registrar_evento_es_silencioso_ante_errores(db):
    # user_id inexistente; no debe propagar excepción
    registrar_evento(99999, "test_event")


def test_publicar_cambio_registra_publication_created(db):
    ana = _usuario("Ana", "ana@test.es")
    pub = _pub(ana, date(2026, 7, 1), date(2026, 7, 2))

    eventos = Event.query.filter_by(user_id=ana.id, event_type="publication_created").all()
    assert len(eventos) == 1
    assert eventos[0].entity_id == pub.id


def test_crear_match_registra_match_found_para_ambas_partes(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")

    pub_ana = _pub(ana, date(2026, 7, 1), date(2026, 7, 2))
    pub_pedro = _pub(pedro, date(2026, 7, 2), date(2026, 7, 1))

    match = crear_match_directo(pub_ana, pub_pedro)
    assert match is not None

    for usuario in (ana, pedro):
        ev = Event.query.filter_by(user_id=usuario.id, event_type="match_found").first()
        assert ev is not None
        assert ev.entity_id == match.id


def test_cancelar_publicacion_registra_publication_cancelled(db):
    ana = _usuario("Ana", "ana@test.es")
    pub = _pub(ana, date(2026, 7, 1), date(2026, 7, 2))

    cancelar_publicacion(pub)

    ev = Event.query.filter_by(user_id=ana.id, event_type="publication_cancelled").first()
    assert ev is not None
    assert ev.entity_id == pub.id


def test_rechazar_match_registra_match_cancelled_para_todos(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")

    pub_ana = _pub(ana, date(2026, 7, 1), date(2026, 7, 2))
    pub_pedro = _pub(pedro, date(2026, 7, 2), date(2026, 7, 1))

    match = crear_match_directo(pub_ana, pub_pedro)
    rechazar_match(match, ana.id)

    assert Event.query.filter_by(event_type="match_cancelled").count() == 2
    for usuario in (ana, pedro):
        ev = Event.query.filter_by(user_id=usuario.id, event_type="match_cancelled").first()
        assert ev is not None
        assert ev.entity_id == match.id


def test_confirmar_match_registra_match_confirmed(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")

    pub_ana = _pub(ana, date(2026, 7, 1), date(2026, 7, 2))
    pub_pedro = _pub(pedro, date(2026, 7, 2), date(2026, 7, 1))

    match = crear_match_directo(pub_ana, pub_pedro)

    confirmar_participacion(match, ana.id)
    assert Event.query.filter_by(event_type="match_confirmed").count() == 0

    confirmar_participacion(match, pedro.id)
    assert Event.query.filter_by(event_type="match_confirmed").count() == 2
    for usuario in (ana, pedro):
        ev = Event.query.filter_by(user_id=usuario.id, event_type="match_confirmed").first()
        assert ev is not None
        assert ev.entity_id == match.id
