"""
Servicio de la hoja de cambio digital: creación manual, firma cruzada entre
cuentas reales (cada participante firma su propia parte, desde su propia
cuenta) y generación de las notas en lenguaje natural que la ayudante copia
y pega en ilog.
"""
import hashlib
import io

from flask import current_app, render_template
from flask_babel import _

from app.extensions import db
from app.models import DocumentoCambio, ParticipanteDocumentoCambio, FirmaDocumentoCambio, Notificacion
from app.push.sender import enviar_push
from app.services.factibilidad_documento_cambio import comprobar_factibilidad

_MESES = [
    None, "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _formatear_fecha(fecha):
    return f"{fecha.day} de {_MESES[fecha.month]}"


def _url_documento(documento):
    from flask import url_for
    return url_for("documento_cambio.ver", documento_id=documento.id)


def _notificar(usuario, documento, tipo, titulo, cuerpo):
    db.session.add(Notificacion(usuario=usuario, documento_cambio=documento, tipo=tipo, mensaje=cuerpo))
    if usuario.push_activo:
        enviar_push(usuario, titulo, cuerpo, url=_url_documento(documento))


def crear_documento_cambio(
    creado_por, companero,
    turno_cede_fecha, turno_cede_franja_id,
    turno_recibe_fecha, turno_recibe_franja_id,
):
    """
    Crea el documento con sus dos participantes espejo: lo que cede/recibe
    creado_por es exactamente lo que recibe/cede companero. Notifica al
    compañero (a quien lo crea no le hace falta, ya sabe que lo acaba de
    hacer) de que tiene una hoja de cambio pendiente de su firma.
    """
    documento = DocumentoCambio(creado_por=creado_por)
    db.session.add(documento)
    db.session.flush()

    documento.participantes.append(ParticipanteDocumentoCambio(
        usuario=creado_por,
        turno_cede_fecha=turno_cede_fecha, turno_cede_franja_id=turno_cede_franja_id,
        turno_recibe_fecha=turno_recibe_fecha, turno_recibe_franja_id=turno_recibe_franja_id,
    ))
    documento.participantes.append(ParticipanteDocumentoCambio(
        usuario=companero,
        turno_cede_fecha=turno_recibe_fecha, turno_cede_franja_id=turno_recibe_franja_id,
        turno_recibe_fecha=turno_cede_fecha, turno_recibe_franja_id=turno_cede_franja_id,
    ))
    db.session.flush()

    documento.factibilidad_estado = comprobar_factibilidad(documento)

    _notificar(
        companero, documento, "documento_cambio_pendiente_firma",
        _("Hoja de cambio pendiente de firma"),
        _("%(nombre)s ha creado una hoja de cambio contigo. Fírmala cuando puedas.", nombre=creado_por.nombre),
    )

    db.session.commit()
    return documento


def _hash_contenido(documento):
    """
    Huella del contenido firmable (quién cede/recibe qué). Igual para todas
    las firmas mientras el documento no cambie, así se puede demostrar más
    adelante qué se firmó exactamente aunque cambie la plantilla del PDF.
    """
    partes = sorted(
        f"{p.usuario_id}:{p.turno_cede_fecha}:{p.turno_cede_franja_id}:"
        f"{p.turno_recibe_fecha}:{p.turno_recibe_franja_id}"
        for p in documento.participantes
    )
    contenido = f"{documento.id}|" + "|".join(partes)
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()


def firmar_documento(documento, usuario, imagen_firma):
    """
    Registra la firma de `usuario`. El estado pasa a pendiente_firmas tras
    la primera firma y a completo en cuanto han firmado todos los
    participantes.

    Al completarse (última firma), recalcula la factibilidad: puede haber
    pasado tiempo desde que se creó el documento y alguien haber publicado
    o cambiado su planilla mientras tanto, así que el resultado guardado en
    la creación podría estar desactualizado justo cuando más importa (el
    momento de cerrar el documento).

    Notifica: si aún falta alguien por firmar, a quien falta (para que sepa
    que ya solo depende de él/ella); si el documento queda completo, a
    todos los participantes.
    """
    firma = FirmaDocumentoCambio(
        documento=documento, usuario=usuario,
        imagen_firma=imagen_firma,
        hash_documento=_hash_contenido(documento),
    )
    db.session.add(firma)
    db.session.flush()

    if documento.todos_han_firmado():
        documento.estado = "completo"
        documento.factibilidad_estado = comprobar_factibilidad(documento)
        for p in documento.participantes:
            _notificar(
                p.usuario, documento, "documento_cambio_completo",
                _("Hoja de cambio completa"),
                _("Las dos firmas están recogidas. La hoja de cambio ya está completa."),
            )
    else:
        documento.estado = "pendiente_firmas"
        ids_firmantes = {f.usuario_id for f in documento.firmas}
        for p in documento.participantes:
            if p.usuario_id not in ids_firmantes:
                _notificar(
                    p.usuario, documento, "documento_cambio_pendiente_firma",
                    _("Falta tu firma en la hoja de cambio"),
                    _("%(nombre)s ya ha firmado. Solo falta tu firma para completar la hoja de cambio.", nombre=usuario.nombre),
                )

    db.session.commit()
    return firma


def generar_notas_ilog(documento):
    """
    Devuelve, por cada participante, dos notas en lenguaje natural listas
    para copiar y pegar en la nota del día correspondiente en ilog: una
    para el día que libra (cede) y otra para el día que trabaja (recibe).
    Un cambio 1 a 1 afecta a 4 casillas (2 trabajadores x 2 días), así que
    devuelve 4 notas. Cada entrada: {usuario, fecha, texto}.
    """
    notas = []
    for p in documento.participantes:
        otro = next(o for o in documento.participantes if o.usuario_id != p.usuario_id)

        notas.append({
            "usuario": p.usuario,
            "fecha": p.turno_cede_fecha,
            "texto": (
                f"Libra el turno de {p.turno_cede_franja.nombre.lower()} a cambio de "
                f"trabajarle a {otro.usuario.nombre} el turno de "
                f"{p.turno_recibe_franja.nombre.lower()} del {_formatear_fecha(p.turno_recibe_fecha)}."
            ),
        })
        notas.append({
            "usuario": p.usuario,
            "fecha": p.turno_recibe_fecha,
            "texto": (
                f"Trabaja el turno de {p.turno_recibe_franja.nombre.lower()} a "
                f"{otro.usuario.nombre} a cambio de que {otro.usuario.nombre} le "
                f"trabaje el turno de {p.turno_cede_franja.nombre.lower()} del "
                f"{_formatear_fecha(p.turno_cede_fecha)}."
            ),
        })
    return notas


def generar_pdf_documento(documento):
    """
    Renderiza la hoja de cambio rellena y firmada como PDF, fiel al impreso
    real (hojacambios.png). Se genera bajo demanda a partir de los datos
    guardados, no se persiste el binario en ningún sitio.

    xhtml2pdf (no WeasyPrint) a propósito: WeasyPrint necesita Pango/
    cairo/gdk-pixbuf vía cffi, y esas librerías de sistema no estaban
    disponibles en Railway (crash en producción, ver PROGRESS.md, Fase
    10). xhtml2pdf es Python puro (usa reportlab por debajo), sin
    dependencias nativas, así que no puede volver a pasar.
    """
    from xhtml2pdf import pisa
    solicitante = documento.creado_por
    participante_solicitante = next(
        p for p in documento.participantes if p.usuario_id == solicitante.id
    )
    companero = next(
        p.usuario for p in documento.participantes if p.usuario_id != solicitante.id
    )
    firmas_por_usuario = {f.usuario_id: f for f in documento.firmas}

    html = render_template(
        "documento_cambio/pdf.html",
        hospital_nombre=solicitante.unidad.hospital.nombre,
        unidad_nombre=solicitante.unidad.nombre,
        solicitante=solicitante,
        participante_solicitante=participante_solicitante,
        companero=companero,
        fecha_documento=documento.fecha_creacion.date(),
        numero_documento=documento.id,
        meses=_MESES,
        firma_solicitante=firmas_por_usuario.get(solicitante.id),
        firma_companero=firmas_por_usuario.get(companero.id),
        logo_path=f"{current_app.static_folder}/img/logo-hospital-la-paz.png",
    )

    buffer = io.BytesIO()
    resultado = pisa.CreatePDF(html, dest=buffer)
    if resultado.err:
        raise RuntimeError(f"Error generando el PDF: {resultado.log}")
    return buffer.getvalue()
