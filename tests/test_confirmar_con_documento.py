"""Tests de integración: confirmar un match directo simétrico genera y
firma su DocumentoCambio automáticamente, sin pasos manuales extra."""
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
from app.services.registro import registrar_usuario

FIRMA_ANA = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4"
    "2mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
FIRMA_PEDRO = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAADklE"
    "QVR4nGNgGAWDEwAAAZoAAR2CVqgAAAAASUVORK5CYII="
)


def _setup_match_simetrico(db, tipo="directo_2"):
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
    ta_ana = TurnoAceptado(publicacion_id=pub_ana.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id)
    db.session.add_all([tc_ana, ta_ana])

    pub_pedro = PublicacionCambio(usuario_id=pedro.id)
    db.session.add(pub_pedro)
    db.session.flush()
    tc_pedro = TurnoCedido(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id)
    ta_pedro = TurnoAceptado(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id)
    db.session.add_all([tc_pedro, ta_pedro])

    match = MatchCambio(tipo=tipo, estado="propuesto")
    db.session.add(match)
    db.session.flush()
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_ana.id, turno_cedido_id=tc_ana.id, turno_aceptado_id=ta_ana.id))
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_pedro.id, turno_cedido_id=tc_pedro.id, turno_aceptado_id=ta_pedro.id))
    db.session.commit()

    return ana, pedro, match


def _setup_match_regalo(db):
    """Match asimétrico (regalo/petición): no admite DocumentoCambio."""
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario("Ana", "ana@test.es", "password123", "H1", "Urgencias", cat.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "H1", "Urgencias", cat.id)
    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=ana.unidad.grupo_intercambio_id, nombre="Mañana"
    ).first()

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

    return ana, pedro, match


def test_confirmar_simetrico_sin_firma_no_confirma(client, db):
    ana, pedro, match = _setup_match_simetrico(db)
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    client.post(f"/matches/{match.id}/confirmar")
    db.session.refresh(match)
    assert match.estado == "propuesto"


def test_confirmar_simetrico_sin_firma_da_flash_error(client, db):
    ana, pedro, match = _setup_match_simetrico(db)
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    resp = client.post(f"/matches/{match.id}/confirmar", follow_redirects=True)
    assert "Debes firmar" in resp.get_data(as_text=True)


def test_confirmar_simetrico_con_firma_crea_documento_cambio(client, db):
    ana, pedro, match = _setup_match_simetrico(db)
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    client.post(f"/matches/{match.id}/confirmar", data={"firma": FIRMA_ANA})

    documento = DocumentoCambio.query.filter_by(match_id=match.id).first()
    assert documento is not None
    # Se crea y se firma en la misma acción de confirmar: ya no queda en
    # 'borrador' (que implicaría 0 firmas), pasa directo a 'pendiente_firmas'.
    assert documento.estado == "pendiente_firmas"


def test_confirmar_simetrico_con_firma_registra_la_firma_de_quien_confirma(client, db):
    ana, pedro, match = _setup_match_simetrico(db)
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    client.post(f"/matches/{match.id}/confirmar", data={"firma": FIRMA_ANA})

    documento = DocumentoCambio.query.filter_by(match_id=match.id).first()
    ids_firmantes = {f.usuario_id for f in documento.firmas}
    assert ids_firmantes == {ana.id}


def test_confirmar_simetrico_sigue_marcando_confirmado_parcial(client, db):
    ana, pedro, match = _setup_match_simetrico(db)
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    client.post(f"/matches/{match.id}/confirmar", data={"firma": FIRMA_ANA})
    db.session.refresh(match)
    assert match.estado == "confirmado_parcial"


def test_confirmar_ambas_partes_completa_el_documento(client, db):
    ana, pedro, match = _setup_match_simetrico(db)
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    client.post(f"/matches/{match.id}/confirmar", data={"firma": FIRMA_ANA})
    client.get("/auth/logout")
    client.post("/auth/login", data={"email": "pedro@test.es", "password": "password123"})
    client.post(f"/matches/{match.id}/confirmar", data={"firma": FIRMA_PEDRO})

    documento = DocumentoCambio.query.filter_by(match_id=match.id).first()
    ids_firmantes = {f.usuario_id for f in documento.firmas}
    assert ids_firmantes == {ana.id, pedro.id}
    assert documento.estado == "completo"

    db.session.refresh(match)
    assert match.estado == "confirmado_total"


def test_confirmar_ambas_partes_reutiliza_el_mismo_documento(client, db):
    ana, pedro, match = _setup_match_simetrico(db)
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    client.post(f"/matches/{match.id}/confirmar", data={"firma": FIRMA_ANA})
    client.get("/auth/logout")
    client.post("/auth/login", data={"email": "pedro@test.es", "password": "password123"})
    client.post(f"/matches/{match.id}/confirmar", data={"firma": FIRMA_PEDRO})

    assert DocumentoCambio.query.filter_by(match_id=match.id).count() == 1


def test_confirmar_asimetrico_no_exige_firma(client, db):
    ana, pedro, match = _setup_match_regalo(db)
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    resp = client.post(f"/matches/{match.id}/confirmar", follow_redirects=False)
    assert resp.status_code == 302
    db.session.refresh(match)
    assert match.estado == "confirmado_parcial"


def test_confirmar_asimetrico_no_crea_documento_cambio(client, db):
    ana, pedro, match = _setup_match_regalo(db)
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    client.post(f"/matches/{match.id}/confirmar")
    assert DocumentoCambio.query.filter_by(match_id=match.id).first() is None


def test_confirmar_cadena_no_exige_firma(client, db):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario("Ana", "ana@test.es", "password123", "H1", "Urgencias", cat.id)
    pedro = registrar_usuario("Pedro", "pedro@test.es", "password123", "H1", "Urgencias", cat.id)
    luis = registrar_usuario("Luis", "luis@test.es", "password123", "H1", "Urgencias", cat.id)
    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=ana.unidad.grupo_intercambio_id, nombre="Mañana"
    ).first()

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

    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    resp = client.post(f"/matches/{match.id}/confirmar", follow_redirects=False)
    assert resp.status_code == 302
    db.session.refresh(match)
    assert match.estado == "confirmado_parcial"
    assert DocumentoCambio.query.filter_by(match_id=match.id).first() is None


def test_reconfirmar_tras_desconfirmar_no_duplica_la_firma(client, db):
    ana, pedro, match = _setup_match_simetrico(db)
    client.post("/auth/login", data={"email": "ana@test.es", "password": "password123"})
    client.post(f"/matches/{match.id}/confirmar", data={"firma": FIRMA_ANA})
    client.post(f"/matches/{match.id}/desconfirmar")

    resp = client.post(f"/matches/{match.id}/confirmar", data={"firma": FIRMA_ANA}, follow_redirects=False)
    assert resp.status_code == 302

    documento = DocumentoCambio.query.filter_by(match_id=match.id).first()
    assert len([f for f in documento.firmas if f.usuario_id == ana.id]) == 1
