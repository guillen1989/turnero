from datetime import date, time
from app.models import (
    Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria, Usuario,
    MatchCambio,
    DocumentoCambio, ParticipanteDocumentoCambio, FirmaDocumentoCambio,
)


def _setup(db, sufijo="a"):
    hospital = Hospital(nombre=f"Hospital {sufijo}")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    categoria = Categoria(nombre=f"Enfermería {sufijo}")
    unidad = Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo)
    manyana = FranjaHoraria(nombre="Mañana", hora_inicio=time(7, 0), hora_fin=time(15, 0), grupo_intercambio=grupo)
    tarde = FranjaHoraria(nombre="Tarde", hora_inicio=time(15, 0), hora_fin=time(22, 0), grupo_intercambio=grupo)
    db.session.add_all([categoria, unidad, manyana, tarde])
    db.session.commit()

    def crear_usuario(email):
        u = Usuario(nombre="Usuario Test", email=email, unidad=unidad, categoria=categoria)
        u.set_password("pass")
        db.session.add(u)
        db.session.commit()
        return u

    return crear_usuario, manyana, tarde


def _crear_documento_con_dos_participantes(db, sufijo):
    crear_usuario, manyana, tarde = _setup(db, sufijo)
    ana = crear_usuario(f"ana{sufijo}@h.es")
    pedro = crear_usuario(f"pedro{sufijo}@h.es")

    documento = DocumentoCambio(creado_por=ana)
    db.session.add(documento)
    db.session.flush()

    documento.participantes.append(ParticipanteDocumentoCambio(
        usuario=ana,
        turno_cede_fecha=date(2026, 7, 25), turno_cede_franja=manyana,
        turno_recibe_fecha=date(2026, 7, 26), turno_recibe_franja=tarde,
    ))
    documento.participantes.append(ParticipanteDocumentoCambio(
        usuario=pedro,
        turno_cede_fecha=date(2026, 7, 26), turno_cede_franja=tarde,
        turno_recibe_fecha=date(2026, 7, 25), turno_recibe_franja=manyana,
    ))
    db.session.commit()
    return documento, ana, pedro


def test_crear_documento_cambio_con_participantes(db):
    documento, ana, pedro = _crear_documento_con_dos_participantes(db, "a")

    recuperado = db.session.get(DocumentoCambio, documento.id)
    assert recuperado.estado == "borrador"
    assert recuperado.factibilidad_estado == "no_verificado"
    assert recuperado.match_id is None
    assert recuperado.creado_por_id == ana.id
    assert len(recuperado.participantes) == 2

    participante_ana = next(p for p in recuperado.participantes if p.usuario_id == ana.id)
    assert participante_ana.turno_cede_fecha == date(2026, 7, 25)
    assert participante_ana.turno_recibe_fecha == date(2026, 7, 26)


def test_documento_cambio_enlaza_a_match_opcional(db):
    crear_usuario, manyana, tarde = _setup(db, "b")
    ana = crear_usuario("anab@h.es")

    match = MatchCambio()
    db.session.add(match)
    db.session.flush()

    documento = DocumentoCambio(creado_por=ana, match=match)
    db.session.add(documento)
    db.session.commit()

    assert db.session.get(DocumentoCambio, documento.id).match_id == match.id


def test_participante_unico_por_documento_y_usuario(db):
    import pytest
    from sqlalchemy.exc import IntegrityError

    crear_usuario, manyana, tarde = _setup(db, "c")
    ana = crear_usuario("anac@h.es")
    documento = DocumentoCambio(creado_por=ana)
    db.session.add(documento)
    db.session.flush()

    p1 = ParticipanteDocumentoCambio(
        documento=documento, usuario=ana,
        turno_cede_fecha=date(2026, 7, 25), turno_cede_franja=manyana,
        turno_recibe_fecha=date(2026, 7, 26), turno_recibe_franja=tarde,
    )
    p2 = ParticipanteDocumentoCambio(
        documento=documento, usuario=ana,
        turno_cede_fecha=date(2026, 8, 1), turno_cede_franja=manyana,
        turno_recibe_fecha=date(2026, 8, 2), turno_recibe_franja=tarde,
    )
    db.session.add_all([p1, p2])
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_firma_documento_cambio(db):
    documento, ana, pedro = _crear_documento_con_dos_participantes(db, "d")

    firma = FirmaDocumentoCambio(
        documento=documento, usuario=ana,
        imagen_firma="data:image/png;base64,iVBORw0KG...",
        hash_documento="a" * 64,
    )
    db.session.add(firma)
    db.session.commit()

    recuperada = db.session.get(FirmaDocumentoCambio, firma.id)
    assert recuperada.usuario_id == ana.id
    assert recuperada.fecha_firma is not None
    assert recuperada.hash_documento == "a" * 64
    assert len(documento.firmas) == 1


def test_firma_unica_por_documento_y_usuario(db):
    import pytest
    from sqlalchemy.exc import IntegrityError

    documento, ana, pedro = _crear_documento_con_dos_participantes(db, "e")

    f1 = FirmaDocumentoCambio(
        documento=documento, usuario=ana, imagen_firma="x", hash_documento="a" * 64,
    )
    f2 = FirmaDocumentoCambio(
        documento=documento, usuario=ana, imagen_firma="y", hash_documento="b" * 64,
    )
    db.session.add_all([f1, f2])
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_todos_han_firmado_falso_si_falta_una(db):
    documento, ana, pedro = _crear_documento_con_dos_participantes(db, "f")

    db.session.add(FirmaDocumentoCambio(
        documento=documento, usuario=ana, imagen_firma="x", hash_documento="a" * 64,
    ))
    db.session.commit()

    assert documento.todos_han_firmado() is False


def test_todos_han_firmado_verdadero_si_firman_todos(db):
    documento, ana, pedro = _crear_documento_con_dos_participantes(db, "g")

    db.session.add_all([
        FirmaDocumentoCambio(documento=documento, usuario=ana, imagen_firma="x", hash_documento="a" * 64),
        FirmaDocumentoCambio(documento=documento, usuario=pedro, imagen_firma="y", hash_documento="b" * 64),
    ])
    db.session.commit()

    assert documento.todos_han_firmado() is True


def test_todos_han_firmado_falso_sin_participantes(db):
    crear_usuario, manyana, tarde = _setup(db, "h")
    ana = crear_usuario("anah@h.es")
    documento = DocumentoCambio(creado_por=ana)
    db.session.add(documento)
    db.session.commit()

    assert documento.todos_han_firmado() is False
