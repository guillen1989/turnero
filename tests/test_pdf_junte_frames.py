"""
Tests de los frames del junte de noches en documento_cambio/pdf.html (ver
especificacion-app-cambio-turnos.md). Todavía no hay un DocumentoCambio de
tipo junte (ParticipanteDocumentoCambio no admite ese modelo, ver
match_admite_documento_cambio en app/services/documento_cambio.py), así que
estos tests renderizan la plantilla directamente en vez de pasar por
generar_pdf_documento -- validan solo el layout de los nuevos @frame.
"""
import io
from datetime import date
from types import SimpleNamespace

import pypdf
from flask import current_app, render_template
from xhtml2pdf import pisa

_FRANJA = SimpleNamespace(nombre="Noche")
_PARTICIPANTE_STUB = SimpleNamespace(
    turno_cede_franja=_FRANJA, turno_cede_fecha=date(2026, 7, 7),
    turno_recibe_franja=_FRANJA, turno_recibe_fecha=date(2026, 7, 14),
)
_SOLICITANTE_STUB = SimpleNamespace(categoria=SimpleNamespace(nombre="Enfermería"))


def _renderizar_pdf(app, **contexto):
    with app.app_context():
        html = render_template(
            "documento_cambio/pdf.html",
            hospital_nombre="Hospital La Paz",
            unidad_nombre="Urgencias",
            solicitante_nombre="",
            companero_nombre="",
            solicitante=_SOLICITANTE_STUB,
            participante_solicitante=_PARTICIPANTE_STUB,
            companero=None,
            fecha_documento=date(2026, 7, 1),
            numero_documento=1,
            meses=[None] + [str(m) for m in range(1, 13)],
            firma_solicitante=None,
            firma_companero=None,
            fondo_path=f"{current_app.static_folder}/img/hoja-cambio-fondo.png",
            decision_supervisora="pendiente",
            motivo_denegacion=None,
            fecha_decision_supervisora=None,
            firma_supervisora=None,
            **contexto,
        )
        buffer = io.BytesIO()
        resultado = pisa.CreatePDF(html, dest=buffer)
        assert not resultado.err
        return buffer.getvalue()


def test_junte_nombres_no_se_muestran_si_mostrar_junte_es_falso(app):
    pdf_bytes = _renderizar_pdf(app, mostrar_junte=False)
    texto = pypdf.PdfReader(io.BytesIO(pdf_bytes)).pages[0].extract_text()
    assert "Ana Torres" not in texto


def test_junte_muestra_nombres_de_ambas_tablas(app):
    pdf_bytes = _renderizar_pdf(
        app,
        mostrar_junte=True,
        junte_corresponde_3_nombre="Ana Torres",
        junte_corresponde_4_nombre="Beatriz Ruiz",
        junte_cambio_3_nombre="Ana Torres",
        junte_cambio_4_nombre="Beatriz Ruiz",
        junte_cambio_3_dias=["", "N", "", "N", "", "N", ""],
        junte_cambio_4_dias=["N", "", "N", "", "N", "", "N"],
    )
    texto = pypdf.PdfReader(io.BytesIO(pdf_bytes)).pages[0].extract_text()
    assert texto.count("Ana Torres") == 2
    assert texto.count("Beatriz Ruiz") == 2


def test_junte_muestra_las_noches_resultantes_del_cambio_en_las_7_columnas(app):
    """Regresión: xhtml2pdf/reportlab descartan en silencio el contenido de
    un @frame si su altura no alcanza el mínimo -- ver PROGRESS.md, Fase 10.
    Las filas de la tabla CAMBIO son las más ajustadas (~6.15-6.27mm), así
    que hay que comprobar que las 7 marcas de cada fila llegan al PDF."""
    dias_3 = ["L3", "M3", "X3", "J3", "V3", "S3", "D3"]
    dias_4 = ["L4", "M4", "X4", "J4", "V4", "S4", "D4"]
    pdf_bytes = _renderizar_pdf(
        app,
        mostrar_junte=True,
        junte_corresponde_3_nombre="Ana Torres",
        junte_corresponde_4_nombre="Beatriz Ruiz",
        junte_cambio_3_nombre="Ana Torres",
        junte_cambio_4_nombre="Beatriz Ruiz",
        junte_cambio_3_dias=dias_3,
        junte_cambio_4_dias=dias_4,
    )
    texto = pypdf.PdfReader(io.BytesIO(pdf_bytes)).pages[0].extract_text()
    for marca in dias_3 + dias_4:
        assert marca in texto
