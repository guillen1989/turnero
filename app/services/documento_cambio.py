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
from app.services.junte_semanal import distribucion_desde_fechas

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
            nombre=p.nombre_mostrar,
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


def _usuario_que_recibe(documento, participante):
    """
    Dado un participante p, devuelve el usuario del participante o que
    recibe el turno que p cede (ciclo A→B→C→A). Funciona igual de bien
    para 2 o para 3 participantes y reemplaza el patrón «otro por
    exclusión» que solo vale para 2.

    Para un documento de 3 participantes en ciclo A→B→C→A:
    - _usuario_que_recibe(doc, p_a) → usuario_b (B recibe lo que A cede)
    - _usuario_que_recibe(doc, p_b) → usuario_c (C recibe lo que B cede)
    - _usuario_que_recibe(doc, p_c) → usuario_a (A recibe lo que C cede)

    Si ningún participante recibe exactamente el turno cedido (documento
    mal construido o inconsistente), devuelve None.
    """
    for o in documento.participantes:
        if o.id == participante.id:
            continue
        if (o.turno_recibe_fecha == participante.turno_cede_fecha
                and o.turno_recibe_franja_id == participante.turno_cede_franja_id):
            return o.usuario
    return None


def crear_documento_cambio(
    creado_por, companero,
    turno_cede_fecha, turno_cede_franja_id,
    turno_recibe_fecha, turno_recibe_franja_id,
    depende_de_id=None,
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
        depende_de_id=depende_de_id,
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

    estado, motivos = comprobar_factibilidad(documento)
    documento.factibilidad_estado = estado
    documento.factibilidad_motivos = "\n".join(motivos) if motivos else None

    _notificar(
        companero, documento, "documento_cambio_pendiente_firma",
        _("Hoja de cambio pendiente de firma"),
        _("%(nombre)s ha creado una hoja de cambio contigo. Fírmala cuando puedas.", nombre=creado_por.nombre),
    )

    db.session.commit()
    return documento


def crear_documento_cambio_junte(
    creado_por, companero, cedidos, aceptados, depende_de_id=None,
):
    """
    Como crear_documento_cambio, pero para un junte de varias noches: crea
    una fila espejo por cada noche en vez de una sola.

    cedidos/aceptados son listas de (fecha, franja_id) de creado_por, del
    mismo formato y misma longitud (una noche cedida se empareja con la
    noche aceptada de su mismo índice).
    """
    documento = DocumentoCambio(
        creado_por=creado_por,
        unidad_id=creado_por.unidad_id,
        numero_unidad=_siguiente_numero_unidad(creado_por.unidad_id),
        tipo="junte",
        depende_de_id=depende_de_id,
    )
    db.session.add(documento)
    db.session.flush()

    for (cede_fecha, cede_franja_id), (recibe_fecha, recibe_franja_id) in zip(cedidos, aceptados):
        documento.participantes.append(ParticipanteDocumentoCambio(
            usuario=creado_por,
            turno_cede_fecha=cede_fecha, turno_cede_franja_id=cede_franja_id,
            turno_recibe_fecha=recibe_fecha, turno_recibe_franja_id=recibe_franja_id,
        ))
        documento.participantes.append(ParticipanteDocumentoCambio(
            usuario=companero,
            turno_cede_fecha=recibe_fecha, turno_cede_franja_id=recibe_franja_id,
            turno_recibe_fecha=cede_fecha, turno_recibe_franja_id=cede_franja_id,
        ))
    db.session.flush()

    estado, motivos = comprobar_factibilidad(documento)
    documento.factibilidad_estado = estado
    documento.factibilidad_motivos = "\n".join(motivos) if motivos else None

    _notificar(
        companero, documento, "documento_cambio_pendiente_firma",
        _("Hoja de cambio pendiente de firma"),
        _("%(nombre)s ha creado una hoja de cambio contigo. Fírmala cuando puedas.", nombre=creado_por.nombre),
    )

    db.session.commit()
    return documento


class CambioNoFactibleError(Exception):
    """Se lanza cuando el cambio que se intenta registrar desde papel no es
    factible según las planillas ya publicadas (alguna de las partes no
    puede ceder o recibir el turno indicado).

    `motivos` es una lista de cadenas legibles con el detalle de cada fallo."""

    def __init__(self, motivos=None):
        super().__init__()
        self.motivos = motivos or []


def registrar_documento_cambio_papel(
    supervisora, usuario1, usuario2,
    turno1_cede_fecha, turno1_cede_franja_id,
    turno1_recibe_fecha, turno1_recibe_franja_id,
    depende_de_id=None,
):
    """
    Registra un cambio que un pequeño número de trabajadores sigue
    formalizando en papel en vez de con la app. Como ya se firmó a mano
    entre los dos implicados, no tiene sentido pedir firmas digitales ni
    dejarlo pendiente de decisión: queda directamente `completo` y
    `autorizado`, aplicándose ya a las planillas (el objetivo real es
    mantenerlas al día para que la comprobación de factibilidad de futuros
    cambios sea correcta). `origen_papel=True` lo distingue de los cambios
    creados y firmados desde la app.

    Si la comprobación de factibilidad determina que el cambio no es
    factible (con las planillas ya publicadas), no se crea ni se aplica:
    se lanza CambioNoFactibleError para que quien llame avise a la
    supervisora en vez de dejar la planilla inconsistente con lo que de
    verdad tienen firmado los dos trabajadores en papel.
    """
    documento = DocumentoCambio(
        creado_por=usuario1,
        unidad_id=usuario1.unidad_id,
        numero_unidad=_siguiente_numero_unidad(usuario1.unidad_id),
        estado="completo",
        origen_papel=True,
        depende_de_id=depende_de_id,
    )
    db.session.add(documento)
    db.session.flush()

    documento.participantes.append(ParticipanteDocumentoCambio(
        usuario=usuario1,
        turno_cede_fecha=turno1_cede_fecha, turno_cede_franja_id=turno1_cede_franja_id,
        turno_recibe_fecha=turno1_recibe_fecha, turno_recibe_franja_id=turno1_recibe_franja_id,
    ))
    documento.participantes.append(ParticipanteDocumentoCambio(
        usuario=usuario2,
        turno_cede_fecha=turno1_recibe_fecha, turno_cede_franja_id=turno1_recibe_franja_id,
        turno_recibe_fecha=turno1_cede_fecha, turno_recibe_franja_id=turno1_cede_franja_id,
    ))
    db.session.flush()

    estado, motivos = comprobar_factibilidad(documento)
    if estado == "no_factible":
        db.session.rollback()
        raise CambioNoFactibleError(motivos)

    documento.factibilidad_estado = estado
    documento.factibilidad_motivos = "\n".join(motivos) if motivos else None
    _congelar_nombres(documento)
    db.session.commit()

    return autorizar_documento(documento, supervisora)


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

    estado, motivos = comprobar_factibilidad(documento)
    documento.factibilidad_estado = estado
    documento.factibilidad_motivos = "\n".join(motivos) if motivos else None

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


def _congelar_nombres(documento):
    """
    Copia el nombre en vivo de cada participante a nombre_congelado en el
    momento en que el documento se completa (queda como equivalente de un
    papel firmado). Si más adelante se elimina alguna de las dos cuentas,
    la hoja de cambio sigue mostrando quién firmó de verdad.
    """
    for p in documento.participantes:
        p.nombre_congelado = p.usuario.nombre


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
        estado, motivos = comprobar_factibilidad(documento)
        documento.factibilidad_estado = estado
        documento.factibilidad_motivos = "\n".join(motivos) if motivos else None
        _congelar_nombres(documento)
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
            "nombre": p.nombre_mostrar,
            "fecha": p.turno_cede_fecha,
            "texto": (
                f"Libra el turno de {p.turno_cede_franja.nombre.lower()} a cambio de "
                f"trabajarle a {otro.nombre_mostrar} el turno de "
                f"{p.turno_recibe_franja.nombre.lower()} del {_formatear_fecha(p.turno_recibe_fecha)}."
            ),
        })
        notas.append({
            "usuario": p.usuario,
            "nombre": p.nombre_mostrar,
            "fecha": p.turno_recibe_fecha,
            "texto": (
                f"Trabaja el turno de {p.turno_recibe_franja.nombre.lower()} a "
                f"{otro.nombre_mostrar} a cambio de que {otro.nombre_mostrar} le "
                f"trabaje el turno de {p.turno_cede_franja.nombre.lower()} del "
                f"{_formatear_fecha(p.turno_cede_fecha)}."
            ),
        })
    return notas


def _contexto_pdf_cadena_3(documento):
    """
    Variables mostrar_cadena_3 / cede_tercer_* / tercer_companero_* /
    firma_tercero que espera documento_cambio/pdf.html cuando
    documento.tipo == "cadena_3". Si el documento no es una cadena_3,
    devuelve solo mostrar_cadena_3=False.
    """
    if documento.tipo != "cadena_3":
        return {"mostrar_cadena_3": False}

    solicitante_id = documento.creado_por_id
    p_solicitante = next(
        p for p in documento.participantes if p.usuario_id == solicitante_id
    )
    companero = _usuario_que_recibe(documento, p_solicitante)

    p_tercero = next(
        p for p in documento.participantes
        if p.usuario_id != solicitante_id and p.usuario_id != companero.id
    )
    tercero = p_tercero.usuario
    receptor_tercero = _usuario_que_recibe(documento, p_tercero)

    return {
        "mostrar_cadena_3": True,
        "cede_tercer_franja_c": p_tercero.turno_cede_franja.nombre,
        "cede_tercer_fecha_c": (
            f"{p_tercero.turno_cede_fecha.strftime('%d/%m/%Y')} "
            f"({_('lo trabaja')} {receptor_tercero.nombre})"
        ),
        "tercer_companero_c": tercero.nombre,
        "firma_tercero": next(
            (f for f in documento.firmas if f.usuario_id == tercero.id), None
        ),
    }


def _contexto_pdf_junte(documento):
    """
    Variables junte_* que espera documento_cambio/pdf.html cuando
    documento.tipo == "junte": agrupa las filas por usuario (2 grupos) y
    calcula, con distribucion_desde_fechas, qué noches de la semana
    trabajaría/libraría cada uno tras el junte. Por construcción de las
    cadencias LMVD (4 noches) y MJS (3 noches), siempre hay una persona con
    num_noches == 3 y otra con num_noches == 4 -- de ahí las variables
    *_3_*/*_4_*. Si el documento no es un junte, devuelve solo
    mostrar_junte=False.
    """
    if documento.tipo != "junte":
        return {"mostrar_junte": False}

    por_usuario = {}
    for p in documento.participantes:
        por_usuario.setdefault(p.usuario_id, []).append(p)

    contexto = {"mostrar_junte": True}
    for filas in por_usuario.values():
        _, trabaja, _libra, num_noches = distribucion_desde_fechas(
            [p.turno_cede_fecha for p in filas],
            [p.turno_recibe_fecha for p in filas],
        )
        dias = ["N" if d in trabaja else "" for d in range(7)]
        contexto[f"junte_corresponde_{num_noches}_nombre"] = filas[0].nombre_mostrar
        contexto[f"junte_cambio_{num_noches}_nombre"] = filas[0].nombre_mostrar
        contexto[f"junte_cambio_{num_noches}_dias"] = dias
    return contexto


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
    if documento.tipo == "cadena_3":
        p_solicitante = next(
            p for p in documento.participantes if p.usuario_id == solicitante.id
        )
        companero = _usuario_que_recibe(documento, p_solicitante)
        p_companero = next(
            p for p in documento.participantes if p.usuario_id == companero.id
        )
        cede_fecha_receptor_nombre = companero.nombre if companero else None
        p_tercero = next(
            p for p in documento.participantes
            if p.usuario_id != solicitante.id and p.usuario_id != companero.id
        )
        receptor_recibe = _usuario_que_recibe(documento, p_tercero)
        recibe_fecha_receptor_nombre = receptor_recibe.nombre if receptor_recibe else None
        solicitante_nombre = p_solicitante.nombre_mostrar
        companero_nombre = p_companero.nombre_mostrar
    else:
        p_solicitante = next(
            p for p in documento.participantes if p.usuario_id == solicitante.id
        )
        p_companero = next(
            p for p in documento.participantes if p.usuario_id != solicitante.id
        )
        companero = p_companero.usuario
        cede_fecha_receptor_nombre = None
        recibe_fecha_receptor_nombre = None
        solicitante_nombre = p_solicitante.nombre_mostrar
        companero_nombre = p_companero.nombre_mostrar

    firmas_por_usuario = {f.usuario_id: f for f in documento.firmas}

    html = render_template(
        "documento_cambio/pdf.html",
        hospital_nombre=solicitante.unidad.hospital.nombre,
        unidad_nombre=solicitante.unidad.nombre,
        solicitante_nombre=solicitante_nombre,
        companero_nombre=companero_nombre,
        solicitante=solicitante,
        participante_solicitante=p_solicitante,
        companero=companero,
        fecha_documento=documento.fecha_creacion.date(),
        numero_documento=documento.numero_unidad,
        meses=_MESES,
        cede_fecha_receptor_nombre=cede_fecha_receptor_nombre,
        recibe_fecha_receptor_nombre=recibe_fecha_receptor_nombre,
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
        **_contexto_pdf_junte(documento),
        **_contexto_pdf_cadena_3(documento),
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


def _recalcular_factibilidad_dependientes(documento):
    """
    Tras autorizar, denegar o anular un documento, los documentos que
    dependen de él pueden cambiar de factibilidad (el overlay que antes los
    hacía factibles ya no aplica, o el estado real de las planillas ha
    cambiado). Recalcula la factibilidad de todos los dependientes directos.
    No recorre en cascada: cada dependiente se recalcula contra el nuevo
    estado (si el predecesor se autorizó y volcó a planillas, el dependiente
    ya lo ve como estado real sin overlay).
    """
    dependientes = DocumentoCambio.query.filter_by(depende_de_id=documento.id).all()
    for dep in dependientes:
        estado, motivos = comprobar_factibilidad(dep)
        dep.factibilidad_estado = estado
        dep.factibilidad_motivos = "\n".join(motivos) if motivos else None
    if dependientes:
        db.session.flush()


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
    _recalcular_factibilidad_dependientes(documento)

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

    _recalcular_factibilidad_dependientes(documento)

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

    _recalcular_factibilidad_dependientes(documento)

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
