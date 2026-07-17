import calendar
import io
from datetime import date, datetime

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user, login_required
from sqlalchemy import and_, or_

from app.models import DocumentoCambio, FranjaHoraria, ParticipanteDocumentoCambio, Unidad, Usuario
from app.extensions import db
from app.services.documento_cambio import (
    crear_documento_cambio, firmar_documento, generar_notas_ilog, generar_pdf_documento,
    autorizar_documento, denegar_documento, anular_documento, puede_anularse,
)
from app.services.registro import crear_franjas_default

bp = Blueprint("documento_cambio", __name__, url_prefix="/documentos-cambio")

# Decisiones de la supervisora que tienen sentido como filtro: los cambios
# `pendiente_firmas` ni siquiera se ofrecen, no han "llegado" todavía a la
# supervisora (nadie ha completado las dos firmas).
_ESTADOS_DECISION_FILTRO = ("pendiente", "autorizado", "denegado")
_FACTIBILIDAD_FILTRO = ("factible", "no_factible", "no_verificado")


def _companeros_disponibles():
    return (
        Usuario.query
        .join(Unidad, Usuario.unidad_id == Unidad.id)
        .filter(
            Usuario.id != current_user.id,
            Usuario.categoria_id == current_user.categoria_id,
            Unidad.grupo_intercambio_id == current_user.grupo_intercambio.id,
        )
        .order_by(Usuario.nombre)
        .all()
    )


def _franjas_disponibles():
    return (
        FranjaHoraria.query
        .filter_by(grupo_intercambio_id=current_user.grupo_intercambio.id)
        .order_by(FranjaHoraria.hora_inicio)
        .all()
    )


def _get_documento_validado(documento_id):
    """Devuelve el documento o aborta 403/404. Puede verlo quien es alguno
    de sus participantes (quien lo creó siempre es uno de ellos), o una
    supervisora del mismo grupo de intercambio que alguno de ellos."""
    documento = db.get_or_404(DocumentoCambio, documento_id)
    ids_participantes = {p.usuario_id for p in documento.participantes}
    if current_user.id in ids_participantes:
        return documento
    if current_user.es_supervisora:
        grupos_documento = {p.usuario.grupo_intercambio.id for p in documento.participantes}
        if current_user.grupo_intercambio.id in grupos_documento:
            return documento
    abort(403)


@bp.get("/")
@login_required
def lista():
    documentos = (
        DocumentoCambio.query
        .join(ParticipanteDocumentoCambio, ParticipanteDocumentoCambio.documento_id == DocumentoCambio.id)
        .filter(ParticipanteDocumentoCambio.usuario_id == current_user.id)
        .order_by(DocumentoCambio.id.desc())
        .all()
    )
    return render_template("documento_cambio/lista.html", documentos=documentos)


def _usuarios_del_grupo(grupo_id):
    return (
        Usuario.query
        .join(Unidad, Usuario.unidad_id == Unidad.id)
        .filter(Unidad.grupo_intercambio_id == grupo_id)
        .order_by(Usuario.nombre)
        .all()
    )


def _subquery_ids_por_usuario_del_grupo(grupo_id):
    return (
        db.session.query(ParticipanteDocumentoCambio.documento_id)
        .join(Usuario, ParticipanteDocumentoCambio.usuario_id == Usuario.id)
        .join(Unidad, Usuario.unidad_id == Unidad.id)
        .filter(Unidad.grupo_intercambio_id == grupo_id)
    )


def _subquery_ids_por_usuario(usuario_id):
    return db.session.query(ParticipanteDocumentoCambio.documento_id).filter(
        ParticipanteDocumentoCambio.usuario_id == usuario_id
    )


def _subquery_ids_por_fecha_y_franja(rango_inicio, rango_fin, franja_id=None):
    """IDs de documentos con al menos un participante cuyo turno cedido o
    recibido cae dentro de [rango_inicio, rango_fin] -- y, si se indica
    franja_id, que además sea justo esa franja (día+turno identifican un
    turno concreto, no dos filtros independientes)."""
    if franja_id:
        condicion = or_(
            and_(
                ParticipanteDocumentoCambio.turno_cede_fecha >= rango_inicio,
                ParticipanteDocumentoCambio.turno_cede_fecha <= rango_fin,
                ParticipanteDocumentoCambio.turno_cede_franja_id == franja_id,
            ),
            and_(
                ParticipanteDocumentoCambio.turno_recibe_fecha >= rango_inicio,
                ParticipanteDocumentoCambio.turno_recibe_fecha <= rango_fin,
                ParticipanteDocumentoCambio.turno_recibe_franja_id == franja_id,
            ),
        )
    else:
        condicion = or_(
            and_(
                ParticipanteDocumentoCambio.turno_cede_fecha >= rango_inicio,
                ParticipanteDocumentoCambio.turno_cede_fecha <= rango_fin,
            ),
            and_(
                ParticipanteDocumentoCambio.turno_recibe_fecha >= rango_inicio,
                ParticipanteDocumentoCambio.turno_recibe_fecha <= rango_fin,
            ),
        )
    return db.session.query(ParticipanteDocumentoCambio.documento_id).filter(condicion)


def _filtros_supervisora_desde_request():
    """Filtros de la tabla de cambios a partir de la query string. mes/año
    por defecto al mes en curso."""
    hoy = date.today()
    return {
        "anyo": request.args.get("anyo", type=int) or hoy.year,
        "mes": request.args.get("mes", type=int) or hoy.month,
        "fecha": request.args.get("fecha", "").strip(),
        "trabajador1_id": request.args.get("trabajador1_id", type=int),
        "trabajador2_id": request.args.get("trabajador2_id", type=int),
        "franja_id": request.args.get("franja_id", type=int),
        "estado_decision": request.args.get("estado_decision", "").strip(),
        "factibilidad": request.args.get("factibilidad", "").strip(),
        "numero": request.args.get("numero", type=int),
    }


def _documentos_del_grupo_supervisora(filtros):
    """Hojas de cambio completas (dos firmas) del grupo de intercambio de la
    supervisora, aplicando los filtros dados. Los cambios `pendiente_firmas`
    quedan siempre fuera: todavía no le han llegado a la supervisora."""
    grupo_id = current_user.grupo_intercambio.id
    query = DocumentoCambio.query.filter(
        DocumentoCambio.estado == "completo",
        DocumentoCambio.id.in_(_subquery_ids_por_usuario_del_grupo(grupo_id)),
    )

    fecha = None
    if filtros["fecha"]:
        try:
            fecha = date.fromisoformat(filtros["fecha"])
        except ValueError:
            fecha = None

    if fecha:
        rango_inicio = rango_fin = fecha
    else:
        _, ultimo_dia = calendar.monthrange(filtros["anyo"], filtros["mes"])
        rango_inicio = date(filtros["anyo"], filtros["mes"], 1)
        rango_fin = date(filtros["anyo"], filtros["mes"], ultimo_dia)

    query = query.filter(DocumentoCambio.id.in_(
        _subquery_ids_por_fecha_y_franja(rango_inicio, rango_fin, filtros["franja_id"])
    ))

    if filtros["trabajador1_id"]:
        query = query.filter(DocumentoCambio.id.in_(_subquery_ids_por_usuario(filtros["trabajador1_id"])))
    if filtros["trabajador2_id"]:
        query = query.filter(DocumentoCambio.id.in_(_subquery_ids_por_usuario(filtros["trabajador2_id"])))
    if filtros["estado_decision"] == "anulado":
        query = query.filter(DocumentoCambio.anulado.is_(True))
    elif filtros["estado_decision"] in _ESTADOS_DECISION_FILTRO:
        query = query.filter(
            DocumentoCambio.decision_supervisora == filtros["estado_decision"],
            DocumentoCambio.anulado.is_(False),
        )
    if filtros["factibilidad"] in _FACTIBILIDAD_FILTRO:
        query = query.filter(DocumentoCambio.factibilidad_estado == filtros["factibilidad"])
    if filtros["numero"]:
        query = query.filter(DocumentoCambio.numero_unidad == filtros["numero"])

    return query.order_by(DocumentoCambio.id.desc()).all()


@bp.get("/supervisora")
@login_required
def supervisora():
    if not current_user.es_supervisora:
        abort(403)
    grupo_id = current_user.grupo_intercambio.id
    filtros = _filtros_supervisora_desde_request()
    documentos = _documentos_del_grupo_supervisora(filtros)
    return render_template(
        "documento_cambio/supervisora.html",
        documentos=documentos, filtros=filtros,
        trabajadores=_usuarios_del_grupo(grupo_id),
        franjas=_franjas_disponibles(),
    )


@bp.route("/nuevo", methods=["GET", "POST"])
@login_required
def nueva():
    grupo = current_user.grupo_intercambio
    crear_franjas_default(grupo)
    db.session.commit()

    companeros = _companeros_disponibles()
    franjas = _franjas_disponibles()
    hoy = date.today()

    if request.method == "POST":
        companero_id = request.form.get("companero_id", type=int)
        cede_fecha_str = request.form.get("turno_cede_fecha", "")
        cede_franja_id = request.form.get("turno_cede_franja_id", type=int)
        recibe_fecha_str = request.form.get("turno_recibe_fecha", "")
        recibe_franja_id = request.form.get("turno_recibe_franja_id", type=int)

        companero = next((c for c in companeros if c.id == companero_id), None)
        franja_ids_validas = {f.id for f in franjas}

        error = None
        try:
            cede_fecha = datetime.strptime(cede_fecha_str, "%Y-%m-%d").date()
            recibe_fecha = datetime.strptime(recibe_fecha_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            error = _("Fechas incorrectas.")
            cede_fecha = recibe_fecha = None

        if not error and companero is None:
            error = _("Selecciona un compañero válido.")
        if not error and (cede_franja_id not in franja_ids_validas or recibe_franja_id not in franja_ids_validas):
            error = _("Selecciona un turno válido.")

        if error:
            flash(error, "danger")
            return render_template(
                "documento_cambio/nuevo.html", companeros=companeros,
                franjas=franjas, today=hoy.isoformat(),
            )

        documento = crear_documento_cambio(
            creado_por=current_user, companero=companero,
            turno_cede_fecha=cede_fecha, turno_cede_franja_id=cede_franja_id,
            turno_recibe_fecha=recibe_fecha, turno_recibe_franja_id=recibe_franja_id,
        )
        flash(_("Hoja de cambio creada. Ahora recoge las dos firmas."), "success")
        return redirect(url_for("documento_cambio.ver", documento_id=documento.id))

    return render_template(
        "documento_cambio/nuevo.html", companeros=companeros,
        franjas=franjas, today=hoy.isoformat(),
    )


@bp.get("/<int:documento_id>")
@login_required
def ver(documento_id):
    documento = _get_documento_validado(documento_id)
    ids_firmantes = {f.usuario_id for f in documento.firmas}
    mi_participante = next(
        (p for p in documento.participantes if p.usuario_id == current_user.id), None
    )
    puedo_firmar = mi_participante is not None and mi_participante.usuario_id not in ids_firmantes
    notas_ilog = (
        generar_notas_ilog(documento)
        if documento.estado == "completo" and current_user.es_supervisora
        else []
    )
    puede_anular, motivo_no_anulable = (
        puede_anularse(documento) if current_user.es_supervisora else (False, None)
    )
    return render_template(
        "documento_cambio/ver.html", documento=documento,
        ids_firmantes=ids_firmantes, mi_participante=mi_participante, puedo_firmar=puedo_firmar,
        notas_ilog=notas_ilog,
        puede_anular=puede_anular, motivo_no_anulable=motivo_no_anulable,
    )


@bp.post("/<int:documento_id>/firmar/<int:participante_id>")
@login_required
def firmar(documento_id, participante_id):
    documento = _get_documento_validado(documento_id)
    participante = next(
        (p for p in documento.participantes if p.id == participante_id), None
    )
    if participante is None:
        abort(404)
    if participante.usuario_id != current_user.id:
        # Firma cruzada entre cuentas reales: cada uno firma su propia
        # parte, nadie puede firmar en nombre de otro.
        abort(403)
    if participante.usuario_id in {f.usuario_id for f in documento.firmas}:
        abort(409)

    imagen_firma = request.form.get("imagen_firma", "")
    if not imagen_firma.startswith("data:image/"):
        flash(_("Falta la firma. Dibújala en el recuadro antes de guardar."), "danger")
        return redirect(url_for("documento_cambio.ver", documento_id=documento.id))

    firmar_documento(documento, participante.usuario, imagen_firma)

    if request.form.get("guardar_firma") and not current_user.firma_guardada:
        current_user.firma_guardada = imagen_firma
        db.session.commit()

    flash(_("Firma guardada."), "success")
    return redirect(url_for("documento_cambio.ver", documento_id=documento.id))


@bp.get("/<int:documento_id>/pdf")
@login_required
def pdf(documento_id):
    documento = _get_documento_validado(documento_id)
    if documento.estado != "completo":
        abort(409)

    pdf_bytes = generar_pdf_documento(documento)
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=hoja-cambio-{documento.id}.pdf"},
    )


def _get_documento_para_decision(documento_id):
    """Devuelve el documento o aborta 403/404/409, para las acciones de
    autorizar/denegar: solo una supervisora del grupo, solo si está
    completo, solo si todavía no se ha decidido."""
    documento = _get_documento_validado(documento_id)
    if not current_user.es_supervisora:
        abort(403)
    if documento.estado != "completo":
        abort(409)
    if documento.decision_supervisora != "pendiente":
        abort(409)
    return documento


@bp.post("/<int:documento_id>/autorizar")
@login_required
def autorizar(documento_id):
    documento = _get_documento_para_decision(documento_id)
    autorizar_documento(documento, current_user)
    flash(_("Cambio autorizado y aplicado a las planillas."), "success")
    return redirect(url_for("documento_cambio.ver", documento_id=documento.id))


@bp.post("/<int:documento_id>/denegar")
@login_required
def denegar(documento_id):
    documento = _get_documento_para_decision(documento_id)
    motivo = request.form.get("motivo", "").strip()
    if not motivo:
        flash(_("Indica el motivo de la denegación."), "danger")
        return redirect(url_for("documento_cambio.ver", documento_id=documento.id))
    denegar_documento(documento, current_user, motivo=motivo)
    flash(_("Cambio denegado."), "info")
    return redirect(url_for("documento_cambio.ver", documento_id=documento.id))


def _get_documento_para_anular(documento_id):
    """Devuelve (documento, None) o (None, motivo_de_error): solo una
    supervisora del grupo, y solo si `puede_anularse` lo permite."""
    documento = _get_documento_validado(documento_id)
    if not current_user.es_supervisora:
        abort(403)
    ok, motivo = puede_anularse(documento)
    if not ok:
        return None, motivo
    return documento, None


@bp.post("/<int:documento_id>/anular")
@login_required
def anular(documento_id):
    documento, error = _get_documento_para_anular(documento_id)
    if error:
        flash(error, "danger")
        return redirect(url_for("documento_cambio.ver", documento_id=documento_id))

    motivo = request.form.get("motivo", "").strip()
    if not motivo:
        flash(_("Indica el motivo de la anulación."), "danger")
        return redirect(url_for("documento_cambio.ver", documento_id=documento.id))

    anular_documento(documento, current_user, motivo=motivo)
    flash(_("Cambio anulado."), "info")
    return redirect(url_for("documento_cambio.ver", documento_id=documento.id))


# ─── Selección en bloque desde la tabla de supervisión ─────────────────────

_CAMPOS_FILTRO_BLOQUE = (
    "anyo", "mes", "fecha", "trabajador1_id", "trabajador2_id",
    "franja_id", "estado_decision", "factibilidad", "numero",
)


def _redirect_a_supervisora_con_filtros():
    args = {campo: request.form.get(campo, "").strip() for campo in _CAMPOS_FILTRO_BLOQUE}
    args = {k: v for k, v in args.items() if v}
    return redirect(url_for("documento_cambio.supervisora", **args))


def _documentos_seleccionados():
    """Documentos de los ids marcados en el formulario que de verdad
    pertenecen al grupo de la supervisora -- nunca se confía en los ids tal
    cual vienen del cliente."""
    ids = request.form.getlist("documento_ids", type=int)
    if not ids:
        return []
    grupo_id = current_user.grupo_intercambio.id
    return (
        DocumentoCambio.query
        .filter(
            DocumentoCambio.id.in_(ids),
            DocumentoCambio.id.in_(_subquery_ids_por_usuario_del_grupo(grupo_id)),
        )
        .all()
    )


@bp.post("/supervisora/bloque/pdf")
@login_required
def bloque_pdf():
    if not current_user.es_supervisora:
        abort(403)
    documentos = _documentos_seleccionados()
    elegibles = [d for d in documentos if d.estado == "completo"]

    if not elegibles:
        flash(_("Ningún cambio seleccionado tiene el PDF disponible (deben estar completos)."), "danger")
        return _redirect_a_supervisora_con_filtros()

    from pypdf import PdfWriter

    writer = PdfWriter()
    for documento in elegibles:
        writer.append(io.BytesIO(generar_pdf_documento(documento)))
    buffer = io.BytesIO()
    writer.write(buffer)
    buffer.seek(0)

    return Response(
        buffer.read(), mimetype="application/pdf",
        headers={"Content-Disposition": "attachment; filename=hojas-cambio.pdf"},
    )


@bp.post("/supervisora/bloque/aceptar")
@login_required
def bloque_aceptar():
    if not current_user.es_supervisora:
        abort(403)
    documentos = _documentos_seleccionados()

    aplicados = 0
    for documento in documentos:
        if documento.estado == "completo" and documento.decision_supervisora == "pendiente":
            autorizar_documento(documento, current_user)
            aplicados += 1

    omitidos = len(documentos) - aplicados
    flash(
        _("%(aplicados)s aceptados. %(omitidos)s omitidos (no estaban pendientes de decisión).",
          aplicados=aplicados, omitidos=omitidos),
        "success" if aplicados else "info",
    )
    return _redirect_a_supervisora_con_filtros()


@bp.post("/supervisora/bloque/denegar")
@login_required
def bloque_denegar():
    if not current_user.es_supervisora:
        abort(403)
    motivo = request.form.get("motivo", "").strip()
    if not motivo:
        flash(_("Indica el motivo para denegar en bloque."), "danger")
        return _redirect_a_supervisora_con_filtros()

    documentos = _documentos_seleccionados()
    aplicados = 0
    for documento in documentos:
        if documento.estado == "completo" and documento.decision_supervisora == "pendiente":
            denegar_documento(documento, current_user, motivo=motivo)
            aplicados += 1

    omitidos = len(documentos) - aplicados
    flash(
        _("%(aplicados)s denegados. %(omitidos)s omitidos (no estaban pendientes de decisión).",
          aplicados=aplicados, omitidos=omitidos),
        "success" if aplicados else "info",
    )
    return _redirect_a_supervisora_con_filtros()


@bp.post("/supervisora/bloque/anular")
@login_required
def bloque_anular():
    if not current_user.es_supervisora:
        abort(403)
    motivo = request.form.get("motivo", "").strip()
    if not motivo:
        flash(_("Indica el motivo para anular en bloque."), "danger")
        return _redirect_a_supervisora_con_filtros()

    documentos = _documentos_seleccionados()
    aplicados = 0
    for documento in documentos:
        ok, _motivo_rechazo = puede_anularse(documento)
        if ok:
            anular_documento(documento, current_user, motivo=motivo)
            aplicados += 1

    omitidos = len(documentos) - aplicados
    flash(
        _("%(aplicados)s anulados. %(omitidos)s omitidos (no se podían anular).",
          aplicados=aplicados, omitidos=omitidos),
        "success" if aplicados else "info",
    )
    return _redirect_a_supervisora_con_filtros()
