"""Genera el PDF de la 'hoja de cambio' (Solicitud de cambio de turno o
guardia) de un match directo ya confirmado por ambas partes, con las
firmas dibujadas al confirmar. Pensado para imprimir y llevar al hospital,
igual que el impreso en papel que sustituye."""
import base64
import io

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

_MARGEN = 20 * mm
_ANCHO_FIRMA = 50 * mm
_ALTO_FIRMA = 20 * mm


def _decodificar_firma(firma_data):
    if not firma_data:
        return None
    _, _, b64 = firma_data.partition(",")
    return ImageReader(io.BytesIO(base64.b64decode(b64)))


def _turno_texto(turno, cualquier_franja_ok=False):
    if turno is None:
        return "—"
    if cualquier_franja_ok and getattr(turno, "cualquier_franja", False):
        franja = "Cualquier turno"
    else:
        franja = turno.franja_horaria.nombre
    return f"{franja} — {turno.fecha.strftime('%d/%m/%Y')}"


def _dibujar_participacion(c, x, y, participacion):
    usuario = participacion.publicacion.usuario
    unidad = usuario.unidad

    c.setFont("Helvetica-Bold", 12)
    c.drawString(x, y, usuario.nombre)
    y -= 6 * mm

    c.setFont("Helvetica", 10)
    c.drawString(x, y, f"Hospital: {unidad.hospital.nombre}    Unidad: {unidad.nombre}    Categoría: {usuario.categoria.nombre}")
    y -= 7 * mm

    c.drawString(x, y, f"Cede el turno de: {_turno_texto(participacion.turno_cedido)}")
    y -= 6 * mm
    c.drawString(x, y, f"A cambio recibe: {_turno_texto(participacion.turno_aceptado, cualquier_franja_ok=True)}")
    y -= 6 * mm

    if participacion.fecha_confirmacion:
        c.drawString(x, y, f"Firmado el {participacion.fecha_confirmacion.strftime('%d/%m/%Y %H:%M')}")
    y -= 4 * mm

    imagen = _decodificar_firma(participacion.firma_data)
    if imagen is not None:
        c.rect(x, y - _ALTO_FIRMA, _ANCHO_FIRMA, _ALTO_FIRMA)
        c.drawImage(imagen, x, y - _ALTO_FIRMA, width=_ANCHO_FIRMA, height=_ALTO_FIRMA, mask="auto")
    y -= _ALTO_FIRMA + 8 * mm
    return y


def generar_pdf_hoja_cambio(match):
    """Devuelve el PDF (bytes) de la hoja de cambio de un match directo_2
    ya confirmado por ambas partes."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    ancho, alto = A4
    x = _MARGEN
    y = alto - _MARGEN

    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(ancho / 2, y, "Solicitud de cambio de turno o guardia")
    y -= 6 * mm
    c.setFont("Helvetica", 9)
    c.drawCentredString(ancho / 2, y, "Generado por Turnero")
    y -= 14 * mm

    for participacion in match.participaciones:
        y = _dibujar_participacion(c, x, y, participacion)

    y -= 6 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x, y, "Informe por parte de la supervisora de la unidad:")
    y -= 14 * mm
    c.setFont("Helvetica", 10)
    c.drawString(x, y, "Favorable: _____        Desfavorable: _____")
    y -= 14 * mm
    c.drawString(x, y, "La supervisora de la unidad,")

    c.showPage()
    c.save()
    return buffer.getvalue()
