from functools import wraps

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user, login_required
from sqlalchemy import distinct, func

from app.extensions import csrf, db
from app.forms.admin import (
    AdminNombreForm, AdminUnidadForm, AdminUsuarioForm,
    AdminProvinciaForm, AdminCiudadForm, AdminHospitalForm, AdminFranjaForm,
)
from app.models import (
    AuditEliminacion,
    Event,
    Pais, Provincia, Ciudad,
    Categoria, Feedback, FranjaHoraria, GrupoIntercambio, Hospital,
    MatchCambio, MatchParticipacion,
    Notificacion, PublicacionCambio, Unidad, Usuario,
    PlanillaMes,
    insertar_categorias_semilla,
)
from app.services.registro import asignar_color_franja
from app.services.publicaciones import eliminar_publicacion
from app.services.registro import (
    encontrar_o_crear_categoria,
    encontrar_o_crear_hospital,
    encontrar_o_crear_unidad,
    encontrar_o_crear_pais,
    encontrar_o_crear_provincia,
    encontrar_o_crear_ciudad,
    eliminar_usuario_admin,
    resolver_geo, resolver_hospital, resolver_unidad,
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

        ciudad = resolver_geo(
            pais_id, form.pais_nuevo.data,
            provincia_id, form.provincia_nueva.data,
            ciudad_id, form.ciudad_nueva.data,
        )
        hospital_nombre = resolver_hospital(hospital_id, form.hospital_nuevo.data)
        unidad_nombre = resolver_unidad(unidad_id, form.unidad_nuevo.data)
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
            unidad, _is_new = encontrar_o_crear_unidad(unidad_nombre, hospital, categoria)
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

        ciudad = resolver_geo(
            pais_id, form.pais_nuevo.data,
            provincia_id, form.provincia_nueva.data,
            ciudad_id, form.ciudad_nueva.data,
        )
        hospital_nombre = resolver_hospital(hospital_id, form.hospital_nuevo.data)
        unidad_nombre = resolver_unidad(unidad_id, form.unidad_nuevo.data)
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
            unidad, _is_new = encontrar_o_crear_unidad(unidad_nombre, hospital, categoria)
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


@bp.route("/usuarios/<int:id>/eliminar", methods=["GET", "POST"])
@admin_required
def usuario_eliminar(id):
    u = db.session.get(Usuario, id) or abort(404)
    if u.id == current_user.id:
        flash(_("No puedes eliminarte a ti mismo."), "danger")
        return redirect(url_for("admin.usuarios"))

    if request.method == "GET":
        num_pubs = u.publicaciones.count()
        return render_template("admin/usuario_eliminar_confirm.html", usuario=u, num_pubs=num_pubs)

    eliminar_usuario_admin(u)
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

def _matches_info_por_pub(publicaciones):
    """Devuelve un dict {pub_id: {partners, fecha_match, fecha_confirmacion}}."""
    pub_ids = [p.id for p in publicaciones]
    if not pub_ids:
        return {}

    participaciones = (
        MatchParticipacion.query
        .filter(MatchParticipacion.publicacion_id.in_(pub_ids))
        .all()
    )
    match_ids = {p.match_id for p in participaciones}
    if not match_ids:
        return {}

    matches = {m.id: m for m in MatchCambio.query.filter(MatchCambio.id.in_(match_ids)).all()}
    todas_parts = (
        MatchParticipacion.query
        .filter(MatchParticipacion.match_id.in_(match_ids))
        .all()
    )

    result = {}
    for part in participaciones:
        match = matches[part.match_id]
        if match.estado in ("rechazado",):
            continue
        partners = [
            p.publicacion.usuario.nombre
            for p in todas_parts
            if p.match_id == match.id and p.publicacion_id != part.publicacion_id
        ]
        existing = result.get(part.publicacion_id)
        if existing is None or (match.fecha_creacion and (
            existing["fecha_match"] is None or match.fecha_creacion < existing["fecha_match"]
        )):
            result[part.publicacion_id] = {
                "partners": partners,
                "fecha_match": match.fecha_creacion,
                "fecha_confirmacion": match.fecha_confirmacion_total,
            }
    return result


_SORT_COLUMNS = {
    "usuario": Usuario.nombre,
    "estado": PublicacionCambio.estado,
    "fecha": PublicacionCambio.fecha_creacion,
}


@bp.route("/publicaciones")
@admin_required
def publicaciones():
    sort = request.args.get("sort", "fecha")
    order = request.args.get("order", "desc")

    col = _SORT_COLUMNS.get(sort, PublicacionCambio.fecha_creacion)
    col_sorted = col.asc() if order == "asc" else col.desc()

    todas = (
        PublicacionCambio.query
        .join(Usuario)
        .order_by(col_sorted)
        .all()
    )
    matches_info = _matches_info_por_pub(todas)
    return render_template(
        "admin/publicaciones.html",
        publicaciones=todas,
        matches_info=matches_info,
        sort=sort,
        order=order,
    )


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
    eliminar_publicacion(p)
    flash(_("Publicación eliminada."), "success")
    return redirect(url_for("admin.publicaciones"))


@bp.route("/feedback")
@admin_required
def feedback():
    tab = request.args.get("tab", "sin_leer")
    sin_leer = (
        Feedback.query
        .filter_by(leido=False)
        .order_by(Feedback.fecha_creacion.desc())
        .all()
    )
    leidos = (
        Feedback.query
        .filter_by(leido=True)
        .order_by(Feedback.fecha_creacion.desc())
        .all()
    )
    return render_template("admin/feedback.html", sin_leer=sin_leer, leidos=leidos, tab=tab)


@bp.route("/feedback/<int:id>/marcar-leido", methods=["POST"])
@admin_required
def feedback_marcar_leido(id):
    fb = db.session.get(Feedback, id) or abort(404)
    fb.leido = True
    db.session.commit()
    return redirect(url_for("admin.feedback"))


@bp.route("/feedback/marcar-leidos", methods=["POST"])
@admin_required
def feedback_marcar_leidos():
    ids = request.form.getlist("ids", type=int)
    if ids:
        Feedback.query.filter(Feedback.id.in_(ids)).update({"leido": True}, synchronize_session=False)
        db.session.commit()
    return redirect(url_for("admin.feedback", tab="sin_leer"))


@bp.route("/feedback/<int:id>/restablecer-contrasena", methods=["POST"])
@admin_required
def feedback_restablecer_contrasena(id):
    import secrets
    fb = db.session.get(Feedback, id) or abort(404)
    usuario = Usuario.query.filter_by(email=fb.email_contacto).first()
    if not usuario:
        flash(_("No se encontró ningún usuario con el email %(email)s.", email=fb.email_contacto), "danger")
        return redirect(url_for("admin.feedback"))

    contrasena_temporal = secrets.token_urlsafe(8)
    usuario.set_password(contrasena_temporal)
    fb.leido = True
    db.session.add(Notificacion(
        usuario_id=usuario.id,
        tipo="contrasena_restablecida",
        mensaje=_("Un administrador te ha restablecido la contraseña. Nueva contraseña temporal: %(pwd)s",
                   pwd=contrasena_temporal),
    ))
    db.session.commit()

    flash(
        _("Contraseña restablecida para %(email)s. Se le ha enviado un aviso con la nueva contraseña.",
          email=fb.email_contacto),
        "success",
    )
    return redirect(url_for("admin.feedback"))


# ---------------------------------------------------------------------------
# Unidad demo
# ---------------------------------------------------------------------------

@bp.route("/demo/reset", methods=["POST"])
@admin_required
def demo_reset():
    from app.services.demo import reset_demo
    try:
        reset_demo()
        flash(_("Unidad de demostración regenerada correctamente."), "success")
    except Exception as e:
        db.session.rollback()
        flash(_("Error al regenerar la demo: %(error)s", error=str(e)), "danger")
    return redirect(url_for("admin.index"))


@bp.route("/demo/reset-cron", methods=["POST"])
@csrf.exempt
def demo_reset_cron():
    """Endpoint para cron externo (cron-job.org). Requiere token en Authorization header."""
    import os
    token = os.environ.get("DEMO_RESET_TOKEN", "")
    if not token:
        abort(404)
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {token}":
        abort(403)
    from app.services.demo import reset_demo
    reset_demo()
    return jsonify({"ok": True, "mensaje": "Demo regenerada."})



# ---------------------------------------------------------------------------
# Franjas horarias (turnos)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@bp.route("/analytics")
@admin_required
def analytics():
    stats = {
        "usuarios": Usuario.query.count(),
        "hospitales": Hospital.query.count(),
        "unidades": Unidad.query.count(),
        "categorias": Categoria.query.count(),
        "publicaciones": PublicacionCambio.query.filter_by(es_sintetica=False).count(),
        "oportunidades_3": PublicacionCambio.query.filter(
            PublicacionCambio.es_sintetica.is_(True),
            PublicacionCambio.sintetica_pub_intermedio_id.is_(None),
        ).count(),
        "oportunidades_4": PublicacionCambio.query.filter(
            PublicacionCambio.es_sintetica.is_(True),
            PublicacionCambio.sintetica_pub_intermedio_id.isnot(None),
        ).count(),
        "activas": PublicacionCambio.query.filter(
            PublicacionCambio.es_sintetica.is_(False),
            PublicacionCambio.estado.in_(["abierta", "parcialmente_resuelta"]),
        ).count(),
        "matches": MatchCambio.query.count(),
        "confirmados": MatchCambio.query.filter_by(estado="confirmado_total").count(),
        "eliminadas": AuditEliminacion.query.count(),
        "planillas_publicadas": (
            db.session.query(func.count(distinct(PlanillaMes.usuario_id)))
            .filter(PlanillaMes.publicada.is_(True))
            .scalar() or 0
        ),
    }
    unidades = (
        Unidad.query
        .join(Hospital)
        .outerjoin(Categoria, Unidad.categoria_id == Categoria.id)
        .order_by(Hospital.nombre, Categoria.nombre, Unidad.nombre)
        .all()
    )
    return render_template("admin/analytics.html", stats=stats, unidades=unidades)


@bp.route("/analytics/data")
@admin_required
def analytics_data():
    granularity = request.args.get("granularity", "day")
    if granularity not in ("day", "week", "month"):
        granularity = "day"
    unidad_id = request.args.get("unidad_id", type=int)

    def to_dict(rows):
        return {str(row.periodo.date()): row.total for row in rows if row.periodo is not None}

    # ── usuarios nuevos ──────────────────────────────────────────────────────
    q_u = db.session.query(
        func.date_trunc(granularity, Usuario.fecha_registro).label("periodo"),
        func.count(Usuario.id).label("total"),
    )
    if unidad_id:
        q_u = q_u.filter(Usuario.unidad_id == unidad_id)
    rows_u = q_u.group_by("periodo").order_by("periodo").all()

    # ── publicaciones nuevas ─────────────────────────────────────────────────
    q_p = db.session.query(
        func.date_trunc(granularity, PublicacionCambio.fecha_creacion).label("periodo"),
        func.count(PublicacionCambio.id).label("total"),
    ).filter(PublicacionCambio.es_sintetica.is_(False))
    if unidad_id:
        q_p = q_p.join(Usuario, Usuario.id == PublicacionCambio.usuario_id).filter(
            Usuario.unidad_id == unidad_id
        )
    rows_p = q_p.group_by("periodo").order_by("periodo").all()

    # ── publicaciones cerradas (para cálculo de activas acumuladas) ──────────
    q_pc = db.session.query(
        func.date_trunc(granularity, PublicacionCambio.fecha_cierre).label("periodo"),
        func.count(PublicacionCambio.id).label("total"),
    ).filter(
        PublicacionCambio.es_sintetica.is_(False),
        PublicacionCambio.fecha_cierre.isnot(None),
    )
    if unidad_id:
        q_pc = q_pc.join(Usuario, Usuario.id == PublicacionCambio.usuario_id).filter(
            Usuario.unidad_id == unidad_id
        )
    rows_pc = q_pc.group_by("periodo").order_by("periodo").all()

    # ── matches nuevos ───────────────────────────────────────────────────────
    q_m = db.session.query(
        func.date_trunc(granularity, MatchCambio.fecha_creacion).label("periodo"),
        func.count(distinct(MatchCambio.id)).label("total"),
    )
    if unidad_id:
        q_m = (
            q_m
            .join(MatchParticipacion, MatchParticipacion.match_id == MatchCambio.id)
            .join(PublicacionCambio, PublicacionCambio.id == MatchParticipacion.publicacion_id)
            .join(Usuario, Usuario.id == PublicacionCambio.usuario_id)
            .filter(Usuario.unidad_id == unidad_id)
        )
    rows_m = q_m.group_by("periodo").order_by("periodo").all()

    # ── confirmados ──────────────────────────────────────────────────────────
    q_c = db.session.query(
        func.date_trunc(granularity, MatchCambio.fecha_confirmacion_total).label("periodo"),
        func.count(distinct(MatchCambio.id)).label("total"),
    ).filter(
        MatchCambio.estado == "confirmado_total",
        MatchCambio.fecha_confirmacion_total.isnot(None),
    )
    if unidad_id:
        q_c = (
            q_c
            .join(MatchParticipacion, MatchParticipacion.match_id == MatchCambio.id)
            .join(PublicacionCambio, PublicacionCambio.id == MatchParticipacion.publicacion_id)
            .join(Usuario, Usuario.id == PublicacionCambio.usuario_id)
            .filter(Usuario.unidad_id == unidad_id)
        )
    rows_c = q_c.group_by("periodo").order_by("periodo").all()

    # ── clics "Me interesa" ──────────────────────────────────────────────────
    q_mi = db.session.query(
        func.date_trunc(granularity, Event.created_at).label("periodo"),
        func.count(Event.id).label("total"),
    ).filter(Event.event_type == "me_interesa")
    if unidad_id:
        q_mi = q_mi.join(Usuario, Usuario.id == Event.user_id).filter(
            Usuario.unidad_id == unidad_id
        )
    rows_mi = q_mi.group_by("periodo").order_by("periodo").all()

    # ── publicaciones eliminadas ─────────────────────────────────────────────
    q_e = db.session.query(
        func.date_trunc(granularity, AuditEliminacion.fecha).label("periodo"),
        func.count(AuditEliminacion.id).label("total"),
    )
    if unidad_id:
        q_e = q_e.filter(AuditEliminacion.unidad_id == unidad_id)
    rows_e = q_e.group_by("periodo").order_by("periodo").all()

    # ── planillas publicadas ─────────────────────────────────────────────────
    q_pp = db.session.query(
        func.date_trunc(granularity, Event.created_at).label("periodo"),
        func.count(Event.id).label("total"),
    ).filter(Event.event_type == "planilla_publicada")
    if unidad_id:
        q_pp = q_pp.join(Usuario, Usuario.id == Event.user_id).filter(
            Usuario.unidad_id == unidad_id
        )
    rows_pp = q_pp.group_by("periodo").order_by("periodo").all()

    d_u  = to_dict(rows_u)
    d_p  = to_dict(rows_p)
    d_pc = to_dict(rows_pc)
    d_m  = to_dict(rows_m)
    d_c  = to_dict(rows_c)
    d_mi = to_dict(rows_mi)
    d_e  = to_dict(rows_e)
    d_pp = to_dict(rows_pp)

    # Unión de todas las fechas con actividad
    all_dates = sorted(
        set(d_u) | set(d_p) | set(d_pc) | set(d_m) | set(d_c) | set(d_mi) | set(d_e) | set(d_pp)
    )

    # Activas acumuladas: suma corriente de (creadas - cerradas) por bucket
    all_delta_dates = sorted(set(d_p) | set(d_pc))
    i_delta = 0
    running_activas = 0
    d_activas = {}
    for d in all_dates:
        while i_delta < len(all_delta_dates) and all_delta_dates[i_delta] <= d:
            dd = all_delta_dates[i_delta]
            running_activas += d_p.get(dd, 0) - d_pc.get(dd, 0)
            i_delta += 1
        d_activas[d] = running_activas

    # ── Totales para los contadores ──────────────────────────────────────────
    if unidad_id:
        unidad_obj = db.session.get(Unidad, unidad_id)
        t_usuarios = Usuario.query.filter_by(unidad_id=unidad_id).count()
        t_hospitales = 1 if unidad_obj else 0
        t_unidades = 1 if unidad_obj else 0
        t_categorias = 1 if (unidad_obj and unidad_obj.categoria_id) else 0
        t_publicaciones = (
            PublicacionCambio.query.filter_by(es_sintetica=False)
            .join(Usuario, Usuario.id == PublicacionCambio.usuario_id)
            .filter(Usuario.unidad_id == unidad_id)
            .count()
        )
        t_oportunidades_3 = (
            PublicacionCambio.query.filter(
                PublicacionCambio.es_sintetica.is_(True),
                PublicacionCambio.sintetica_pub_intermedio_id.is_(None),
            )
            .join(Usuario, Usuario.id == PublicacionCambio.usuario_id)
            .filter(Usuario.unidad_id == unidad_id)
            .count()
        )
        t_oportunidades_4 = (
            PublicacionCambio.query.filter(
                PublicacionCambio.es_sintetica.is_(True),
                PublicacionCambio.sintetica_pub_intermedio_id.isnot(None),
            )
            .join(Usuario, Usuario.id == PublicacionCambio.usuario_id)
            .filter(Usuario.unidad_id == unidad_id)
            .count()
        )
        t_activas = (
            PublicacionCambio.query.filter(
                PublicacionCambio.es_sintetica.is_(False),
                PublicacionCambio.estado.in_(["abierta", "parcialmente_resuelta"]),
            )
            .join(Usuario, Usuario.id == PublicacionCambio.usuario_id)
            .filter(Usuario.unidad_id == unidad_id)
            .count()
        )
        t_matches = (
            db.session.query(func.count(distinct(MatchCambio.id)))
            .join(MatchParticipacion, MatchParticipacion.match_id == MatchCambio.id)
            .join(PublicacionCambio, PublicacionCambio.id == MatchParticipacion.publicacion_id)
            .join(Usuario, Usuario.id == PublicacionCambio.usuario_id)
            .filter(Usuario.unidad_id == unidad_id)
            .scalar() or 0
        )
        t_confirmados = (
            db.session.query(func.count(distinct(MatchCambio.id)))
            .filter(MatchCambio.estado == "confirmado_total")
            .join(MatchParticipacion, MatchParticipacion.match_id == MatchCambio.id)
            .join(PublicacionCambio, PublicacionCambio.id == MatchParticipacion.publicacion_id)
            .join(Usuario, Usuario.id == PublicacionCambio.usuario_id)
            .filter(Usuario.unidad_id == unidad_id)
            .scalar() or 0
        )
        t_eliminadas = AuditEliminacion.query.filter_by(unidad_id=unidad_id).count()
        t_planillas_publicadas = (
            db.session.query(func.count(distinct(PlanillaMes.usuario_id)))
            .join(Usuario, Usuario.id == PlanillaMes.usuario_id)
            .filter(PlanillaMes.publicada.is_(True), Usuario.unidad_id == unidad_id)
            .scalar() or 0
        )
        t_me_interesa = (
            db.session.query(func.count(Event.id))
            .filter(Event.event_type == "me_interesa")
            .join(Usuario, Usuario.id == Event.user_id)
            .filter(Usuario.unidad_id == unidad_id)
            .scalar() or 0
        )
    else:
        t_usuarios = Usuario.query.count()
        t_hospitales = Hospital.query.count()
        t_unidades = Unidad.query.count()
        t_categorias = Categoria.query.count()
        t_publicaciones = PublicacionCambio.query.filter_by(es_sintetica=False).count()
        t_oportunidades_3 = PublicacionCambio.query.filter(
            PublicacionCambio.es_sintetica.is_(True),
            PublicacionCambio.sintetica_pub_intermedio_id.is_(None),
        ).count()
        t_oportunidades_4 = PublicacionCambio.query.filter(
            PublicacionCambio.es_sintetica.is_(True),
            PublicacionCambio.sintetica_pub_intermedio_id.isnot(None),
        ).count()
        t_activas = PublicacionCambio.query.filter(
            PublicacionCambio.es_sintetica.is_(False),
            PublicacionCambio.estado.in_(["abierta", "parcialmente_resuelta"]),
        ).count()
        t_matches = MatchCambio.query.count()
        t_confirmados = MatchCambio.query.filter_by(estado="confirmado_total").count()
        t_eliminadas = AuditEliminacion.query.count()
        t_planillas_publicadas = (
            db.session.query(func.count(distinct(PlanillaMes.usuario_id)))
            .filter(PlanillaMes.publicada.is_(True))
            .scalar() or 0
        )
        t_me_interesa = (
            db.session.query(func.count(Event.id))
            .filter(Event.event_type == "me_interesa")
            .scalar() or 0
        )

    return jsonify({
        "labels": all_dates,
        "datasets": {
            "usuarios": [d_u.get(d, 0) for d in all_dates],
            "publicaciones": [d_p.get(d, 0) for d in all_dates],
            "activas": [d_activas.get(d, 0) for d in all_dates],
            "matches": [d_m.get(d, 0) for d in all_dates],
            "confirmados": [d_c.get(d, 0) for d in all_dates],
            "me_interesa": [d_mi.get(d, 0) for d in all_dates],
            "eliminadas": [d_e.get(d, 0) for d in all_dates],
            "planillas_publicadas": [d_pp.get(d, 0) for d in all_dates],
        },
        "totals": {
            "usuarios": t_usuarios,
            "hospitales": t_hospitales,
            "unidades": t_unidades,
            "categorias": t_categorias,
            "publicaciones": t_publicaciones,
            "oportunidades_3": t_oportunidades_3,
            "oportunidades_4": t_oportunidades_4,
            "activas": t_activas,
            "matches": t_matches,
            "confirmados": t_confirmados,
            "eliminadas": t_eliminadas,
            "planillas_publicadas": t_planillas_publicadas,
            "me_interesa": t_me_interesa,
        },
    })
