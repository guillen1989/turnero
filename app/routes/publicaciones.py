from datetime import date, datetime, time as dtime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user, login_required

from app.extensions import db
from app.models import FranjaHoraria, GrupoIntercambio, PublicacionCambio
from app.services.publicaciones import cancelar_publicacion, editar_publicacion, eliminar_publicacion, publicar_cambio
from app.services.registro import crear_franjas_default
from app.matching.service import buscar_matches_para, crear_match_directo

bp = Blueprint("publicaciones", __name__)


def _extraer_turnos(prefix):
    """Extrae pares (fecha, franja_id) del form con claves fecha_{prefix}_N / franja_{prefix}_N.

    franja_id=None si el valor enviado es '0' (cualquier franja).
    """
    turnos = []
    idx = 0
    while True:
        fecha_str = request.form.get(f"fecha_{prefix}_{idx}", "").strip()
        franja_str = request.form.get(f"franja_{prefix}_{idx}", "").strip()
        if not fecha_str:
            break
        try:
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            if franja_str == "0":
                turnos.append((fecha, None))
            elif franja_str:
                turnos.append((fecha, int(franja_str)))
        except (ValueError, TypeError):
            pass
        idx += 1
    return turnos


def _asegurar_franjas(grupo_intercambio_id):
    """Añade al grupo cualquier franja por defecto que falte."""
    grupo = db.session.get(GrupoIntercambio, grupo_intercambio_id)
    crear_franjas_default(grupo)
    db.session.commit()


@bp.route("/publicar", methods=["GET", "POST"])
@login_required
def nueva():
    grupo_id = current_user.unidad.grupo_intercambio_id
    _asegurar_franjas(grupo_id)
    franjas = (
        FranjaHoraria.query
        .filter_by(grupo_intercambio_id=grupo_id)
        .order_by(FranjaHoraria.hora_inicio)
        .all()
    )

    if request.method == "POST" and request.form.get("accion") == "nueva_franja":
        nombre_f = request.form.get("franja_nombre", "").strip()[:50]
        inicio_str = request.form.get("franja_inicio", "")
        fin_str = request.form.get("franja_fin", "")
        try:
            inicio = dtime.fromisoformat(inicio_str)
            fin = dtime.fromisoformat(fin_str)
            if not nombre_f:
                raise ValueError("nombre vacío")
            existe = FranjaHoraria.query.filter_by(
                grupo_intercambio_id=grupo_id, nombre=nombre_f
            ).first()
            if not existe:
                db.session.add(FranjaHoraria(
                    nombre=nombre_f, hora_inicio=inicio, hora_fin=fin,
                    grupo_intercambio_id=grupo_id,
                ))
                db.session.commit()
                flash(_("Tipo de turno «%(n)s» creado.", n=nombre_f), "success")
            else:
                flash(_("Ya existe un turno con ese nombre."), "warning")
        except (ValueError, TypeError):
            flash(_("Datos del turno incorrectos."), "danger")
        franjas = (
            FranjaHoraria.query
            .filter_by(grupo_intercambio_id=grupo_id)
            .order_by(FranjaHoraria.hora_inicio)
            .all()
        )
        return render_template("publicaciones/publicar.html", franjas=franjas)

    if request.method == "POST":
        tipo = request.form.get("tipo", "cambio")
        if tipo not in ("cambio", "regalo", "peticion"):
            tipo = "cambio"

        cedidos = _extraer_turnos("cedida")
        aceptados = _extraer_turnos("aceptada")

        hoy = date.today()

        if tipo == "cambio":
            if not cedidos:
                flash(_("Debes indicar al menos un turno que cedes."), "danger")
                return render_template("publicaciones/publicar.html", franjas=franjas, today=hoy.isoformat())
            if not aceptados:
                flash(_("Debes indicar al menos un turno que aceptarías."), "danger")
                return render_template("publicaciones/publicar.html", franjas=franjas, today=hoy.isoformat())
        elif tipo == "regalo":
            if not aceptados:
                flash(_("Debes indicar al menos un turno que ofreces trabajar."), "danger")
                return render_template("publicaciones/publicar.html", franjas=franjas, today=hoy.isoformat())
        elif tipo == "peticion":
            if not cedidos:
                flash(_("Debes indicar al menos un turno que quieres librar."), "danger")
                return render_template("publicaciones/publicar.html", franjas=franjas, today=hoy.isoformat())

        todas_fechas = [(f, fid) for f, fid in cedidos + aceptados]
        if any(f < hoy for f, _ in todas_fechas):
            flash(_("Las fechas de los turnos no pueden ser anteriores a hoy."), "danger")
            return render_template("publicaciones/publicar.html", franjas=franjas, today=hoy.isoformat())

        mensaje = request.form.get("mensaje", "").strip()[:200] or None
        pub = publicar_cambio(current_user.id, cedidos, aceptados, mensaje=mensaje, tipo=tipo)
        for candidata in buscar_matches_para(pub):
            crear_match_directo(pub, candidata)
        flash(_("Publicación creada correctamente."), "success")
        return redirect(url_for("main.index"))

    return render_template("publicaciones/publicar.html", franjas=franjas, today=date.today().isoformat())


@bp.post("/publicaciones/<int:pub_id>/cancelar")
@login_required
def cancelar(pub_id):
    pub = db.get_or_404(PublicacionCambio, pub_id)
    if pub.usuario_id != current_user.id:
        abort(403)
    if not pub.esta_activa():
        abort(409)
    cancelar_publicacion(pub)
    flash(_("Publicación cancelada."), "info")
    return redirect(url_for("main.index"))


@bp.route("/publicaciones/<int:pub_id>/editar", methods=["GET", "POST"])
@login_required
def editar(pub_id):
    pub = db.get_or_404(PublicacionCambio, pub_id)
    if pub.usuario_id != current_user.id:
        abort(403)
    if not pub.esta_activa():
        flash(_("Solo puedes editar publicaciones activas."), "danger")
        return redirect(url_for("main.index"))

    grupo_id = current_user.unidad.grupo_intercambio_id
    _asegurar_franjas(grupo_id)
    franjas = (
        FranjaHoraria.query
        .filter_by(grupo_intercambio_id=grupo_id)
        .order_by(FranjaHoraria.hora_inicio)
        .all()
    )

    if request.method == "POST":
        tipo = request.form.get("tipo", pub.tipo)
        if tipo not in ("cambio", "regalo", "peticion"):
            tipo = pub.tipo

        cedidos = _extraer_turnos("cedida")
        aceptados = _extraer_turnos("aceptada")
        hoy = date.today()

        if tipo == "cambio":
            if not cedidos:
                flash(_("Debes indicar al menos un turno que cedes."), "danger")
                return render_template("publicaciones/editar.html", pub=pub, franjas=franjas, today=hoy.isoformat())
            if not aceptados:
                flash(_("Debes indicar al menos un turno que aceptarías."), "danger")
                return render_template("publicaciones/editar.html", pub=pub, franjas=franjas, today=hoy.isoformat())
        elif tipo == "regalo":
            if not aceptados:
                flash(_("Debes indicar al menos un turno que ofreces trabajar."), "danger")
                return render_template("publicaciones/editar.html", pub=pub, franjas=franjas, today=hoy.isoformat())
        elif tipo == "peticion":
            if not cedidos:
                flash(_("Debes indicar al menos un turno que quieres librar."), "danger")
                return render_template("publicaciones/editar.html", pub=pub, franjas=franjas, today=hoy.isoformat())

        if any(f < hoy for f, _ in cedidos + aceptados):
            flash(_("Las fechas de los turnos no pueden ser anteriores a hoy."), "danger")
            return render_template("publicaciones/editar.html", pub=pub, franjas=franjas, today=hoy.isoformat())

        mensaje = request.form.get("mensaje", "").strip()[:200] or None
        editar_publicacion(pub, cedidos, aceptados, mensaje=mensaje, tipo=tipo)
        for candidata in buscar_matches_para(pub):
            crear_match_directo(pub, candidata)
        flash(_("Publicación actualizada."), "success")
        return redirect(url_for("main.index"))

    return render_template("publicaciones/editar.html", pub=pub, franjas=franjas, today=date.today().isoformat())


@bp.post("/publicaciones/<int:pub_id>/eliminar")
@login_required
def eliminar(pub_id):
    pub = db.get_or_404(PublicacionCambio, pub_id)
    if pub.usuario_id != current_user.id:
        abort(403)
    eliminar_publicacion(pub)
    flash(_("Publicación eliminada."), "success")
    return redirect(url_for("main.index"))
