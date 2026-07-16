"""Tests del PDF de la 'hoja de cambio' (Solicitud de cambio de turno o
guardia), generado bajo demanda a partir de un match directo ya confirmado
por ambas partes, con las firmas dibujadas al confirmar."""
from datetime import date, datetime, timezone

from pypdf import PdfReader
import io

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
from app.services.hoja_cambio import generar_pdf_hoja_cambio
from app.services.registro import registrar_usuario

# PNG 1x1 transparente válido.
FIRMA = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4"
    "2mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _match_confirmado_total(db):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    ana = registrar_usuario("Ana García", "ana@test.es", "password123", "Hospital La Paz", "Urgencias", cat.id)
    pedro = registrar_usuario("Pedro Ruiz", "pedro@test.es", "password123", "Hospital La Paz", "Urgencias", cat.id)

    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=ana.unidad.grupo_intercambio_id, nombre="Mañana"
    ).first()

    pub_ana = PublicacionCambio(usuario_id=ana.id)
    db.session.add(pub_ana)
    db.session.flush()
    tc_ana = TurnoCedido(publicacion_id=pub_ana.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id, estado="resuelto")
    ta_ana = TurnoAceptado(publicacion_id=pub_ana.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id, estado="resuelto")
    db.session.add_all([tc_ana, ta_ana])

    pub_pedro = PublicacionCambio(usuario_id=pedro.id)
    db.session.add(pub_pedro)
    db.session.flush()
    tc_pedro = TurnoCedido(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id, estado="resuelto")
    ta_pedro = TurnoAceptado(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id, estado="resuelto")
    db.session.add_all([tc_pedro, ta_pedro])

    match = MatchCambio(tipo="directo_2", estado="confirmado_total", fecha_confirmacion_total=datetime.now(timezone.utc))
    db.session.add(match)
    db.session.flush()
    ahora = datetime.now(timezone.utc)
    db.session.add(MatchParticipacion(
        match_id=match.id, publicacion_id=pub_ana.id, turno_cedido_id=tc_ana.id, turno_aceptado_id=ta_ana.id,
        confirmado=True, fecha_confirmacion=ahora, firma_data=FIRMA,
    ))
    db.session.add(MatchParticipacion(
        match_id=match.id, publicacion_id=pub_pedro.id, turno_cedido_id=tc_pedro.id, turno_aceptado_id=ta_pedro.id,
        confirmado=True, fecha_confirmacion=ahora, firma_data=FIRMA,
    ))
    db.session.commit()

    return ana, pedro, match


def _texto_pdf(pdf_bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() for page in reader.pages)


def test_generar_pdf_devuelve_bytes_con_cabecera_pdf(db):
    ana, pedro, match = _match_confirmado_total(db)
    pdf_bytes = generar_pdf_hoja_cambio(match)
    assert pdf_bytes[:5] == b"%PDF-"


def test_generar_pdf_incluye_nombres_de_ambos_usuarios(db):
    ana, pedro, match = _match_confirmado_total(db)
    texto = _texto_pdf(generar_pdf_hoja_cambio(match))
    assert "Ana García" in texto
    assert "Pedro Ruiz" in texto


def test_generar_pdf_incluye_hospital_unidad_categoria(db):
    ana, pedro, match = _match_confirmado_total(db)
    texto = _texto_pdf(generar_pdf_hoja_cambio(match))
    assert "Hospital La Paz" in texto
    assert "Urgencias" in texto
    assert "Enfermería" in texto


def test_generar_pdf_incluye_fechas_y_franjas_de_los_turnos(db):
    ana, pedro, match = _match_confirmado_total(db)
    texto = _texto_pdf(generar_pdf_hoja_cambio(match))
    assert "01/09/2026" in texto
    assert "02/09/2026" in texto
    assert "Mañana" in texto
