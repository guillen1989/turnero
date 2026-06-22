from datetime import date, datetime, time as dtime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user, login_required

from app.extensions import db
from app.models import FranjaHoraria, GrupoIntercambio, PublicacionCambio, TurnoCedido, TurnoAceptado, Usuario
from app.services.publicaciones import cancelar_publicacion, editar_publicacion, eliminar_publicacion, publicar_cambio
from app.services.registro import crear_franjas_default
from app.matching.service import buscar_matches_para, crear_match_directo

bp = Blueprint("publicaciones", __name__)

_CADENCIA_DIAS = {
    'LMVD': [0, 2, 4, 6],  # Lun, Mié, Vie, Dom
    'MJS':  [1, 3, 5],     # Mar, Jue, Sáb
}


def _extraer_turnos_junte():
    """
    Procesa el formulario de junte de noches.
    Devuelve (cedidos, aceptados, error_msg). error_msg es None si todo va bien.
    """
    semana_str = request.form.get('junte_semana',   '').strip()
    cadencia   = request.form.get('junte_cadencia', '').strip()
    noches_raw = request.form.getlist('junte_noches')

    if not semana_str:
        return [], [], _('Indica la semana del junte.')
    if cadencia not in _CADENCIA_DIAS:
        return [], [], _('Selecciona tu cadencia de noches.')

    franja_noche = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=current_user.unidad.grupo_intercambio_id,
        nombre='Noche',
    ).first()
    if not franja_noche:
        return [], [], _('No hay turno nocturno configurado para tu unidad.')
    franja_id = franja_noche.id

    try:
        dia_ref     = datetime.strptime(semana_str, '%Y-%m-%d').date()
        noches_post = {int(n) for n in noches_raw if n.isdigit() and 0 <= int(n) <= 6}
    except (ValueError, TypeError):
        return [], [], _('Datos del junte incorrectos.')

    lunes = dia_ref - timedelta(days=dia_ref.weekday())
    hoy = date.today()
    lunes_actual = hoy - timedelta(days=hoy.weekday())
    if lunes < lunes_actual:
        return [], [], _('La semana del junte no puede ser anterior a la semana actual.')

    dias_cadencia = set(_CADENCIA_DIAS[cadencia])
    dias_partner  = set(range(7)) - dias_cadencia

    if len(noches_post) != len(dias_cadencia):
        return [], [], _('Debes seleccionar exactamente %(n)s noches.', n=len(dias_cadencia))

    cedidos   = [(lunes + timedelta(days=d), franja_id) for d in sorted(dias_cadencia - noches_post)]
    aceptados = [(lunes + timedelta(days=d), franja_id) for d in sorted(dias_partner  & noches_post)]

    if not cedidos:
        return [], [], _('Debes seleccionar noches diferentes a las que ya tienes.')
    if not aceptados:
        return [], [], _('Debes incluir al menos una noche de la otra cadencia.')

    return cedidos, aceptados, None


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
        if tipo not in ("cambio", "regalo", "peticion", "junte"):
            tipo = "cambio"

        hoy = date.today()

        if tipo == "junte":
            cedidos, aceptados, error = _extraer_turnos_junte()
            if error:
                flash(error, "danger")
                return render_template("publicaciones/publicar.html", franjas=franjas, today=hoy.isoformat())
        else:
            cedidos  = _extraer_turnos("cedida")
            aceptados = _extraer_turnos("aceptada")

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

        if tipo != "junte":
            todas_fechas = cedidos + aceptados
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


@bp.post("/cambios/<int:pub_id>/me-interesa")
@login_required
def me_interesa(pub_id):
    pub_a = db.get_or_404(PublicacionCambio, pub_id)

    if pub_a.usuario_id == current_user.id:
        flash(_("No puedes aceptar tu propia publicación."), "warning")
        return redirect(url_for("main.cambios"))

    if pub_a.estado not in ("abierta", "parcialmente_resuelta"):
        flash(_("Esta publicación ya no está activa."), "warning")
        return redirect(url_for("main.cambios"))

    autor = db.session.get(Usuario, pub_a.usuario_id)
    if (autor.categoria_id != current_user.categoria_id or
            autor.unidad.grupo_intercambio_id != current_user.unidad.grupo_intercambio_id):
        abort(403)

    try:
        pub_b = _crear_publicacion_espejo(pub_a)
    except ValueError as exc:
        flash(str(exc), "warning")
        return redirect(url_for("main.cambios"))

    match = crear_match_directo(pub_a, pub_b)
    if match is None:
        eliminar_publicacion(pub_b)
        flash(_("No fue posible crear el match. Los turnos pueden haber cambiado."), "warning")
        return redirect(url_for("main.cambios"))

    flash(_("¡Match creado! Ve a «Mis cambios» para confirmar."), "success")
    return redirect(url_for("main.index"))


def _crear_publicacion_espejo(pub_a):
    """Crea la publicación de current_user que encaja con pub_a y lanza el match."""
    tipo = pub_a.tipo

    if tipo == "regalo":
        ta_id = request.form.get("turno_aceptado_id", type=int)
        if not ta_id:
            raise ValueError(_("Selecciona el turno que te interesa."))
        ta = TurnoAceptado.query.filter_by(id=ta_id, publicacion_id=pub_a.id).first()
        if ta is None:
            raise ValueError(_("Turno no encontrado en esta publicación."))
        if ta.cualquier_franja:
            franja_b = request.form.get("franja_b", type=int)
            if not franja_b:
                raise ValueError(_("Especifica el turno que quieres librar."))
            cedidos = [(ta.fecha, franja_b)]
        else:
            cedidos = [(ta.fecha, ta.franja_horaria_id)]
        return publicar_cambio(current_user.id, cedidos, [], tipo="peticion")

    if tipo == "peticion":
        tc_id = request.form.get("turno_cedido_id", type=int)
        if not tc_id:
            raise ValueError(_("Selecciona el turno que quieres cubrir."))
        tc = TurnoCedido.query.filter_by(id=tc_id, publicacion_id=pub_a.id, estado="abierto").first()
        if tc is None:
            raise ValueError(_("Turno no encontrado o ya resuelto."))
        return publicar_cambio(current_user.id, [], [(tc.fecha, tc.franja_horaria_id)], tipo="regalo")

    if tipo == "junte":
        cedidos_b = [(ta.fecha, ta.franja_horaria_id) for ta in pub_a.turnos_aceptados]
        aceptados_b = [(tc.fecha, tc.franja_horaria_id) for tc in pub_a.turnos_cedidos if tc.estado == "abierto"]
        if not cedidos_b or not aceptados_b:
            raise ValueError(_("El junte ya no tiene turnos disponibles."))
        return publicar_cambio(current_user.id, cedidos_b, aceptados_b, tipo="junte")

    if tipo == "cambio":
        tc_id = request.form.get("turno_cedido_id", type=int)
        ta_id = request.form.get("turno_aceptado_id", type=int)
        if not tc_id or not ta_id:
            raise ValueError(_("Selecciona los dos turnos."))
        tc = TurnoCedido.query.filter_by(id=tc_id, publicacion_id=pub_a.id, estado="abierto").first()
        ta = TurnoAceptado.query.filter_by(id=ta_id, publicacion_id=pub_a.id).first()
        if tc is None or ta is None:
            raise ValueError(_("Turnos no encontrados en esta publicación."))
        if ta.cualquier_franja:
            franja_b = request.form.get("franja_b", type=int)
            if not franja_b:
                raise ValueError(_("Especifica el turno que quieres librar."))
            cedidos_b = [(ta.fecha, franja_b)]
        else:
            cedidos_b = [(ta.fecha, ta.franja_horaria_id)]
        aceptados_b = [(tc.fecha, tc.franja_horaria_id)]
        return publicar_cambio(current_user.id, cedidos_b, aceptados_b, tipo="cambio")

    raise ValueError(_("Tipo de publicación no reconocido."))
