"""Paso 3.3 del plan de cambios en el día: un match directo_2 generado a
partir de dos publicaciones tipo cambio_dia (mismo día, distinta franja)
debe poder generar su DocumentoCambio igual que un cambio normal, ya que
match_admite_documento_cambio no distingue por PublicacionCambio.tipo."""
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
from app.services.documento_cambio import (
    crear_documento_cambio_desde_match,
    match_admite_documento_cambio,
)
from app.services.registro import registrar_usuario


def _match_cambio_dia_simetrico(db):
    """Match directo_2 tipo cambio_dia: Ana y Pedro cambian de franja el mismo día."""
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario("AnaCD", "anacd@test.es", "password123", "Hospital La Paz", "Urgencias", cat.id)
    pedro = registrar_usuario("PedroCD", "pedrocd@test.es", "password123", "Hospital La Paz", "Urgencias", cat.id)
    db.session.refresh(ana)
    db.session.refresh(pedro)
    grupo_id = ana.unidad.grupo_intercambio_id
    manana = FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id, nombre="Mañana").first()
    tarde = FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id, nombre="Tarde").first()
    dia = date(2026, 9, 1)

    pub_ana = PublicacionCambio(usuario_id=ana.id, tipo="cambio_dia")
    db.session.add(pub_ana)
    db.session.flush()
    tc_ana = TurnoCedido(publicacion_id=pub_ana.id, fecha=dia, franja_horaria_id=manana.id)
    ta_ana = TurnoAceptado(publicacion_id=pub_ana.id, fecha=dia, franja_horaria_id=tarde.id)
    db.session.add_all([tc_ana, ta_ana])

    pub_pedro = PublicacionCambio(usuario_id=pedro.id, tipo="cambio_dia")
    db.session.add(pub_pedro)
    db.session.flush()
    tc_pedro = TurnoCedido(publicacion_id=pub_pedro.id, fecha=dia, franja_horaria_id=tarde.id)
    ta_pedro = TurnoAceptado(publicacion_id=pub_pedro.id, fecha=dia, franja_horaria_id=manana.id)
    db.session.add_all([tc_pedro, ta_pedro])

    match = MatchCambio(tipo="directo_2", estado="propuesto")
    db.session.add(match)
    db.session.flush()
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_ana.id, turno_cedido_id=tc_ana.id, turno_aceptado_id=ta_ana.id))
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_pedro.id, turno_cedido_id=tc_pedro.id, turno_aceptado_id=ta_pedro.id))
    db.session.commit()

    return match, ana, pedro, dia, manana, tarde


def test_match_cambio_dia_admite_documento_cambio(db):
    match, *_rest = _match_cambio_dia_simetrico(db)
    assert match_admite_documento_cambio(match) is True


def test_crear_documento_cambio_desde_match_cambio_dia_genera_participantes_espejo(db):
    match, ana, pedro, dia, manana, tarde = _match_cambio_dia_simetrico(db)
    documento = crear_documento_cambio_desde_match(match)

    p_ana = next(p for p in documento.participantes if p.usuario_id == ana.id)
    p_pedro = next(p for p in documento.participantes if p.usuario_id == pedro.id)

    assert p_ana.turno_cede_fecha == dia
    assert p_ana.turno_cede_franja_id == manana.id
    assert p_ana.turno_recibe_fecha == dia
    assert p_ana.turno_recibe_franja_id == tarde.id

    assert p_pedro.turno_cede_fecha == dia
    assert p_pedro.turno_cede_franja_id == tarde.id
    assert p_pedro.turno_recibe_fecha == dia
    assert p_pedro.turno_recibe_franja_id == manana.id
