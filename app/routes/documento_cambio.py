from datetime import date, datetime

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user, login_required

from app.models import DocumentoCambio, FranjaHoraria, ParticipanteDocumentoCambio, Unidad, Usuario
from app.extensions import db
from app.services.documento_cambio import (
    crear_documento_cambio, firmar_documento, generar_notas_ilog, generar_pdf_documento,
    autorizar_documento, denegar_documento,
)
from app.services.registro import crear_franjas_default

bp = Blueprint("documento_cambio", __name__, url_prefix="/documentos-cambio")


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


def _documentos_del_grupo_supervisora():
    grupo_id = current_user.grupo_intercambio.id
    return (
        DocumentoCambio.query
        .join(ParticipanteDocumentoCambio, ParticipanteDocumentoCambio.documento_id == DocumentoCambio.id)
        .join(Usuario, ParticipanteDocumentoCambio.usuario_id == Usuario.id)
        .join(Unidad, Usuario.unidad_id == Unidad.id)
        .filter(Unidad.grupo_intercambio_id == grupo_id)
        .distinct()
        .order_by(DocumentoCambio.id.desc())
        .all()
    )


@bp.get("/supervisora")
@login_required
def supervisora():
    if not current_user.es_supervisora:
        abort(403)
    documentos = _documentos_del_grupo_supervisora()
    return render_template("documento_cambio/supervisora.html", documentos=documentos)


@bp.get("/supervisora/tabla")
@login_required
def supervisora_tabla():
    """Misma información que `supervisora`, en formato tabla (una fila por
    hoja de cambio) pensado para pantallas de ordenador. Vista alternativa
    mientras se decide cuál sustituye a la otra -- no se ha retirado
    `supervisora.html`."""
    if not current_user.es_supervisora:
        abort(403)
    documentos = _documentos_del_grupo_supervisora()
    return render_template("documento_cambio/supervisora_tabla.html", documentos=documentos)


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
    return render_template(
        "documento_cambio/ver.html", documento=documento,
        ids_firmantes=ids_firmantes, mi_participante=mi_participante, puedo_firmar=puedo_firmar,
        notas_ilog=notas_ilog,
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
