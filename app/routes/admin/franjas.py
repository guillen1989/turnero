from flask import abort, flash, redirect, render_template, request, url_for
from flask_babel import _

from app.extensions import db
from app.forms.admin import AdminFranjaForm
from app.models import FranjaHoraria, GrupoIntercambio
from app.routes.admin import admin_required, bp
from app.services.registro import asignar_color_franja


def _choices_grupos():
    grupos = GrupoIntercambio.query.all()
    choices = []
    for g in grupos:
        unidades = g.unidades.all()
        label = ", ".join(u.nombre for u in unidades[:3]) if unidades else f"Grupo {g.id}"
        if len(unidades) > 3:
            label += f" (+{len(unidades) - 3})"
        choices.append((g.id, label))
    return choices


@bp.route("/franjas")
@admin_required
def franjas():
    form = AdminFranjaForm(prefix="nuevo")
    form.grupo_intercambio_id.choices = _choices_grupos()
    grupos = GrupoIntercambio.query.all()
    grupos_data = []
    for g in grupos:
        unidades = g.unidades.all()
        label = ", ".join(u.nombre for u in unidades) if unidades else f"Grupo {g.id}"
        franjas_g = g.franjas_horarias.order_by(FranjaHoraria.hora_inicio).all()
        grupos_data.append({"grupo": g, "label": label, "franjas": franjas_g})
    return render_template("admin/franjas.html", grupos_data=grupos_data, form=form)


@bp.route("/franjas/nueva", methods=["POST"])
@admin_required
def franja_nueva():
    form = AdminFranjaForm(prefix="nuevo")
    form.grupo_intercambio_id.choices = _choices_grupos()
    if form.validate_on_submit():
        existe = FranjaHoraria.query.filter_by(
            nombre=form.nombre.data.strip(),
            grupo_intercambio_id=form.grupo_intercambio_id.data,
        ).first()
        if existe:
            flash(_("Ya existe un turno con ese nombre en ese grupo."), "danger")
        else:
            nombre_f = form.nombre.data.strip()
            grupo_id_f = form.grupo_intercambio_id.data
            db.session.add(FranjaHoraria(
                nombre=nombre_f,
                hora_inicio=form.hora_inicio.data,
                hora_fin=form.hora_fin.data,
                grupo_intercambio_id=grupo_id_f,
                color=asignar_color_franja(nombre_f, grupo_id_f),
            ))
            db.session.commit()
            flash(_("Turno creado."), "success")
    return redirect(url_for("admin.franjas"))


@bp.route("/franjas/<int:id>/editar", methods=["GET", "POST"])
@admin_required
def franja_editar(id):
    f = db.session.get(FranjaHoraria, id) or abort(404)
    form = AdminFranjaForm(obj=f)
    form.grupo_intercambio_id.choices = _choices_grupos()
    if form.validate_on_submit():
        existe = FranjaHoraria.query.filter(
            FranjaHoraria.nombre == form.nombre.data.strip(),
            FranjaHoraria.grupo_intercambio_id == form.grupo_intercambio_id.data,
            FranjaHoraria.id != id,
        ).first()
        if existe:
            flash(_("Ya existe un turno con ese nombre en ese grupo."), "danger")
        else:
            f.nombre = form.nombre.data.strip()
            f.hora_inicio = form.hora_inicio.data
            f.hora_fin = form.hora_fin.data
            f.grupo_intercambio_id = form.grupo_intercambio_id.data
            db.session.commit()
            flash(_("Turno actualizado."), "success")
            return redirect(url_for("admin.franjas"))
    elif request.method == "GET":
        form.grupo_intercambio_id.data = f.grupo_intercambio_id
    return render_template("admin/franja_form.html", form=form, franja=f, titulo=_("Editar turno"))


@bp.route("/franjas/<int:id>/eliminar", methods=["POST"])
@admin_required
def franja_eliminar(id):
    f = db.session.get(FranjaHoraria, id) or abort(404)
    db.session.delete(f)
    db.session.commit()
    flash(_("Turno eliminado."), "success")
    return redirect(url_for("admin.franjas"))
