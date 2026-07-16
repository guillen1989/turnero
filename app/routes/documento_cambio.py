from datetime import date, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user, login_required

from app.models import DocumentoCambio, FranjaHoraria, Unidad, Usuario
from app.extensions import db
from app.services.documento_cambio import crear_documento_cambio, firmar_documento, generar_notas_ilog
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
    """Devuelve el documento o aborta 403/404. Fase mono-cuenta: solo quien
    lo creó puede verlo/firmarlo, ya que las dos firmas se recogen desde su
    mismo dispositivo."""
    documento = db.get_or_404(DocumentoCambio, documento_id)
    if documento.creado_por_id != current_user.id:
        abort(403)
    return documento


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
    siguiente_participante = next(
        (p for p in documento.participantes if p.usuario_id not in ids_firmantes), None
    )
    notas_ilog = generar_notas_ilog(documento) if documento.estado == "completo" else []
    return render_template(
        "documento_cambio/ver.html", documento=documento,
        ids_firmantes=ids_firmantes, siguiente_participante=siguiente_participante,
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
    if participante.usuario_id in {f.usuario_id for f in documento.firmas}:
        abort(409)

    imagen_firma = request.form.get("imagen_firma", "")
    if not imagen_firma.startswith("data:image/"):
        flash(_("Falta la firma. Dibújala en el recuadro antes de guardar."), "danger")
        return redirect(url_for("documento_cambio.ver", documento_id=documento.id))

    firmar_documento(documento, participante.usuario, imagen_firma)
    flash(_("Firma guardada."), "success")
    return redirect(url_for("documento_cambio.ver", documento_id=documento.id))
