from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user, login_required

from app.extensions import db
from app.forms.admin import (
    AdminNombreForm, AdminUnidadForm, AdminUsuarioForm,
    AdminProvinciaForm, AdminCiudadForm, AdminHospitalForm,
)
from app.models import (
    Pais, Provincia, Ciudad,
    Categoria, Feedback, Hospital, MatchCambio, MatchParticipacion,
    Notificacion, PublicacionCambio, Unidad, Usuario,
    insertar_categorias_semilla,
)
from app.services.registro import (
    encontrar_o_crear_categoria,
    encontrar_o_crear_hospital,
    encontrar_o_crear_unidad,
    encontrar_o_crear_pais,
    encontrar_o_crear_provincia,
    encontrar_o_crear_ciudad,
)

bp = Blueprint("admin", __name__, url_prefix="/admin")

_OPCION_NUEVA = 0
_OPCION_NUEVA_CATEGORIA = 0


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.es_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Helpers de choices
# ---------------------------------------------------------------------------

def _choices_cats():
    cats = Categoria.query.order_by(Categoria.nombre).all()
    choices = [(c.id, c.nombre) for c in cats]
    choices.append((_OPCION_NUEVA_CATEGORIA, _("— Añadir nueva categoría —")))
    return choices


def _choices_cats_unidad():
    cats = Categoria.query.order_by(Categoria.nombre).all()
    return [(0, _("— Sin categoría —"))] + [(c.id, c.nombre) for c in cats]


def _choices_hospitales():
    return [(h.id, h.nombre) for h in Hospital.query.order_by(Hospital.nombre).all()]


def _choices_paises():
    return [(p.id, p.nombre) for p in Pais.query.order_by(Pais.nombre).all()]


def _choices_provincias():
    return [(p.id, f"{p.nombre} ({p.pais.nombre})") for p in
            Provincia.query.join(Pais).order_by(Pais.nombre, Provincia.nombre).all()]


def _choices_ciudades():
    return [(c.id, f"{c.nombre} — {c.provincia.nombre}, {c.provincia.pais.nombre}") for c in
            Ciudad.query.join(Provincia).join(Pais).order_by(Pais.nombre, Provincia.nombre, Ciudad.nombre).all()]


# ---------------------------------------------------------------------------
# Helpers de resolución (igual que en auth.py)
# ---------------------------------------------------------------------------

def _resolver_geo(pais_id, pais_nuevo, provincia_id, provincia_nueva, ciudad_id, ciudad_nueva):
    if pais_id and pais_id != _OPCION_NUEVA:
        pais = db.session.get(Pais, pais_id)
    else:
        nombre = (pais_nuevo or "").strip()
        pais = encontrar_o_crear_pais(nombre) if nombre else None
    if pais is None:
        return None

    if provincia_id and provincia_id != _OPCION_NUEVA:
        provincia = db.session.get(Provincia, provincia_id)
    else:
        nombre = (provincia_nueva or "").strip()
        provincia = encontrar_o_crear_provincia(nombre, pais) if nombre else None
    if provincia is None:
        return None

    if ciudad_id and ciudad_id != _OPCION_NUEVA:
        ciudad = db.session.get(Ciudad, ciudad_id)
    else:
        nombre = (ciudad_nueva or "").strip()
        ciudad = encontrar_o_crear_ciudad(nombre, provincia) if nombre else None
    return ciudad


def _resolver_hospital(hospital_id, hospital_nuevo):
    if hospital_id == _OPCION_NUEVA or hospital_id is None:
        nombre = (hospital_nuevo or "").strip()
        return nombre if nombre else None
    h = db.session.get(Hospital, hospital_id)
    return h.nombre if h else None


def _resolver_unidad(unidad_id, unidad_nuevo):
    if unidad_id == _OPCION_NUEVA or unidad_id is None:
        nombre = (unidad_nuevo or "").strip()
        return nombre if nombre else None
    u = db.session.get(Unidad, unidad_id)
    return u.nombre if u else None


# ---------------------------------------------------------------------------
# Vista general
# ---------------------------------------------------------------------------

@bp.route("/")
@admin_required
def index():
    stats = {
        "usuarios": Usuario.query.count(),
        "paises": Pais.query.count(),
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
        pais_id = request.form.get("pais_id", type=int)
        provincia_id = request.form.get("provincia_id", type=int)
        ciudad_id = request.form.get("ciudad_id", type=int)
        hospital_id = request.form.get("hospital_id", type=int)
        unidad_id = request.form.get("unidad_id", type=int)

        ciudad = _resolver_geo(
            pais_id, form.pais_nuevo.data,
            provincia_id, form.provincia_nueva.data,
            ciudad_id, form.ciudad_nueva.data,
        )
        hospital_nombre = _resolver_hospital(hospital_id, form.hospital_nuevo.data)
        unidad_nombre = _resolver_unidad(unidad_id, form.unidad_nuevo.data)
        cat_id = form.categoria_id.data or None
        cat_nueva = form.categoria_nueva.data or None

        errores = False
        if not hospital_nombre:
            flash(_("Selecciona un hospital o escribe el nombre de uno nuevo."), "danger")
            errores = True
        if not unidad_nombre:
            flash(_("Selecciona una unidad o escribe el nombre de una nueva."), "danger")
            errores = True
        if not cat_id and not cat_nueva:
            flash(_("Indica una categoría o escribe una nueva."), "danger")
            errores = True
        if not errores and not form.password.data:
            flash(_("La contraseña es obligatoria para usuarios nuevos."), "danger")
            errores = True

        if not errores:
            hospital = encontrar_o_crear_hospital(hospital_nombre, ciudad)
            categoria = encontrar_o_crear_categoria(
                cat_id if cat_id != _OPCION_NUEVA_CATEGORIA else None,
                cat_nueva,
            )
            unidad = encontrar_o_crear_unidad(unidad_nombre, hospital, categoria)
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

    paises = Pais.query.order_by(Pais.nombre).all()
    return render_template(
        "admin/usuario_form.html", form=form, titulo=_("Nuevo usuario"),
        paises=paises,
        current_pais_id=None, current_provincia_id=None, current_ciudad_id=None,
        current_hospital_id=None, current_unidad_id=None,
        current_provincias=[], current_ciudades=[], current_hospitales=[], current_unidades=[],
    )


@bp.route("/usuarios/<int:id>/editar", methods=["GET", "POST"])
@admin_required
def usuario_editar(id):
    u = db.session.get(Usuario, id) or abort(404)
    form = AdminUsuarioForm(obj=u)
    form.categoria_id.choices = _choices_cats()
    if form.validate_on_submit():
        pais_id = request.form.get("pais_id", type=int)
        provincia_id = request.form.get("provincia_id", type=int)
        ciudad_id = request.form.get("ciudad_id", type=int)
        hospital_id = request.form.get("hospital_id", type=int)
        unidad_id = request.form.get("unidad_id", type=int)

        ciudad = _resolver_geo(
            pais_id, form.pais_nuevo.data,
            provincia_id, form.provincia_nueva.data,
            ciudad_id, form.ciudad_nueva.data,
        )
        hospital_nombre = _resolver_hospital(hospital_id, form.hospital_nuevo.data)
        unidad_nombre = _resolver_unidad(unidad_id, form.unidad_nuevo.data)
        cat_id = form.categoria_id.data or None
        cat_nueva = form.categoria_nueva.data or None

        errores = False
        if not hospital_nombre:
            flash(_("Selecciona un hospital o escribe el nombre de uno nuevo."), "danger")
            errores = True
        if not unidad_nombre:
            flash(_("Selecciona una unidad o escribe el nombre de una nueva."), "danger")
            errores = True
        if not cat_id and not cat_nueva:
            flash(_("Indica una categoría o escribe una nueva."), "danger")
            errores = True

        if not errores:
            hospital = encontrar_o_crear_hospital(hospital_nombre, ciudad)
            categoria = encontrar_o_crear_categoria(
                cat_id if cat_id != _OPCION_NUEVA_CATEGORIA else None,
                cat_nueva,
            )
            unidad = encontrar_o_crear_unidad(unidad_nombre, hospital, categoria)
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
        form.categoria_id.data = u.categoria_id

    current_hospital = u.unidad.hospital
    current_ciudad = current_hospital.ciudad
    current_provincia = current_ciudad.provincia if current_ciudad else None
    current_pais = current_provincia.pais if current_provincia else None

    current_unidades = Unidad.query.filter_by(
        hospital_id=current_hospital.id,
        categoria_id=u.categoria_id,
    ).order_by(Unidad.nombre).all()
    current_hospitales = (
        Hospital.query.filter_by(ciudad_id=current_ciudad.id).order_by(Hospital.nombre).all()
        if current_ciudad else [current_hospital]
    )
    current_ciudades = (
        Ciudad.query.filter_by(provincia_id=current_provincia.id).order_by(Ciudad.nombre).all()
        if current_provincia else []
    )
    current_provincias = (
        Provincia.query.filter_by(pais_id=current_pais.id).order_by(Provincia.nombre).all()
        if current_pais else []
    )

    paises = Pais.query.order_by(Pais.nombre).all()
    return render_template(
        "admin/usuario_form.html", form=form, titulo=_("Editar usuario"),
        paises=paises,
        current_pais_id=current_pais.id if current_pais else None,
        current_provincia_id=current_provincia.id if current_provincia else None,
        current_ciudad_id=current_ciudad.id if current_ciudad else None,
        current_hospital_id=current_hospital.id,
        current_unidad_id=u.unidad_id,
        current_provincias=current_provincias,
        current_ciudades=current_ciudades,
        current_hospitales=current_hospitales,
        current_unidades=current_unidades,
    )


@bp.route("/usuarios/<int:id>/eliminar", methods=["POST"])
@admin_required
def usuario_eliminar(id):
    u = db.session.get(Usuario, id) or abort(404)
    if u.id == current_user.id:
        flash(_("No puedes eliminarte a ti mismo."), "danger")
        return redirect(url_for("admin.usuarios"))

    # Delete in the correct order to satisfy FK constraints.
    # Step 1: delete matches that involve this user's publications.
    # (MatchParticipacion.publicacion_id and .turno_cedido_id block deletion otherwise.)
    pub_ids = [p.id for p in u.publicaciones]
    if pub_ids:
        matches = (
            MatchCambio.query
            .join(MatchParticipacion)
            .filter(MatchParticipacion.publicacion_id.in_(pub_ids))
            .all()
        )
        for match in matches:
            # MatchCambio.notificaciones has no cascade, so delete manually.
            Notificacion.query.filter_by(match_id=match.id).delete()
            db.session.delete(match)  # cascades to MatchParticipacion

    # Step 2: delete user's own notifications.
    Notificacion.query.filter_by(usuario_id=u.id).delete()

    # Step 3: delete user's publications (cascades to TurnoCedido + TurnoAceptado).
    for pub in u.publicaciones:
        db.session.delete(pub)

    db.session.delete(u)
    db.session.commit()
    flash(_("Usuario eliminado."), "success")
    return redirect(url_for("admin.usuarios"))


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
        if u.usuarios.count() > 0:
            flash(_("No se puede eliminar: alguna de sus unidades tiene usuarios asociados."), "danger")
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
        encontrar_o_crear_unidad(form.nombre.data, hospital, categoria)
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
# Publicaciones
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


@bp.route("/feedback")
@admin_required
def feedback():
    items = Feedback.query.order_by(Feedback.fecha_creacion.desc()).all()
    return render_template("admin/feedback.html", items=items)
