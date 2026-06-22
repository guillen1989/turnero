"""Tests para el sistema de avisos por email al detectar un match."""
from datetime import date, time
from unittest.mock import patch

from app.extensions import db
from app.models import (
    Categoria,
    FranjaHoraria,
    PublicacionCambio,
    TurnoCedido,
    TurnoAceptado,
    insertar_categorias_semilla,
)
from app.models.aviso_email import AvisoEmail
from app.services.registro import registrar_usuario
from app.services.email import enviar_aviso_match


def _setup(db):
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
    db.session.add(TurnoCedido(publicacion_id=pub_ana.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub_ana.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id))
    pub_pedro = PublicacionCambio(usuario_id=pedro.id)
    db.session.add(pub_pedro)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id))
    db.session.commit()
    return ana, pedro, pub_ana, pub_pedro


def test_no_envia_email_si_avisos_desactivados(db):
    """Si el usuario no tiene avisos activados, no se envía email."""
    ana, pedro, pub_ana, _ = _setup(db)
    ana.avisos_email = False
    db.session.commit()

    with patch("app.services.email._enviar_correo") as mock_mail:
        enviar_aviso_match(ana, pub_ana, date(2026, 9, 1))
        mock_mail.assert_not_called()


def test_envia_email_si_avisos_activados(db):
    """Si el usuario tiene avisos activados y no ha alcanzado el límite, se envía email."""
    ana, pedro, pub_ana, _ = _setup(db)
    ana.avisos_email = True
    ana.limite_avisos_email = 3
    db.session.commit()

    with patch("app.services.email._enviar_correo") as mock_mail:
        enviar_aviso_match(ana, pub_ana, date(2026, 9, 1))
        mock_mail.assert_called_once()
        aviso = AvisoEmail.query.filter_by(usuario_id=ana.id).first()
        assert aviso is not None


def test_no_envia_si_limite_alcanzado(db):
    """Si el usuario ya alcanzó su límite diario, no se envía email."""
    ana, pedro, pub_ana, _ = _setup(db)
    ana.avisos_email = True
    ana.limite_avisos_email = 2
    db.session.commit()

    hoy = date(2026, 9, 1)
    # Simular 2 avisos ya enviados hoy
    db.session.add(AvisoEmail(usuario_id=ana.id, fecha=hoy))
    db.session.add(AvisoEmail(usuario_id=ana.id, fecha=hoy))
    db.session.commit()

    with patch("app.services.email._enviar_correo") as mock_mail:
        enviar_aviso_match(ana, pub_ana, hoy)
        mock_mail.assert_not_called()


def test_ultimo_email_del_dia_incluye_advertencia(db):
    """El último email del día (al alcanzar el límite) incluye texto de advertencia."""
    ana, pedro, pub_ana, _ = _setup(db)
    ana.avisos_email = True
    ana.limite_avisos_email = 3
    db.session.commit()

    hoy = date(2026, 9, 1)
    # Simular 2 avisos ya enviados (el siguiente será el 3.º = último)
    db.session.add(AvisoEmail(usuario_id=ana.id, fecha=hoy))
    db.session.add(AvisoEmail(usuario_id=ana.id, fecha=hoy))
    db.session.commit()

    captured = {}
    def fake_enviar(destinatario, asunto, cuerpo):
        captured["asunto"] = asunto
        captured["cuerpo"] = cuerpo

    with patch("app.services.email._enviar_correo", side_effect=fake_enviar):
        enviar_aviso_match(ana, pub_ana, hoy)

    assert "límite" in captured["cuerpo"].lower() or "limite" in captured["cuerpo"].lower()


def test_avisos_de_dias_anteriores_no_cuentan(db):
    """Los avisos de días anteriores no afectan al contador del día de hoy."""
    ana, pedro, pub_ana, _ = _setup(db)
    ana.avisos_email = True
    ana.limite_avisos_email = 1
    db.session.commit()

    ayer = date(2026, 8, 31)
    hoy = date(2026, 9, 1)
    # 1 aviso de ayer (no debería contar)
    db.session.add(AvisoEmail(usuario_id=ana.id, fecha=ayer))
    db.session.commit()

    with patch("app.services.email._enviar_correo") as mock_mail:
        enviar_aviso_match(ana, pub_ana, hoy)
        mock_mail.assert_called_once()
