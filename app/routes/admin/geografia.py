from flask import abort, flash, redirect, render_template, request, url_for
from flask_babel import _

from app.extensions import db
from app.forms.admin import AdminCiudadForm, AdminHospitalForm, AdminNombreForm, AdminProvinciaForm, AdminUnidadForm
from app.models import (
    AuditEliminacion, Categoria, Ciudad, DocumentoCambio, EstadoDiaPlanilla, Hospital,
    MapeoTrabajadorPlanilla, NotaDia, Notificacion, Pais, PlanillaMes,
    Provincia, PublicacionCambio, SalienteDia, TurnoPlanilla, Unidad,
)
from app.routes.admin import admin_required, bp
from app.routes.admin.helpers import _choices_cats_unidad, _choices_ciudades, _choices_hospitales, _choices_paises, _choices_provincias
from app.services.registro import encontrar_o_crear_categoria, encontrar_o_crear_ciudad, encontrar_o_crear_hospital, encontrar_o_crear_pais, encontrar_o_crear_provincia, encontrar_o_crear_unidad

# ---------------------------------------------------------------------------
# Países
# ---------------------------------------------------------------------------

@bp.route("/paises", methods=["GET", "POST"])
@admin_required
def paises():
    form = AdminNombreForm(prefix="nuevo")
    if form.validate_on_submit():
        encontrar_o_crear_pais(form.nombre.data)
        db.session.commit()
        flash(_("País creado."), "success")
        return redirect(url_for("admin.paises"))
    todos = Pais.query.order_by(Pais.nombre).all()
    return render_template("admin/paises.html", paises=todos, form=form)


@bp.route("/paises/<int:id>/editar", methods=["GET", "POST"])
@admin_required
def pais_editar(id):
    p = db.session.get(Pais, id) or abort(404)
    form = AdminNombreForm(obj=p)
    if form.validate_on_submit():
        p.nombre = form.nombre.data.strip()
        db.session.commit()
        flash(_("País actualizado."), "success")
        return redirect(url_for("admin.paises"))
    return render_template("admin/nombre_form.html", form=form, titulo=_("Editar país"), volver=url_for("admin.paises"))


@bp.route("/paises/<int:id>/eliminar", methods=["POST"])
@admin_required
def pais_eliminar(id):
    p = db.session.get(Pais, id) or abort(404)
    if p.provincias.count() > 0:
        flash(_("No se puede eliminar: el país tiene provincias asociadas."), "danger")
        return redirect(url_for("admin.paises"))
    db.session.delete(p)
    db.session.commit()
    flash(_("País eliminado."), "success")
    return redirect(url_for("admin.paises"))


# ---------------------------------------------------------------------------
# Provincias
# ---------------------------------------------------------------------------

@bp.route("/provincias", methods=["GET", "POST"])
@admin_required
def provincias():
    form = AdminProvinciaForm(prefix="nuevo")
    form.pais_id.choices = _choices_paises()
    if form.validate_on_submit():
        pais = db.session.get(Pais, form.pais_id.data) or abort(400)
        encontrar_o_crear_provincia(form.nombre.data, pais)
        db.session.commit()
        flash(_("Provincia creada."), "success")
        return redirect(url_for("admin.provincias"))
    todas = Provincia.query.join(Pais).order_by(Pais.nombre, Provincia.nombre).all()
    return render_template("admin/provincias.html", provincias=todas, form=form)


@bp.route("/provincias/<int:id>/editar", methods=["GET", "POST"])
@admin_required
def provincia_editar(id):
    p = db.session.get(Provincia, id) or abort(404)
    form = AdminProvinciaForm(obj=p)
    form.pais_id.choices = _choices_paises()
    if form.validate_on_submit():
        p.nombre = form.nombre.data.strip()
        p.pais_id = form.pais_id.data
        db.session.commit()
        flash(_("Provincia actualizada."), "success")
        return redirect(url_for("admin.provincias"))
    elif request.method == "GET":
        form.pais_id.data = p.pais_id
    return render_template("admin/provincia_form.html", form=form, titulo=_("Editar provincia"))


@bp.route("/provincias/<int:id>/eliminar", methods=["POST"])
@admin_required
def provincia_eliminar(id):
    p = db.session.get(Provincia, id) or abort(404)
    if p.ciudades.count() > 0:
        flash(_("No se puede eliminar: la provincia tiene ciudades asociadas."), "danger")
        return redirect(url_for("admin.provincias"))
    db.session.delete(p)
    db.session.commit()
    flash(_("Provincia eliminada."), "success")
    return redirect(url_for("admin.provincias"))


# ---------------------------------------------------------------------------
# Ciudades
# ---------------------------------------------------------------------------

@bp.route("/ciudades", methods=["GET", "POST"])
@admin_required
def ciudades():
    form = AdminCiudadForm(prefix="nuevo")
    form.provincia_id.choices = _choices_provincias()
    if form.validate_on_submit():
        provincia = db.session.get(Provincia, form.provincia_id.data) or abort(400)
        encontrar_o_crear_ciudad(form.nombre.data, provincia)
        db.session.commit()
        flash(_("Ciudad creada."), "success")
        return redirect(url_for("admin.ciudades"))
    todas = Ciudad.query.join(Provincia).join(Pais).order_by(Pais.nombre, Provincia.nombre, Ciudad.nombre).all()
    return render_template("admin/ciudades.html", ciudades=todas, form=form)


@bp.route("/ciudades/<int:id>/editar", methods=["GET", "POST"])
@admin_required
def ciudad_editar(id):
    c = db.session.get(Ciudad, id) or abort(404)
    form = AdminCiudadForm(obj=c)
    form.provincia_id.choices = _choices_provincias()
    if form.validate_on_submit():
        c.nombre = form.nombre.data.strip()
        c.provincia_id = form.provincia_id.data
        db.session.commit()
        flash(_("Ciudad actualizada."), "success")
        return redirect(url_for("admin.ciudades"))
    elif request.method == "GET":
        form.provincia_id.data = c.provincia_id
    return render_template("admin/ciudad_form.html", form=form, titulo=_("Editar ciudad"))


@bp.route("/ciudades/<int:id>/eliminar", methods=["POST"])
@admin_required
def ciudad_eliminar(id):
    c = db.session.get(Ciudad, id) or abort(404)
    if c.hospitales.count() > 0:
        flash(_("No se puede eliminar: la ciudad tiene hospitales asociados."), "danger")
        return redirect(url_for("admin.ciudades"))
    db.session.delete(c)
    db.session.commit()
    flash(_("Ciudad eliminada."), "success")
    return redirect(url_for("admin.ciudades"))


# ---------------------------------------------------------------------------
# Hospitales
# ---------------------------------------------------------------------------

@bp.route("/hospitales", methods=["GET", "POST"])
@admin_required
def hospitales():
    form = AdminHospitalForm(prefix="nuevo")
    form.ciudad_id.choices = [(0, _("— Sin ciudad —"))] + _choices_ciudades()
    if form.validate_on_submit():
        ciudad_id = form.ciudad_id.data
        ciudad = db.session.get(Ciudad, ciudad_id) if ciudad_id else None
        encontrar_o_crear_hospital(form.nombre.data, ciudad)
        db.session.commit()
        flash(_("Hospital creado."), "success")
        return redirect(url_for("admin.hospitales"))
    todos = Hospital.query.order_by(Hospital.nombre).all()
    return render_template("admin/hospitales.html", hospitales=todos, form=form)


@bp.route("/hospitales/<int:id>/editar", methods=["GET", "POST"])
@admin_required
def hospital_editar(id):
    h = db.session.get(Hospital, id) or abort(404)
    form = AdminHospitalForm(obj=h)
    form.ciudad_id.choices = [(0, _("— Sin ciudad —"))] + _choices_ciudades()
    if form.validate_on_submit():
        h.nombre = form.nombre.data.strip()
        ciudad_id = form.ciudad_id.data
        h.ciudad_id = ciudad_id if ciudad_id else None
        db.session.commit()
        flash(_("Hospital actualizado."), "success")
        return redirect(url_for("admin.hospitales"))
    elif request.method == "GET":
        form.ciudad_id.data = h.ciudad_id or 0
    return render_template("admin/hospital_form.html", form=form, titulo=_("Editar hospital"))


@bp.route("/hospitales/<int:id>/eliminar", methods=["POST"])
@admin_required
def hospital_eliminar(id):
    h = db.session.get(Hospital, id) or abort(404)
    unidades = h.unidades.all()
    for u in unidades:
        if _unidad_tiene_datos_asociados(u):
            flash(_("No se puede eliminar: alguna de sus unidades tiene datos asociados."), "danger")
            return redirect(url_for("admin.hospitales"))
    for u in unidades:
        db.session.delete(u)
    db.session.delete(h)
    db.session.commit()
    n = len(unidades)
    if n:
        flash(_("Hospital eliminado junto con sus %(n)s unidades.", n=n), "success")
    else:
        flash(_("Hospital eliminado."), "success")
    return redirect(url_for("admin.hospitales"))


# ---------------------------------------------------------------------------
# Unidades
# ---------------------------------------------------------------------------

@bp.route("/unidades", methods=["GET", "POST"])
@admin_required
def unidades():
    form = AdminUnidadForm(prefix="nuevo")
    form.hospital_id.choices = _choices_hospitales()
    form.categoria_id.choices = _choices_cats_unidad()
    if form.validate_on_submit():
        hospital = db.session.get(Hospital, form.hospital_id.data) or abort(400)
        cat_id = form.categoria_id.data
        categoria = db.session.get(Categoria, cat_id) if cat_id else None
        _u, _is_new = encontrar_o_crear_unidad(form.nombre.data, hospital, categoria)
        db.session.commit()
        flash(_("Unidad creada."), "success")
        return redirect(url_for("admin.unidades"))
    todas = Unidad.query.join(Hospital).order_by(Hospital.nombre, Unidad.nombre).all()
    return render_template("admin/unidades.html", unidades=todas, form=form)


@bp.route("/unidades/<int:id>/editar", methods=["GET", "POST"])
@admin_required
def unidad_editar(id):
    u = db.session.get(Unidad, id) or abort(404)
    form = AdminUnidadForm(obj=u)
    form.hospital_id.choices = _choices_hospitales()
    form.categoria_id.choices = _choices_cats_unidad()
    if form.validate_on_submit():
        u.nombre = form.nombre.data.strip()
        u.hospital_id = form.hospital_id.data
        cat_id = form.categoria_id.data
        u.categoria_id = cat_id if cat_id else None
        db.session.commit()
        flash(_("Unidad actualizada."), "success")
        return redirect(url_for("admin.unidades"))
    elif request.method == "GET":
        form.hospital_id.data = u.hospital_id
        form.categoria_id.data = u.categoria_id or 0
    return render_template("admin/unidad_form.html", form=form, titulo=_("Editar unidad"))


_HISTORIAL_MODELS = (
    DocumentoCambio,
    Notificacion,
    EstadoDiaPlanilla,
    TurnoPlanilla,
    PlanillaMes,
    SalienteDia,
    NotaDia,
    MapeoTrabajadorPlanilla,
    PublicacionCambio,
)


def _unidad_tiene_historial(u):
    for model in _HISTORIAL_MODELS:
        if db.session.query(model.id).filter_by(unidad_id=u.id).first():
            return True
    return False


def _unidad_tiene_datos_asociados(u):
    if u.usuarios.count() > 0:
        return True
    if u.membresias_unidad or u.supervisoras:
        return True
    if _unidad_tiene_historial(u):
        return True
    return False


@bp.route("/unidades/<int:id>/eliminar", methods=["POST"])
@admin_required
def unidad_eliminar(id):
    u = db.session.get(Unidad, id) or abort(404)
    if _unidad_tiene_datos_asociados(u):
        flash(_("No se puede eliminar: la unidad tiene datos asociados."), "danger")
        return redirect(url_for("admin.unidades"))
    db.session.query(AuditEliminacion).filter_by(unidad_id=u.id).update({"unidad_id": None})
    db.session.delete(u)
    db.session.commit()
    flash(_("Unidad eliminada."), "success")
    return redirect(url_for("admin.unidades"))


# ---------------------------------------------------------------------------
# Categorías
# ---------------------------------------------------------------------------

@bp.route("/categorias", methods=["GET", "POST"])
@admin_required
def categorias():
    form = AdminNombreForm(prefix="nuevo")
    if form.validate_on_submit():
        encontrar_o_crear_categoria(None, form.nombre.data)
        db.session.commit()
        flash(_("Categoría creada."), "success")
        return redirect(url_for("admin.categorias"))
    todas = Categoria.query.order_by(Categoria.nombre).all()
    return render_template("admin/categorias.html", categorias=todas, form=form)


@bp.route("/categorias/<int:id>/editar", methods=["GET", "POST"])
@admin_required
def categoria_editar(id):
    c = db.session.get(Categoria, id) or abort(404)
    form = AdminNombreForm(obj=c)
    if form.validate_on_submit():
        c.nombre = form.nombre.data.strip()
        db.session.commit()
        flash(_("Categoría actualizada."), "success")
        return redirect(url_for("admin.categorias"))
    return render_template("admin/nombre_form.html", form=form, titulo=_("Editar categoría"), volver=url_for("admin.categorias"))


@bp.route("/categorias/<int:id>/eliminar", methods=["POST"])
@admin_required
def categoria_eliminar(id):
    c = db.session.get(Categoria, id) or abort(404)
    if c.usuarios.count() > 0:
        flash(_("No se puede eliminar: la categoría tiene usuarios asociados."), "danger")
        return redirect(url_for("admin.categorias"))
    db.session.delete(c)
    db.session.commit()
    flash(_("Categoría eliminada."), "success")
    return redirect(url_for("admin.categorias"))
