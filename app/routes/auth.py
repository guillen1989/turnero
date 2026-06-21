from flask import Blueprint, jsonify, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from flask_babel import _
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Pais, Provincia, Ciudad, Hospital, Unidad, Categoria
from app.forms.auth import LoginForm, PerfilForm, RegistroForm
from app.models.usuario import Usuario
from app.services.registro import (
    actualizar_perfil, registrar_usuario,
    encontrar_o_crear_pais, encontrar_o_crear_provincia, encontrar_o_crear_ciudad,
)

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
# Registro / login / logout
# ---------------------------------------------------------------------------

@bp.route("/registro", methods=["GET", "POST"])
def registro():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = RegistroForm()
    form.categoria_id.choices = _choices_categorias()

    if form.validate_on_submit():
        pais_id = request.form.get("pais_id", type=int)
        provincia_id = request.form.get("provincia_id", type=int)
        ciudad_id = request.form.get("ciudad_id", type=int)
        hospital_id = request.form.get("hospital_id", type=int)
        unidad_id = request.form.get("unidad_id", type=int)

        hospital_nombre = _resolver_hospital(hospital_id, form.hospital_nuevo.data)
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
                pais_nombre = (form.pais_nuevo.data or "").strip() or None
                provincia_nombre = (form.provincia_nueva.data or "").strip() or None
                ciudad_nombre = (form.ciudad_nueva.data or "").strip() or None
                if ciudad_id and ciudad_id != _OPCION_NUEVA:
                    c = db.session.get(Ciudad, ciudad_id)
                    if c:
                        ciudad_nombre = c.nombre
                        provincia_nombre = c.provincia.nombre
                        pais_nombre = c.provincia.pais.nombre
                elif provincia_id and provincia_id != _OPCION_NUEVA:
                    p = db.session.get(Provincia, provincia_id)
                    if p:
                        provincia_nombre = p.nombre
                        pais_nombre = p.pais.nombre
                elif pais_id and pais_id != _OPCION_NUEVA:
                    pa = db.session.get(Pais, pais_id)
                    if pa:
                        pais_nombre = pa.nombre

                usuario = registrar_usuario(
                    nombre=form.nombre.data,
                    email=form.email.data,
                    password=form.password.data,
                    hospital_nombre=hospital_nombre,
                    unidad_nombre=unidad_nombre,
                    categoria_id=categoria_id if categoria_id != _OPCION_NUEVA_CATEGORIA else None,
                    categoria_nueva_nombre=categoria_nueva,
                    pais_nombre=pais_nombre,
                    provincia_nombre=provincia_nombre,
                    ciudad_nombre=ciudad_nombre,
                )
                login_user(usuario)
                flash(_("¡Bienvenido/a, %(nombre)s!", nombre=usuario.nombre), "success")
                return redirect(url_for("main.index"))
            except IntegrityError:
                db.session.rollback()
                flash(_("Ese correo ya está registrado."), "danger")

    paises = Pais.query.order_by(Pais.nombre).all()
    return render_template("auth/registro.html", form=form, paises=paises)


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


# ---------------------------------------------------------------------------
# API de cascada geográfica
# ---------------------------------------------------------------------------

@bp.get("/api/provincias")
def api_provincias():
    pais_id = request.args.get("pais_id", type=int)
    if not pais_id:
        return jsonify([])
    provincias = Provincia.query.filter_by(pais_id=pais_id).order_by(Provincia.nombre).all()
    return jsonify([{"id": p.id, "nombre": p.nombre} for p in provincias])


@bp.get("/api/ciudades")
def api_ciudades():
    provincia_id = request.args.get("provincia_id", type=int)
    if not provincia_id:
        return jsonify([])
    ciudades = Ciudad.query.filter_by(provincia_id=provincia_id).order_by(Ciudad.nombre).all()
    return jsonify([{"id": c.id, "nombre": c.nombre} for c in ciudades])


@bp.get("/api/hospitales")
def api_hospitales():
    ciudad_id = request.args.get("ciudad_id", type=int)
    if not ciudad_id:
        return jsonify([])
    hospitales = Hospital.query.filter_by(ciudad_id=ciudad_id).order_by(Hospital.nombre).all()
    return jsonify([{"id": h.id, "nombre": h.nombre} for h in hospitales])


@bp.get("/api/unidades")
def api_unidades():
    hospital_id = request.args.get("hospital_id", type=int)
    categoria_id = request.args.get("categoria_id", type=int)
    if not hospital_id:
        return jsonify([])
    q = Unidad.query.filter_by(hospital_id=hospital_id)
    if categoria_id:
        q = q.filter_by(categoria_id=categoria_id)
    unidades = q.order_by(Unidad.nombre).all()
    return jsonify([{"id": u.id, "nombre": u.nombre} for u in unidades])


# ---------------------------------------------------------------------------
# Perfil
# ---------------------------------------------------------------------------

@bp.route("/perfil", methods=["GET", "POST"])
@login_required
def perfil():
    form = PerfilForm()
    form.categoria_id.choices = _choices_categorias()

    if form.validate_on_submit():
        pais_id = request.form.get("pais_id", type=int)
        provincia_id = request.form.get("provincia_id", type=int)
        ciudad_id = request.form.get("ciudad_id", type=int)
        hospital_id = request.form.get("hospital_id", type=int)
        unidad_id = request.form.get("unidad_id", type=int)

        hospital_nombre = _resolver_hospital(hospital_id, form.hospital_nuevo.data)
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
            pais_nombre = (form.pais_nuevo.data or "").strip() or None
            provincia_nombre = (form.provincia_nueva.data or "").strip() or None
            ciudad_nombre = (form.ciudad_nueva.data or "").strip() or None
            if ciudad_id and ciudad_id != _OPCION_NUEVA:
                c = db.session.get(Ciudad, ciudad_id)
                if c:
                    ciudad_nombre = c.nombre
                    provincia_nombre = c.provincia.nombre
                    pais_nombre = c.provincia.pais.nombre
            elif provincia_id and provincia_id != _OPCION_NUEVA:
                p = db.session.get(Provincia, provincia_id)
                if p:
                    provincia_nombre = p.nombre
                    pais_nombre = p.pais.nombre
            elif pais_id and pais_id != _OPCION_NUEVA:
                pa = db.session.get(Pais, pais_id)
                if pa:
                    pais_nombre = pa.nombre

            actualizar_perfil(
                usuario=current_user,
                hospital_nombre=hospital_nombre,
                unidad_nombre=unidad_nombre,
                categoria_id=categoria_id if categoria_id != _OPCION_NUEVA_CATEGORIA else None,
                categoria_nueva_nombre=categoria_nueva,
                pais_nombre=pais_nombre,
                provincia_nombre=provincia_nombre,
                ciudad_nombre=ciudad_nombre,
            )
            flash(_("Perfil actualizado correctamente."), "success")
            return redirect(url_for("main.index"))

    elif request.method == "GET":
        form.categoria_id.data = current_user.categoria_id

    current_hospital = current_user.unidad.hospital
    current_ciudad = current_hospital.ciudad
    current_provincia = current_ciudad.provincia if current_ciudad else None
    current_pais = current_provincia.pais if current_provincia else None

    current_unidades = Unidad.query.filter_by(
        hospital_id=current_hospital.id,
        categoria_id=current_user.categoria_id,
    ).order_by(Unidad.nombre).all()

    # Opciones pre-cargadas para la cascada de la ciudad actual.
    # Si el hospital no tiene ciudad (datos legacy), mostrarlo igualmente.
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

    return render_template(
        "auth/perfil.html",
        form=form,
        paises=Pais.query.order_by(Pais.nombre).all(),
        current_pais_id=current_pais.id if current_pais else None,
        current_provincia_id=current_provincia.id if current_provincia else None,
        current_ciudad_id=current_ciudad.id if current_ciudad else None,
        current_hospital_id=current_hospital.id,
        current_unidad_id=current_user.unidad_id,
        current_provincias=current_provincias,
        current_ciudades=current_ciudades,
        current_hospitales=current_hospitales,
        current_unidades=current_unidades,
    )
