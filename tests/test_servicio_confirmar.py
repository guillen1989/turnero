"""Tests unitarios del servicio confirmar_participacion (sin pasar por HTTP)."""
from datetime import date

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
from app.services.matches import confirmar_participacion
from app.services.registro import registrar_usuario


def _setup_match(db):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario("Ana", "ana@test.es", "password123", "H1", "Urgencias", cat.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "H1", "Urgencias", cat.id)

    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=ana.unidad.grupo_intercambio_id, nombre="Mañana"
    ).first()

    pub_ana = PublicacionCambio(usuario_id=ana.id)
    db.session.add(pub_ana)
    db.session.flush()
    tc_ana = TurnoCedido(publicacion_id=pub_ana.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id)
    db.session.add(tc_ana)

    pub_pedro = PublicacionCambio(usuario_id=pedro.id)
    db.session.add(pub_pedro)
    db.session.flush()
    tc_pedro = TurnoCedido(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id)
    db.session.add(tc_pedro)

    match = MatchCambio(tipo="directo_2", estado="propuesto")
    db.session.add(match)
    db.session.flush()
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_ana.id, turno_cedido_id=tc_ana.id))
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_pedro.id, turno_cedido_id=tc_pedro.id))
    db.session.commit()

    return ana, pedro, match


def test_confirmar_participacion_sin_firma_deja_firma_data_none(db):
    ana, pedro, match = _setup_match(db)
    confirmar_participacion(match, ana.id)
    part_ana = next(p for p in match.participaciones if p.publicacion_id == match.participaciones[0].publicacion_id)
    assert part_ana.firma_data is None


def test_confirmar_participacion_guarda_firma_data_de_quien_confirma(db):
    ana, pedro, match = _setup_match(db)
    firma = "data:image/png;base64,iVBORw0KGgo="
    confirmar_participacion(match, ana.id, firma_data=firma)

    part_ana = next(p for p in match.participaciones if p.publicacion.usuario_id == ana.id)
    part_pedro = next(p for p in match.participaciones if p.publicacion.usuario_id == pedro.id)
    assert part_ana.firma_data == firma
    assert part_pedro.firma_data is None


def test_confirmar_participacion_no_toca_la_firma_de_otras_partes(db):
    ana, pedro, match = _setup_match(db)
    confirmar_participacion(match, ana.id, firma_data="data:image/png;base64,AAA=")
    confirmar_participacion(match, pedro.id, firma_data="data:image/png;base64,BBB=")

    part_ana = next(p for p in match.participaciones if p.publicacion.usuario_id == ana.id)
    part_pedro = next(p for p in match.participaciones if p.publicacion.usuario_id == pedro.id)
    assert part_ana.firma_data == "data:image/png;base64,AAA="
    assert part_pedro.firma_data == "data:image/png;base64,BBB="
