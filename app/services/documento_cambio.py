"""
Servicio de la hoja de cambio digital: creación manual, firma cruzada entre
cuentas reales (cada participante firma su propia parte, desde su propia
cuenta) y generación de las notas en lenguaje natural que la ayudante copia
y pega en ilog.
"""
import hashlib
import io
from datetime import date, datetime, timezone

from flask import current_app, render_template
from flask_babel import _

from app.extensions import db
from app.models import (
    DocumentoCambio, ParticipanteDocumentoCambio, FirmaDocumentoCambio, Notificacion,
    TurnoPlanilla,
)
from app.push.sender import enviar_push
from app.services.email import enviar_email, url_absoluta
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


def _resumen_cambio(documento):
    """
    Resumen legible de quién hace el cambio y qué día/turno libra y trabaja
    cada participante. Se incluye en los avisos de autorización/denegación
    para que el destinatario vea los datos del cambio sin tener que entrar
    a la hoja.
    """
    return " ".join(
        _(
            "%(nombre)s libra %(turno_cede)s del %(fecha_cede)s y trabaja "
            "%(turno_recibe)s del %(fecha_recibe)s.",
            nombre=p.usuario.nombre,
            turno_cede=p.turno_cede_franja.nombre,
            fecha_cede=p.turno_cede_fecha.strftime("%d/%m/%Y"),
            turno_recibe=p.turno_recibe_franja.nombre,
            fecha_recibe=p.turno_recibe_fecha.strftime("%d/%m/%Y"),
        )
        for p in documento.participantes
    )


def _notificar(usuario, documento, tipo, titulo, cuerpo):
    db.session.add(Notificacion(usuario=usuario, documento_cambio=documento, tipo=tipo, mensaje=cuerpo))
    if usuario.push_activo:
        enviar_push(usuario, titulo, cuerpo, url=_url_documento(documento))


def _siguiente_numero_unidad(unidad_id):
    """
    Siguiente número de la secuencia propia de esa unidad (1, 2, 3...), la
    misma numeración absoluta que llevaba a mano la ayudante -- no el id
    autoincremental de Postgres, compartido por toda la app.
    """
    ultimo = (
        db.session.query(db.func.max(DocumentoCambio.numero_unidad))
        .filter(DocumentoCambio.unidad_id == unidad_id)
        .scalar()
    )
    return (ultimo or 0) + 1


def _enviar_email_completo(documento, usuario, companero):
    enlace = url_absoluta("documento_cambio.ver", documento_id=documento.id)
    cuerpo_html = render_template(
        "email/documento_cambio_completo.html",
        usuario=usuario, companero=companero, documento=documento, enlace=enlace,
    )
    enviar_email(usuario.email, _("Hoja de cambio completa"), cuerpo_html)


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
    documento = DocumentoCambio(
        creado_por=creado_por,
        unidad_id=creado_por.unidad_id,
        numero_unidad=_siguiente_numero_unidad(creado_por.unidad_id),
    )
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


def match_admite_documento_cambio(match) -> bool:
    """
    Un match solo puede generar su propio DocumentoCambio si es un
    intercambio simétrico entre 2 personas: cada participación cede Y
    recibe un turno con franja concreta (no 'cualquier turno'). Las
    coincidencias asimétricas (regalo/petición: una parte solo cede o solo
    recibe) y las cadenas de 3/4 bandas no encajan en el modelo de
    ParticipanteDocumentoCambio (cede/recibe obligatorios) y quedan fuera;
    para esos casos se sigue usando 'Mis hojas de cambio > Nueva hoja de
    cambio'.
    """
    if match.tipo != "directo_2" or len(match.participaciones) != 2:
        return False
    for p in match.participaciones:
        if p.turno_cedido is None or p.turno_aceptado is None:
            return False
        if p.turno_aceptado.cualquier_franja or p.turno_aceptado.franja_horaria_id is None:
            return False
    return True


def crear_documento_cambio_desde_match(match):
    """
    Crea el DocumentoCambio equivalente a un MatchCambio directo_2 ya
    detectado por el motor de matching (publicación automática o 'Me
    interesa'), reutilizando los turnos que ya tiene el match en vez de
    que el usuario los vuelva a escribir a mano. Solo válido si
    match_admite_documento_cambio(match) es True.

    No manda la notificación "pendiente de firma" de crear_documento_cambio:
    confirmar_participacion ya notifica al resto de partes que hay un
    cambio pendiente de confirmar.
    """
    p1, p2 = match.participaciones
    u1, u2 = p1.publicacion.usuario, p2.publicacion.usuario

    documento = DocumentoCambio(
        creado_por=u1, match=match,
        unidad_id=u1.unidad_id,
        numero_unidad=_siguiente_numero_unidad(u1.unidad_id),
    )
    db.session.add(documento)
    db.session.flush()

    documento.participantes.append(ParticipanteDocumentoCambio(
        usuario=u1,
        turno_cede_fecha=p1.turno_cedido.fecha, turno_cede_franja_id=p1.turno_cedido.franja_horaria_id,
        turno_recibe_fecha=p1.turno_aceptado.fecha, turno_recibe_franja_id=p1.turno_aceptado.franja_horaria_id,
    ))
    documento.participantes.append(ParticipanteDocumentoCambio(
        usuario=u2,
        turno_cede_fecha=p2.turno_cedido.fecha, turno_cede_franja_id=p2.turno_cedido.franja_horaria_id,
        turno_recibe_fecha=p2.turno_aceptado.fecha, turno_recibe_franja_id=p2.turno_aceptado.franja_horaria_id,
    ))
    db.session.flush()

    documento.factibilidad_estado = comprobar_factibilidad(documento)

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
            otro = next(o for o in documento.participantes if o.usuario_id != p.usuario_id)
            if p.usuario.notif_email_documento_cambio:
                _enviar_email_completo(documento, p.usuario, otro.usuario)
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
    Renderiza la hoja de cambio rellena y firmada como PDF. El impreso real
    del hospital (app/static/img/hoja-cambio-fondo.png) se usa como fondo a
    página completa; los datos se superponen en las mismas coordenadas que
    ocupan sus huecos en el impreso, vía @frame de xhtml2pdf (ver pdf.html).
    Se genera bajo demanda a partir de los datos guardados, no se persiste
    el binario en ningún sitio.

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
        numero_documento=documento.numero_unidad,
        meses=_MESES,
        firma_solicitante=firmas_por_usuario.get(solicitante.id),
        firma_companero=firmas_por_usuario.get(companero.id),
        fondo_path=f"{current_app.static_folder}/img/hoja-cambio-fondo.png",
        decision_supervisora=documento.decision_supervisora,
        motivo_denegacion=documento.motivo_denegacion,
        fecha_decision_supervisora=(
            documento.fecha_decision_supervisora.date()
            if documento.fecha_decision_supervisora else None
        ),
        firma_supervisora=documento.firma_supervisora,
    )

    buffer = io.BytesIO()
    resultado = pisa.CreatePDF(html, dest=buffer)
    if resultado.err:
        raise RuntimeError(f"Error generando el PDF: {resultado.log}")
    return buffer.getvalue()


def volcar_documento_a_planillas(documento):
    """
    Aplica el cambio ya autorizado a la planilla de cada participante:
    elimina el turno cedido, añade el turno recibido, y deja anotado el
    día con la misma nota en lenguaje natural que se ofrece para ilog
    (generar_notas_ilog) -- así queda constancia dentro de la propia app,
    igual que ya hace volcar_matches_a_planilla para los matches del motor
    de matching.
    """
    from app.services.planilla import añadir_turno, eliminar_turno
    from app.services.volcar_cambios import _añadir_linea_nota

    for p in documento.participantes:
        eliminar_turno(p.usuario, p.turno_cede_fecha, p.turno_cede_franja_id)
        añadir_turno(p.usuario, p.turno_recibe_fecha, p.turno_recibe_franja_id)

    for nota in generar_notas_ilog(documento):
        _añadir_linea_nota(nota["usuario"], nota["fecha"], nota["texto"])
    db.session.commit()


def autorizar_documento(documento, supervisora, imagen_firma=None):
    """
    La supervisora autoriza un documento completo (dos firmas): se vuelca
    a las planillas de los implicados y se notifica a ambos.

    `imagen_firma` es opcional aquí (para no atar este servicio a HTTP ni
    romper los flujos internos que ya lo llaman sin firma); la ruta HTTP es
    quien de verdad la exige antes de invocar esta función.
    """
    documento.decision_supervisora = "autorizado"
    documento.supervisora = supervisora
    documento.fecha_decision_supervisora = datetime.now(timezone.utc)
    if imagen_firma:
        documento.firma_supervisora = imagen_firma
    volcar_documento_a_planillas(documento)

    resumen = _resumen_cambio(documento)
    for p in documento.participantes:
        _notificar(
            p.usuario, documento, "documento_cambio_autorizado",
            _("Cambio autorizado"),
            _("La supervisora ha autorizado tu hoja de cambio nº %(numero)s del %(fecha)s. Ya se ha aplicado a tu planilla.", numero=documento.numero_unidad, fecha=documento.fecha_creacion.strftime('%d/%m/%Y'))
            + " " + resumen,
        )
    db.session.commit()
    return documento


def denegar_documento(documento, supervisora, motivo, imagen_firma=None):
    """
    La supervisora deniega un documento completo: no se toca ninguna
    planilla. `motivo` es obligatorio -- los participantes deben poder ver
    por qué se ha denegado, no solo que se ha denegado.

    `imagen_firma` es opcional aquí, ver `autorizar_documento`.
    """
    documento.decision_supervisora = "denegado"
    documento.supervisora = supervisora
    documento.fecha_decision_supervisora = datetime.now(timezone.utc)
    documento.motivo_denegacion = motivo
    if imagen_firma:
        documento.firma_supervisora = imagen_firma

    resumen = _resumen_cambio(documento)
    for p in documento.participantes:
        _notificar(
            p.usuario, documento, "documento_cambio_denegado",
            _("Cambio denegado"),
            _(
                "La supervisora ha denegado tu hoja de cambio nº %(numero)s del %(fecha)s. Motivo: %(motivo)s",
                numero=documento.numero_unidad, fecha=documento.fecha_creacion.strftime('%d/%m/%Y'), motivo=motivo,
            )
            + " " + resumen,
        )
    db.session.commit()
    return documento


def _fechas_turno(documento):
    """Las fechas de turno implicadas en el cambio (como mucho 2 distintas:
    la que cede y la que recibe cada participante son la misma pareja de
    fechas vista desde el otro lado)."""
    fechas = set()
    for p in documento.participantes:
        fechas.add(p.turno_cede_fecha)
        fechas.add(p.turno_recibe_fecha)
    return fechas


def puede_anularse(documento):
    """
    (bool, motivo_si_no_es_anulable). Un cambio solo se puede anular si:
    - ya está autorizado (nada que deshacer en pendiente/denegado) y no
      anulado ya de antes,
    - ningún turno implicado ha pasado todavía (deshacer un turno que ya
      se trabajó de verdad falsearía el historial, no lo corregiría),
    - la planilla actual de cada participante sigue tal cual quedó tras
      autorizar: tiene el turno que ganó y el que cedió sigue libre --
      si algo más lo ha tocado desde entonces (otro cambio posterior),
      deshacer a ciegas pisaría o duplicaría datos.
    No muta nada; solo consulta.
    """
    if documento.decision_supervisora != "autorizado":
        return False, _("Solo se puede anular un cambio ya autorizado.")
    if documento.anulado:
        return False, _("Este cambio ya está anulado.")

    hoy = date.today()
    if any(fecha < hoy for fecha in _fechas_turno(documento)):
        return False, _("No se puede anular: alguno de los turnos ya ha pasado.")

    for p in documento.participantes:
        recibido = TurnoPlanilla.query.filter_by(
            usuario_id=p.usuario_id, fecha=p.turno_recibe_fecha,
            franja_horaria_id=p.turno_recibe_franja_id,
        ).first()
        if recibido is None:
            return False, _("No se puede anular: la planilla ya no coincide con este cambio.")
        conflicto = TurnoPlanilla.query.filter_by(
            usuario_id=p.usuario_id, fecha=p.turno_cede_fecha,
            franja_horaria_id=p.turno_cede_franja_id,
        ).first()
        if conflicto is not None:
            return False, _("No se puede anular: el turno original ya está ocupado por otro cambio.")

    return True, None


def reabrir_match_de_documento(match):
    """
    Reabre un match ya confirmado_total cuyo DocumentoCambio se anula: los
    turnos implicados vuelven a 'abierto' y las publicaciones recalculan su
    estado, quedando de nuevo disponibles para nuevos cambios. El match
    pasa a 'anulado' -- distinto de 'rechazado' (un rechazo antes de
    confirmar, nunca llegó a resolver ningún turno).
    """
    match.estado = "anulado"
    for p in match.participaciones:
        if p.turno_cedido_id is not None:
            p.turno_cedido.estado = "abierto"
            p.publicacion.actualizar_estado()
        else:
            p.publicacion.estado = "abierta"
        if p.turno_aceptado_id is not None:
            p.turno_aceptado.estado = "abierto"


def anular_documento(documento, supervisora, motivo):
    """
    Deshace un cambio ya autorizado: revierte la planilla de cada
    participante (le quita lo que ganó, le devuelve lo que cedió) y, si el
    documento viene de un match del motor de matching, reabre ese match y
    sus publicaciones. No comprueba elegibilidad -- responsabilidad del
    llamador (ver puede_anularse), igual que autorizar_documento/
    denegar_documento.
    """
    from app.services.planilla import añadir_turno, eliminar_turno

    for p in documento.participantes:
        eliminar_turno(p.usuario, p.turno_recibe_fecha, p.turno_recibe_franja_id)
        añadir_turno(p.usuario, p.turno_cede_fecha, p.turno_cede_franja_id)

    if documento.match_id is not None:
        reabrir_match_de_documento(documento.match)

    documento.anulado = True
    documento.anulado_por = supervisora
    documento.fecha_anulacion = datetime.now(timezone.utc)
    documento.motivo_anulacion = motivo

    resumen = _resumen_cambio(documento)
    for p in documento.participantes:
        _notificar(
            p.usuario, documento, "documento_cambio_anulado",
            _("Cambio anulado"),
            _(
                "La supervisora ha anulado tu hoja de cambio nº %(numero)s del %(fecha)s. Motivo: %(motivo)s",
                numero=documento.numero_unidad, fecha=documento.fecha_creacion.strftime('%d/%m/%Y'), motivo=motivo,
            )
            + " " + resumen,
        )
    db.session.commit()
    return documento
