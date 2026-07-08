"""
Tests de regresión: cancelar/editar/eliminar una publicación con un match
todavía activo (propuesto o confirmado_parcial) no debe dejar a la contraparte
con un match huérfano ni borrarlo en silencio sin avisarle.

Bug original: `cancelar_publicacion` no tocaba los matches asociados (quedaban
huérfanos, la contraparte los seguía viendo como pendientes de confirmar), y
`editar_publicacion`/`eliminar_publicacion` los borraban de la base de datos
sin notificar ni registrar evento alguno.
"""
from datetime import date

from app.extensions import db
from app.models import (
    Categoria,
    Event,
    FranjaHoraria,
    MatchCambio,
    MatchParticipacion,
    Notificacion,
    PublicacionCambio,
    TurnoAceptado,
    TurnoCedido,
    insertar_categorias_semilla,
)
from app.services.publicaciones import cancelar_publicacion, editar_publicacion, eliminar_publicacion
from app.services.registro import registrar_usuario


def _usuario(nombre, email):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario(nombre, email, "password123", "H1", "Urgencias", cat.id)


def _franja(grupo_id, nombre="Mañana"):
    return FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id, nombre=nombre).first()


def _setup_match(estado_match="propuesto"):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_ana = PublicacionCambio(usuario_id=ana.id)
    db.session.add(pub_ana)
    db.session.flush()
    tc_ana = TurnoCedido(publicacion_id=pub_ana.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id)
    ta_ana = TurnoAceptado(publicacion_id=pub_ana.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id)
    db.session.add(tc_ana)
    db.session.add(ta_ana)

    pub_pedro = PublicacionCambio(usuario_id=pedro.id)
    db.session.add(pub_pedro)
    db.session.flush()
    tc_pedro = TurnoCedido(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id)
    ta_pedro = TurnoAceptado(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id)
    db.session.add(tc_pedro)
    db.session.add(ta_pedro)
    db.session.flush()

    match = MatchCambio(tipo="directo_2", estado=estado_match)
    db.session.add(match)
    db.session.flush()
    mp_ana = MatchParticipacion(match_id=match.id, publicacion_id=pub_ana.id, turno_cedido_id=tc_ana.id, turno_aceptado_id=ta_ana.id)
    mp_pedro = MatchParticipacion(match_id=match.id, publicacion_id=pub_pedro.id, turno_cedido_id=tc_pedro.id, turno_aceptado_id=ta_pedro.id)
    if estado_match == "confirmado_parcial":
        mp_pedro.confirmado = True
    db.session.add(mp_ana)
    db.session.add(mp_pedro)
    db.session.commit()

    return ana, pedro, pub_ana, pub_pedro, match


# --- cancelar_publicacion ---

def test_cancelar_publicacion_rechaza_match_propuesto(db):
    ana, pedro, pub_ana, pub_pedro, match = _setup_match("propuesto")
    cancelar_publicacion(pub_ana)
    db.session.refresh(match)
    assert match.estado == "rechazado"


def test_cancelar_publicacion_notifica_a_la_contraparte(db):
    ana, pedro, pub_ana, pub_pedro, match = _setup_match("propuesto")
    cancelar_publicacion(pub_ana)
    n = Notificacion.query.filter_by(usuario_id=pedro.id, tipo="rechazo", match_id=match.id).first()
    assert n is not None


def test_cancelar_publicacion_rechaza_match_confirmado_parcial(db):
    ana, pedro, pub_ana, pub_pedro, match = _setup_match("confirmado_parcial")
    cancelar_publicacion(pub_ana)
    db.session.refresh(match)
    assert match.estado == "rechazado"


def test_cancelar_publicacion_no_toca_match_ya_confirmado_total(db):
    ana, pedro, pub_ana, pub_pedro, match = _setup_match("confirmado_total")
    cancelar_publicacion(pub_ana)
    db.session.refresh(match)
    assert match.estado == "confirmado_total"


def test_cancelar_publicacion_registra_evento_match_cancelled_para_ambos(db):
    ana, pedro, pub_ana, pub_pedro, match = _setup_match("propuesto")
    cancelar_publicacion(pub_ana)
    eventos = Event.query.filter_by(event_type="match_cancelled", entity_id=match.id).all()
    usuarios_con_evento = {e.user_id for e in eventos}
    assert usuarios_con_evento == {ana.id, pedro.id}


# --- editar_publicacion ---

def test_editar_publicacion_rechaza_y_notifica_match_activo(db):
    ana, pedro, pub_ana, pub_pedro, match = _setup_match("confirmado_parcial")
    editar_publicacion(pub_ana, [(date(2026, 9, 5), _franja(ana.unidad.grupo_intercambio_id).id)], [(date(2026, 9, 6), _franja(ana.unidad.grupo_intercambio_id).id)])

    n = Notificacion.query.filter_by(usuario_id=pedro.id, tipo="rechazo").first()
    assert n is not None

    eventos = Event.query.filter_by(event_type="match_cancelled", entity_id=match.id).all()
    usuarios_con_evento = {e.user_id for e in eventos}
    assert usuarios_con_evento == {ana.id, pedro.id}


def test_editar_publicacion_sigue_reemplazando_los_turnos(db):
    ana, pedro, pub_ana, pub_pedro, match = _setup_match("propuesto")
    nueva_fecha_cedida = date(2026, 9, 10)
    franja = _franja(ana.unidad.grupo_intercambio_id)
    editar_publicacion(pub_ana, [(nueva_fecha_cedida, franja.id)], [(date(2026, 9, 11), franja.id)])

    db.session.refresh(pub_ana)
    fechas_cedidas = {t.fecha for t in pub_ana.turnos_cedidos}
    assert fechas_cedidas == {nueva_fecha_cedida}


# --- eliminar_publicacion ---

def test_eliminar_publicacion_notifica_rechazo_de_match_activo(db):
    ana, pedro, pub_ana, pub_pedro, match = _setup_match("propuesto")
    eliminar_publicacion(pub_ana)

    n = Notificacion.query.filter_by(usuario_id=pedro.id, tipo="rechazo").first()
    assert n is not None

    eventos = Event.query.filter_by(event_type="match_cancelled", entity_id=match.id).all()
    usuarios_con_evento = {e.user_id for e in eventos}
    assert usuarios_con_evento == {ana.id, pedro.id}
