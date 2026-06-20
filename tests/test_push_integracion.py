"""Tests que verifican que enviar_push se llama desde los servicios correctos (Fase 7, paso 2)."""
import json
from datetime import date, time
from unittest.mock import patch

from app.extensions import db
from app.models import (
    Categoria,
    FranjaHoraria,
    MatchCambio,
    MatchParticipacion,
    PublicacionCambio,
    TurnoCedido,
    TurnoAceptado,
    insertar_categorias_semilla,
)
from app.services.registro import registrar_usuario
from app.services.matches import confirmar_participacion, rechazar_match
from app.matching.service import crear_match_directo


def _setup(db):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario("Ana", "ana@test.es", "password123", "H1", "Urgencias", cat.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "H1", "Urgencias", cat.id)

    franja = FranjaHoraria(
        nombre="Mañana", hora_inicio=time(7, 0), hora_fin=time(15, 0),
        grupo_intercambio_id=ana.unidad.grupo_intercambio_id,
    )
    db.session.add(franja)
    db.session.flush()

    pub_ana = PublicacionCambio(usuario_id=ana.id)
    db.session.add(pub_ana)
    db.session.flush()
    tc_ana = TurnoCedido(publicacion_id=pub_ana.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id)
    db.session.add(tc_ana)
    db.session.add(TurnoAceptado(publicacion_id=pub_ana.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id))

    pub_pedro = PublicacionCambio(usuario_id=pedro.id)
    db.session.add(pub_pedro)
    db.session.flush()
    tc_pedro = TurnoCedido(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id)
    db.session.add(tc_pedro)
    db.session.add(TurnoAceptado(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id))
    db.session.commit()

    return ana, pedro, pub_ana, pub_pedro, tc_ana, tc_pedro


def _match(db, pub_ana, pub_pedro, tc_ana, tc_pedro):
    match = MatchCambio(tipo="directo_2", estado="propuesto")
    db.session.add(match)
    db.session.flush()
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_ana.id, turno_cedido_id=tc_ana.id))
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_pedro.id, turno_cedido_id=tc_pedro.id))
    db.session.commit()
    return match


def test_crear_match_llama_enviar_push_para_ambos_usuarios(db):
    ana, pedro, pub_ana, pub_pedro, _, _ = _setup(db)

    with patch("app.matching.service.enviar_push") as mock_push:
        crear_match_directo(pub_ana, pub_pedro)
        assert mock_push.call_count == 2
        usuarios_notificados = {c.args[0].id for c in mock_push.call_args_list}
        assert ana.id in usuarios_notificados
        assert pedro.id in usuarios_notificados


def test_confirmar_parcial_llama_enviar_push_al_otro(db):
    ana, pedro, pub_ana, pub_pedro, tc_ana, tc_pedro = _setup(db)
    match = _match(db, pub_ana, pub_pedro, tc_ana, tc_pedro)

    with patch("app.services.matches.enviar_push") as mock_push:
        confirmar_participacion(match, ana.id)
        mock_push.assert_called_once()
        assert mock_push.call_args.args[0].id == pedro.id


def test_rechazar_llama_enviar_push_al_otro(db):
    ana, pedro, pub_ana, pub_pedro, tc_ana, tc_pedro = _setup(db)
    match = _match(db, pub_ana, pub_pedro, tc_ana, tc_pedro)

    with patch("app.services.matches.enviar_push") as mock_push:
        rechazar_match(match, ana.id)
        mock_push.assert_called_once()
        assert mock_push.call_args.args[0].id == pedro.id
