from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user, login_required

from app.extensions import db
from app.forms.admin import AdminNombreForm, AdminUnidadForm, AdminUsuarioForm
from app.models import (
    Categoria,
    Hospital,
    PublicacionCambio,
    Unidad,
    Usuario,
    insertar_categorias_semilla,
)
from app.services.registro import (
    encontrar_o_crear_categoria,
    encontrar_o_crear_hospital,
    encontrar_o_crear_unidad,
)

bp = Blueprint("admin", __name__, url_prefix="/admin")

_OPCION_NUEVA_CATEGORIA = 0


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.es_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def _choices_cats():
    cats = Categoria.query.order_by(Categoria.nombre).all()
    choices = [(c.id, c.nombre) for c in cats]
    choices.append((_OPCION_NUEVA_CATEGORIA, _("— Añadir nueva categoría —")))
    return choices


def _choices_hospitales():
    return [(h.id, h.nombre) for h in Hospital.query.order_by(Hospital.nombre).all()]


# ---------------------------------------------------------------------------
# Vista general
# ---------------------------------------------------------------------------

@bp.route("/")
@admin_required
def index():
    stats = {
        "usuarios": Usuario.query.count(),
        "hospitales": Hospital.query.count(),
        "unidades": Unidad.query.count(),
        "categorias": Categoria.query.count(),
        "publicaciones": PublicacionCambio.query.count(),
    }
    return render_template("admin/index.html", stats=stats)


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------

@bp.route("/usuarios")
@admin_required
def usuarios():
    todos = Usuario.query.order_by(Usuario.nombre).all()
    return render_template("admin/usuarios.html", usuarios=todos)


@bp.route("/usuarios/nuevo", methods=["GET", "POST"])
@admin_required
def usuario_nuevo():
    form = AdminUsuarioForm()
    form.categoria_id.choices = _choices_cats()
    if form.validate_on_submit():
        cat_id = form.categoria_id.data or None
        cat_nueva = form.categoria_nueva.data or None
        if not cat_id and not cat_nueva:
            flash(_("Indica una categoría o escribe una nueva."), "danger")
        elif not form.password.data:
            flash(_("La contraseña es obligatoria para usuarios nuevos."), "danger")
        else:
            hospital = encontrar_o_crear_hospital(form.hospital_nombre.data)
            unidad = encontrar_o_crear_unidad(form.unidad_nombre.data, hospital)
            categoria = encontrar_o_crear_categoria(
                cat_id if cat_id != _OPCION_NUEVA_CATEGORIA else None,
                cat_nueva,
            )
            u = Usuario(
                nombre=form.nombre.data.strip(),
                email=form.email.data.strip().lower(),
                unidad=unidad,
                categoria=categoria,
                es_admin=form.es_admin.data,
            )
            u.set_password(form.password.data)
            db.session.add(u)
            db.session.commit()
            flash(_("Usuario creado."), "success")
            return redirect(url_for("admin.usuarios"))
    hospitales = Hospital.query.order_by(Hospital.nombre).all()
    return render_template("admin/usuario_form.html", form=form, titulo=_("Nuevo usuario"), hospitales=hospitales)


@bp.route("/usuarios/<int:id>/editar", methods=["GET", "POST"])
@admin_required
def usuario_editar(id):
    u = db.session.get(Usuario, id) or abort(404)
    form = AdminUsuarioForm(obj=u)
    form.categoria_id.choices = _choices_cats()
    if form.validate_on_submit():
        cat_id = form.categoria_id.data or None
        cat_nueva = form.categoria_nueva.data or None
        if not cat_id and not cat_nueva:
            flash(_("Indica una categoría o escribe una nueva."), "danger")
        else:
            hospital = encontrar_o_crear_hospital(form.hospital_nombre.data)
            unidad = encontrar_o_crear_unidad(form.unidad_nombre.data, hospital)
            categoria = encontrar_o_crear_categoria(
                cat_id if cat_id != _OPCION_NUEVA_CATEGORIA else None,
                cat_nueva,
            )
            u.nombre = form.nombre.data.strip()
            u.email = form.email.data.strip().lower()
            u.unidad = unidad
            u.categoria = categoria
            u.es_admin = form.es_admin.data
            if form.password.data:
                u.set_password(form.password.data)
            db.session.commit()
            flash(_("Usuario actualizado."), "success")
            return redirect(url_for("admin.usuarios"))
    elif request.method == "GET":
        form.hospital_nombre.data = u.unidad.hospital.nombre
        form.unidad_nombre.data = u.unidad.nombre
        form.categoria_id.data = u.categoria_id
    hospitales = Hospital.query.order_by(Hospital.nombre).all()
    return render_template("admin/usuario_form.html", form=form, titulo=_("Editar usuario"), hospitales=hospitales)


@bp.route("/usuarios/<int:id>/eliminar", methods=["POST"])
@admin_required
def usuario_eliminar(id):
    u = db.session.get(Usuario, id) or abort(404)
    if u.id == current_user.id:
        flash(_("No puedes eliminarte a ti mismo."), "danger")
        return redirect(url_for("admin.usuarios"))
    db.session.delete(u)
    db.session.commit()
    flash(_("Usuario eliminado."), "success")
    return redirect(url_for("admin.usuarios"))


# ---------------------------------------------------------------------------
# Hospitales
# ---------------------------------------------------------------------------

@bp.route("/hospitales", methods=["GET", "POST"])
@admin_required
def hospitales():
    form = AdminNombreForm(prefix="nuevo")
    if form.validate_on_submit():
        encontrar_o_crear_hospital(form.nombre.data)
        db.session.commit()
        flash(_("Hospital creado."), "success")
        return redirect(url_for("admin.hospitales"))
    todos = Hospital.query.order_by(Hospital.nombre).all()
    return render_template("admin/hospitales.html", hospitales=todos, form=form)


@bp.route("/hospitales/<int:id>/editar", methods=["GET", "POST"])
@admin_required
def hospital_editar(id):
    h = db.session.get(Hospital, id) or abort(404)
    form = AdminNombreForm(obj=h)
    if form.validate_on_submit():
        h.nombre = form.nombre.data.strip()
        db.session.commit()
        flash(_("Hospital actualizado."), "success")
        return redirect(url_for("admin.hospitales"))
    return render_template("admin/nombre_form.html", form=form, titulo=_("Editar hospital"), volver=url_for("admin.hospitales"))


@bp.route("/hospitales/<int:id>/eliminar", methods=["POST"])
@admin_required
def hospital_eliminar(id):
    h = db.session.get(Hospital, id) or abort(404)
    if h.unidades.count() > 0:
        flash(_("No se puede eliminar: el hospital tiene unidades asociadas."), "danger")
        return redirect(url_for("admin.hospitales"))
    db.session.delete(h)
    db.session.commit()
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
    if form.validate_on_submit():
        hospital = db.session.get(Hospital, form.hospital_id.data) or abort(400)
        encontrar_o_crear_unidad(form.nombre.data, hospital)
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
    if form.validate_on_submit():
        u.nombre = form.nombre.data.strip()
        u.hospital_id = form.hospital_id.data
        db.session.commit()
        flash(_("Unidad actualizada."), "success")
        return redirect(url_for("admin.unidades"))
    elif request.method == "GET":
        form.hospital_id.data = u.hospital_id
    return render_template("admin/unidad_form.html", form=form, titulo=_("Editar unidad"))


@bp.route("/unidades/<int:id>/eliminar", methods=["POST"])
@admin_required
def unidad_eliminar(id):
    u = db.session.get(Unidad, id) or abort(404)
    if u.usuarios.count() > 0:
        flash(_("No se puede eliminar: la unidad tiene usuarios asociados."), "danger")
        return redirect(url_for("admin.unidades"))
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


# ---------------------------------------------------------------------------
# Publicaciones (cambios de todos los usuarios)
# ---------------------------------------------------------------------------

@bp.route("/publicaciones")
@admin_required
def publicaciones():
    todas = (
        PublicacionCambio.query
        .join(Usuario)
        .order_by(PublicacionCambio.fecha_creacion.desc())
        .all()
    )
    return render_template("admin/publicaciones.html", publicaciones=todas)


@bp.route("/publicaciones/<int:id>/cancelar", methods=["POST"])
@admin_required
def publicacion_cancelar(id):
    p = db.session.get(PublicacionCambio, id) or abort(404)
    p.estado = "cancelada"
    db.session.commit()
    flash(_("Publicación cancelada."), "success")
    return redirect(url_for("admin.publicaciones"))


@bp.route("/publicaciones/<int:id>/eliminar", methods=["POST"])
@admin_required
def publicacion_eliminar(id):
    p = db.session.get(PublicacionCambio, id) or abort(404)
    db.session.delete(p)
    db.session.commit()
    flash(_("Publicación eliminada."), "success")
    return redirect(url_for("admin.publicaciones"))
