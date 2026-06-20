from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from flask_babel import _
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Hospital, Unidad, Categoria
from app.forms.auth import RegistroForm, LoginForm
from app.models.usuario import Usuario
from app.services.registro import registrar_usuario

bp = Blueprint("auth", __name__)

_OPCION_NUEVA_CATEGORIA = 0


def _choices_categorias():
    cats = Categoria.query.order_by(Categoria.nombre).all()
    choices = [(c.id, c.nombre) for c in cats]
    choices.append((_OPCION_NUEVA_CATEGORIA, _("— Añadir nueva categoría —")))
    return choices


@bp.route("/registro", methods=["GET", "POST"])
def registro():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = RegistroForm()
    form.categoria_id.choices = _choices_categorias()

    if form.validate_on_submit():
        categoria_id = form.categoria_id.data or None
        categoria_nueva = form.categoria_nueva.data or None

        if not categoria_id and not categoria_nueva:
            form.categoria_nueva.errors.append(_("Indica una categoría o escribe una nueva."))
        else:
            try:
                usuario = registrar_usuario(
                    nombre=form.nombre.data,
                    email=form.email.data,
                    password=form.password.data,
                    hospital_nombre=form.hospital_nombre.data,
                    unidad_nombre=form.unidad_nombre.data,
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
    unidades = Unidad.query.order_by(Unidad.nombre).all()
    return render_template(
        "auth/registro.html",
        form=form,
        hospitales=hospitales,
        unidades=unidades,
    )


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
