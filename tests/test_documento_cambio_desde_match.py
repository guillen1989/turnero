"""Tests del enganche entre el motor de matching (MatchCambio) y la hoja de
cambio digital (DocumentoCambio): en vez de que el usuario rellene a mano
los datos del cambio en 'Nueva hoja de cambio', un match directo_2 ya
detectado por la app (por publicación automática o por 'Me interesa') debe
poder generar su propio DocumentoCambio reutilizando los datos que ya tiene."""
from datetime import date

from app.extensions import db
from app.models import (
    Categoria,
    DocumentoCambio,
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


def _usuarios(db, sufijo="a"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario(f"Ana{sufijo}", f"ana{sufijo}@test.es", "password123", "Hospital La Paz", "Urgencias", cat.id)
    pedro = registrar_usuario(f"Pedro{sufijo}", f"pedro{sufijo}@test.es", "password123", "Hospital La Paz", "Urgencias", cat.id)
    return ana, pedro


def _franja(grupo_id, nombre="Mañana"):
    return FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id, nombre=nombre).first()


def _match_cambio_simetrico(db, sufijo="a"):
    """Match directo_2 tipo 'cambio': ambos ceden y reciben un turno con franja concreta."""
    ana, pedro = _usuarios(db, sufijo)
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_ana = PublicacionCambio(usuario_id=ana.id)
    db.session.add(pub_ana)
    db.session.flush()
    tc_ana = TurnoCedido(publicacion_id=pub_ana.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id)
    ta_ana = TurnoAceptado(publicacion_id=pub_ana.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id)
    db.session.add_all([tc_ana, ta_ana])

    pub_pedro = PublicacionCambio(usuario_id=pedro.id)
    db.session.add(pub_pedro)
    db.session.flush()
    tc_pedro = TurnoCedido(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id)
    ta_pedro = TurnoAceptado(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id)
    db.session.add_all([tc_pedro, ta_pedro])

    match = MatchCambio(tipo="directo_2", estado="propuesto")
    db.session.add(match)
    db.session.flush()
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_ana.id, turno_cedido_id=tc_ana.id, turno_aceptado_id=ta_ana.id))
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_pedro.id, turno_cedido_id=tc_pedro.id, turno_aceptado_id=ta_pedro.id))
    db.session.commit()

    return match, ana, pedro


def _match_regalo_peticion(db, sufijo="b"):
    """Match directo_2 asimétrico: uno solo cede, el otro solo recibe (regalo)."""
    ana, pedro = _usuarios(db, sufijo)
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_ana = PublicacionCambio(usuario_id=ana.id, tipo="peticion")
    db.session.add(pub_ana)
    db.session.flush()
    tc_ana = TurnoCedido(publicacion_id=pub_ana.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id)
    db.session.add(tc_ana)

    pub_pedro = PublicacionCambio(usuario_id=pedro.id, tipo="regalo")
    db.session.add(pub_pedro)
    db.session.flush()
    ta_pedro = TurnoAceptado(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id)
    db.session.add(ta_pedro)

    match = MatchCambio(tipo="directo_2", estado="propuesto")
    db.session.add(match)
    db.session.flush()
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_ana.id, turno_cedido_id=tc_ana.id))
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_pedro.id, turno_aceptado_id=ta_pedro.id))
    db.session.commit()

    return match, ana, pedro


def _match_cadena_3(db, sufijo="c"):
    ana, pedro = _usuarios(db, sufijo)
    cat = ana.categoria
    luis = registrar_usuario(f"Luis{sufijo}", f"luis{sufijo}@test.es", "password123", "Hospital La Paz", "Urgencias", cat.id)
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pubs = []
    for u, fecha in [(ana, date(2026, 9, 1)), (pedro, date(2026, 9, 2)), (luis, date(2026, 9, 3))]:
        pub = PublicacionCambio(usuario_id=u.id)
        db.session.add(pub)
        db.session.flush()
        tc = TurnoCedido(publicacion_id=pub.id, fecha=fecha, franja_horaria_id=franja.id)
        db.session.add(tc)
        db.session.flush()
        pubs.append((pub, tc))

    match = MatchCambio(tipo="cadena_3", estado="propuesto")
    db.session.add(match)
    db.session.flush()
    for pub, tc in pubs:
        db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub.id, turno_cedido_id=tc.id))
    db.session.commit()
    return match


def test_match_admite_documento_cambio_con_swap_simetrico(db):
    match, ana, pedro = _match_cambio_simetrico(db)
    assert match_admite_documento_cambio(match) is True


def test_match_no_admite_documento_cambio_si_es_asimetrico(db):
    match, ana, pedro = _match_regalo_peticion(db)
    assert match_admite_documento_cambio(match) is False


def test_match_no_admite_documento_cambio_si_es_cadena(db):
    match = _match_cadena_3(db)
    assert match_admite_documento_cambio(match) is False


def test_match_no_admite_documento_cambio_si_turno_aceptado_es_cualquier_franja(db):
    ana, pedro = _usuarios(db, "d")
    franja = _franja(ana.unidad.grupo_intercambio_id)

    pub_ana = PublicacionCambio(usuario_id=ana.id)
    db.session.add(pub_ana)
    db.session.flush()
    tc_ana = TurnoCedido(publicacion_id=pub_ana.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id)
    ta_ana = TurnoAceptado(publicacion_id=pub_ana.id, fecha=date(2026, 9, 2), cualquier_franja=True)
    db.session.add_all([tc_ana, ta_ana])

    pub_pedro = PublicacionCambio(usuario_id=pedro.id)
    db.session.add(pub_pedro)
    db.session.flush()
    tc_pedro = TurnoCedido(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id)
    ta_pedro = TurnoAceptado(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id)
    db.session.add_all([tc_pedro, ta_pedro])

    match = MatchCambio(tipo="directo_2", estado="propuesto")
    db.session.add(match)
    db.session.flush()
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_ana.id, turno_cedido_id=tc_ana.id, turno_aceptado_id=ta_ana.id))
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_pedro.id, turno_cedido_id=tc_pedro.id, turno_aceptado_id=ta_pedro.id))
    db.session.commit()

    assert match_admite_documento_cambio(match) is False


def test_crear_documento_cambio_desde_match_enlaza_el_match(db):
    match, ana, pedro = _match_cambio_simetrico(db)
    documento = crear_documento_cambio_desde_match(match)
    assert documento.match_id == match.id


def test_crear_documento_cambio_desde_match_genera_participantes_espejo(db):
    match, ana, pedro = _match_cambio_simetrico(db)
    documento = crear_documento_cambio_desde_match(match)

    p_ana = next(p for p in documento.participantes if p.usuario_id == ana.id)
    p_pedro = next(p for p in documento.participantes if p.usuario_id == pedro.id)

    assert p_ana.turno_cede_fecha == date(2026, 9, 1)
    assert p_ana.turno_cede_franja_id == _franja(ana.unidad.grupo_intercambio_id).id
    assert p_ana.turno_recibe_fecha == date(2026, 9, 2)

    assert p_pedro.turno_cede_fecha == date(2026, 9, 2)
    assert p_pedro.turno_recibe_fecha == date(2026, 9, 1)


def test_crear_documento_cambio_desde_match_queda_en_borrador(db):
    match, ana, pedro = _match_cambio_simetrico(db)
    documento = crear_documento_cambio_desde_match(match)
    assert documento.estado == "borrador"


def test_crear_documento_cambio_desde_match_no_duplica_notificacion_de_pendiente_de_firma(db):
    """La notificación de 'pendiente de confirmar el match' ya la manda
    confirmar_participacion; crear el documento desde el match no debe
    generar una segunda notificación de 'pendiente de firma'."""
    from app.models import Notificacion

    match, ana, pedro = _match_cambio_simetrico(db)
    crear_documento_cambio_desde_match(match)

    assert Notificacion.query.filter_by(
        usuario_id=pedro.id, tipo="documento_cambio_pendiente_firma"
    ).count() == 0
