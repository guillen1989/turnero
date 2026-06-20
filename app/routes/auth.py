from flask import Blueprint, jsonify, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from flask_babel import _
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Hospital, Unidad, Categoria
from app.forms.auth import LoginForm, PerfilForm, RegistroForm
from app.models.usuario import Usuario
from app.services.registro import actualizar_perfil, registrar_usuario

bp = Blueprint("auth", __name__)

_OPCION_NUEVA = 0
_OPCION_NUEVA_CATEGORIA = 0


def _choices_categorias():
    cats = Categoria.query.filter(
        Categoria.nombre != "Administrador"
    ).order_by(Categoria.nombre).all()
    choices = [(c.id, c.nombre) for c in cats]
    choices.append((_OPCION_NUEVA_CATEGORIA, _("— Añadir nueva categoría —")))
    return choices


def _resolver_hospital(hospital_id, hospital_nuevo):
    """Devuelve el nombre del hospital a usar, o None si falta dato."""
    if hospital_id == _OPCION_NUEVA or hospital_id is None:
        nombre = (hospital_nuevo or "").strip()
        return nombre if nombre else None
    h = db.session.get(Hospital, hospital_id)
    return h.nombre if h else None


def _resolver_unidad(unidad_id, unidad_nuevo):
    """Devuelve el nombre de la unidad a usar, o None si falta dato."""
    if unidad_id == _OPCION_NUEVA or unidad_id is None:
        nombre = (unidad_nuevo or "").strip()
        return nombre if nombre else None
    u = db.session.get(Unidad, unidad_id)
    return u.nombre if u else None


@bp.route("/registro", methods=["GET", "POST"])
def registro():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = RegistroForm()
    form.categoria_id.choices = _choices_categorias()

    if form.validate_on_submit():
        hospital_id = request.form.get("hospital_id", type=int)
        hospital_nombre = _resolver_hospital(hospital_id, form.hospital_nuevo.data)
        unidad_id = request.form.get("unidad_id", type=int)
        unidad_nombre = _resolver_unidad(unidad_id, form.unidad_nuevo.data)
        categoria_id = form.categoria_id.data or None
        categoria_nueva = form.categoria_nueva.data or None

        errores = False
        if not hospital_nombre:
            flash(_("Selecciona un hospital o escribe el nombre de uno nuevo."), "danger")
            errores = True
        if not unidad_nombre:
            flash(_("Selecciona una unidad o escribe el nombre de una nueva."), "danger")
            errores = True
        if not categoria_id and not categoria_nueva:
            form.categoria_nueva.errors.append(_("Indica una categoría o escribe una nueva."))
            errores = True

        if not errores:
            try:
                usuario = registrar_usuario(
                    nombre=form.nombre.data,
                    email=form.email.data,
                    password=form.password.data,
                    hospital_nombre=hospital_nombre,
                    unidad_nombre=unidad_nombre,
                    categoria_id=categoria_id if categoria_id != _OPCION_NUEVA_CATEGORIA else None,
                    categoria_nueva_nombre=categoria_nueva,
                )
                login_user(usuario)
                flash(_("¡Bienvenido/a, %(nombre)s!", nombre=usuario.nombre), "success")
                return redirect(url_for("main.index"))
            except IntegrityError:
                db.session.rollback()
                flash(_("Ese correo ya está registrado."), "danger")

    hospitales = Hospital.query.order_by(Hospital.nombre).all()
    return render_template("auth/registro.html", form=form, hospitales=hospitales)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        usuario = Usuario.query.filter_by(email=form.email.data.strip().lower()).first()
        if usuario and usuario.check_password(form.password.data):
            login_user(usuario)
            siguiente = request.args.get("next")
            return redirect(siguiente or url_for("main.index"))
        flash(_("Correo o contraseña incorrectos."), "danger")

    return render_template("auth/login.html", form=form)


@bp.get("/logout")
@login_required
def logout():
    logout_user()
    flash(_("Has cerrado sesión."), "info")
    return redirect(url_for("auth.login"))


@bp.get("/api/unidades")
def api_unidades():
    hospital_id = request.args.get("hospital_id", type=int)
    if not hospital_id:
        return jsonify([])
    hospital = db.session.get(Hospital, hospital_id)
    if not hospital:
        return jsonify([])
    unidades = Unidad.query.filter_by(hospital_id=hospital.id).order_by(Unidad.nombre).all()
    return jsonify([{"id": u.id, "nombre": u.nombre} for u in unidades])


@bp.route("/perfil", methods=["GET", "POST"])
@login_required
def perfil():
    form = PerfilForm()
    form.categoria_id.choices = _choices_categorias()

    if form.validate_on_submit():
        hospital_id = request.form.get("hospital_id", type=int)
        hospital_nombre = _resolver_hospital(hospital_id, form.hospital_nuevo.data)
        unidad_id = request.form.get("unidad_id", type=int)
        unidad_nombre = _resolver_unidad(unidad_id, form.unidad_nuevo.data)
        categoria_id = form.categoria_id.data or None
        categoria_nueva = form.categoria_nueva.data or None

        errores = False
        if not hospital_nombre:
            flash(_("Selecciona un hospital o escribe el nombre de uno nuevo."), "danger")
            errores = True
        if not unidad_nombre:
            flash(_("Selecciona una unidad o escribe el nombre de una nueva."), "danger")
            errores = True
        if not categoria_id and not categoria_nueva:
            form.categoria_nueva.errors.append(_("Indica una categoría o escribe una nueva."))
            errores = True

        if not errores:
            actualizar_perfil(
                usuario=current_user,
                hospital_nombre=hospital_nombre,
                unidad_nombre=unidad_nombre,
                categoria_id=categoria_id if categoria_id != _OPCION_NUEVA_CATEGORIA else None,
                categoria_nueva_nombre=categoria_nueva,
            )
            flash(_("Perfil actualizado correctamente."), "success")
            return redirect(url_for("main.index"))

    elif request.method == "GET":
        form.categoria_id.data = current_user.categoria_id

    current_hospital = current_user.unidad.hospital
    current_unidades = Unidad.query.filter_by(
        hospital_id=current_hospital.id
    ).order_by(Unidad.nombre).all()

    return render_template(
        "auth/perfil.html",
        form=form,
        hospitales=Hospital.query.order_by(Hospital.nombre).all(),
        current_hospital_id=current_hospital.id,
        current_unidad_id=current_user.unidad_id,
        current_unidades=current_unidades,
    )
