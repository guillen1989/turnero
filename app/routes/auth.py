from urllib.parse import quote as urlquote

from flask import Blueprint, abort, current_app, jsonify, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from flask_babel import _
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Pais, Provincia, Ciudad, Hospital, Unidad, Categoria
from app.forms.auth import (
    CuentaForm, EliminarCuentaForm, LoginForm, PerfilForm, RegistroForm,
    SolicitarResetForm, RestablecerPasswordForm,
)
from app.models.usuario import Usuario
from app.services.email import enviar_email, url_absoluta
from app.services.password_reset import (
    TOKEN_TTL_MINUTOS, consumir_token, generar_token_reset, obtener_usuario_por_token,
)
from app.services.registro import (
    actualizar_perfil, eliminar_cuenta, registrar_usuario,
    encontrar_o_crear_pais, encontrar_o_crear_provincia, encontrar_o_crear_ciudad,
    resolver_hospital, resolver_unidad,
)

bp = Blueprint("auth", __name__)

_OPCION_NUEVA = 0
_OPCION_NUEVA_CATEGORIA = 0


def _datos_invitacion():
    """Lee los parámetros inv_* del query string y devuelve un dict con los IDs
    geográficos necesarios para pre-rellenar el formulario de registro."""
    inv_hospital_id = request.args.get("inv_hospital", type=int)
    if not inv_hospital_id:
        return {}
    hospital = db.session.get(Hospital, inv_hospital_id)
    if not hospital:
        return {}
    ciudad = hospital.ciudad
    provincia = ciudad.provincia if ciudad else None
    pais = provincia.pais if provincia else None
    return {
        "pais_id": pais.id if pais else None,
        "provincia_id": provincia.id if provincia else None,
        "ciudad_id": ciudad.id if ciudad else None,
        "hospital_id": hospital.id,
        "unidad_id": request.args.get("inv_unidad", type=int),
        "categoria_id": request.args.get("inv_categoria", type=int),
    }


def _choices_categorias():
    cats = Categoria.query.filter(
        Categoria.nombre != "Administrador"
    ).order_by(Categoria.nombre).all()
    choices = [(c.id, c.nombre) for c in cats]
    choices.append((_OPCION_NUEVA_CATEGORIA, _("— Añadir nueva categoría —")))
    return choices



# ---------------------------------------------------------------------------
# Registro / login / logout
# ---------------------------------------------------------------------------

@bp.route("/registro", methods=["GET", "POST"])
def registro():
    if current_user.is_authenticated:
        return redirect(url_for("calendario.index"))

    form = RegistroForm()
    form.categoria_id.choices = _choices_categorias()

    if form.validate_on_submit():
        pais_id = request.form.get("pais_id", type=int)
        provincia_id = request.form.get("provincia_id", type=int)
        ciudad_id = request.form.get("ciudad_id", type=int)
        hospital_id = request.form.get("hospital_id", type=int)
        unidad_id = request.form.get("unidad_id", type=int)

        hospital_nombre = resolver_hospital(hospital_id, form.hospital_nuevo.data)
        unidad_nombre = resolver_unidad(unidad_id, form.unidad_nuevo.data)
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
                login_user(usuario, remember=True)
                flash(_("¡Bienvenido/a, %(nombre)s!", nombre=usuario.nombre), "success")
                if getattr(usuario, "_es_nueva_unidad", False):
                    flash(_("Tu unidad es nueva. Configura los turnos disponibles en tu servicio."), "info")
                    return redirect(url_for("unidad.turnos"))
                return redirect(url_for("main.como_funciona"))
            except IntegrityError:
                db.session.rollback()
                flash(_("Ese correo ya está registrado."), "danger")

    inv = _datos_invitacion()
    if request.method == "GET" and inv.get("categoria_id"):
        form.categoria_id.data = inv["categoria_id"]

    paises = Pais.query.order_by(Pais.nombre).all()
    return render_template("auth/registro.html", form=form, paises=paises, inv=inv)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("calendario.index"))

    form = LoginForm()
    if form.validate_on_submit():
        usuario = Usuario.query.filter_by(email=form.email.data.strip().lower()).first()
        if usuario and usuario.check_password(form.password.data):
            login_user(usuario, remember=True)
            siguiente = request.args.get("next")
            if siguiente:
                return redirect(siguiente)
            if not usuario.onboarding_visto:
                return redirect(url_for("main.como_funciona"))
            return redirect(url_for("calendario.index"))
        flash(_("Correo o contraseña incorrectos."), "danger")

    demo_login_enabled = bool(current_app.config.get("DEMO_LOGIN_EMAIL"))
    return render_template("auth/login.html", form=form, demo_login_enabled=demo_login_enabled)


@bp.route("/login/demo", methods=["POST"])
def login_demo():
    if current_user.is_authenticated:
        return redirect(url_for("calendario.index"))

    demo_email = current_app.config.get("DEMO_LOGIN_EMAIL")
    demo_password = current_app.config.get("DEMO_LOGIN_PASSWORD")
    if not demo_email or not demo_password:
        abort(404)

    usuario = Usuario.query.filter_by(email=demo_email).first()
    if usuario and usuario.check_password(demo_password):
        login_user(usuario, remember=True)
        if not usuario.onboarding_visto:
            return redirect(url_for("main.como_funciona"))
        return redirect(url_for("calendario.index"))

    flash(_("No se pudo iniciar sesión con la cuenta demo."), "danger")
    return redirect(url_for("auth.login"))


@bp.get("/logout")
@login_required
def logout():
    logout_user()
    flash(_("Has cerrado sesión."), "info")
    return redirect(url_for("auth.login"))


@bp.route("/recuperar-contrasena", methods=["GET", "POST"])
def recuperar_contrasena():
    form = SolicitarResetForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        usuario = Usuario.query.filter_by(email=email).first()
        if usuario:
            token = generar_token_reset(usuario)
            enlace = url_absoluta("auth.restablecer_password", token=token)
            cuerpo_html = render_template(
                "email/recuperar_password.html",
                usuario=usuario, enlace=enlace, ttl_minutos=TOKEN_TTL_MINUTOS,
            )
            enviar_email(usuario.email, _("Recupera tu contraseña de Turnero"), cuerpo_html)
        # Mismo mensaje exista o no el email: evita revelar qué correos están registrados.
        flash(
            _("Si ese email está registrado, te hemos enviado un enlace para restablecer la contraseña."),
            "success",
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/recuperar.html", form=form)


@bp.route("/restablecer-contrasena/<token>", methods=["GET", "POST"])
def restablecer_password(token):
    usuario = obtener_usuario_por_token(token)
    if usuario is None:
        flash(_("El enlace no es válido o ha caducado. Solicita uno nuevo."), "danger")
        return redirect(url_for("auth.recuperar_contrasena"))

    form = RestablecerPasswordForm()
    if form.validate_on_submit():
        usuario.set_password(form.password.data)
        consumir_token(token)
        flash(_("Contraseña actualizada. Ya puedes iniciar sesión."), "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/restablecer.html", form=form)


# ---------------------------------------------------------------------------
# API de cascada geográfica
# ---------------------------------------------------------------------------

@bp.get("/api/provincias")
def api_provincias():
    pais_id = request.args.get("pais_id", type=int)
    if not pais_id:
        return jsonify([])
    provincias = Provincia.query.filter_by(pais_id=pais_id).order_by(Provincia.nombre).all()
    ids = [p.id for p in provincias]
    counts = dict(
        db.session.query(Ciudad.provincia_id, func.count(Ciudad.id))
        .filter(Ciudad.provincia_id.in_(ids))
        .group_by(Ciudad.provincia_id).all()
    )
    return jsonify([
        {"id": p.id, "nombre": p.nombre, "count": counts.get(p.id, 0)}
        for p in provincias
    ])


@bp.get("/api/ciudades")
def api_ciudades():
    provincia_id = request.args.get("provincia_id", type=int)
    if not provincia_id:
        return jsonify([])
    ciudades = Ciudad.query.filter_by(provincia_id=provincia_id).order_by(Ciudad.nombre).all()
    ids = [c.id for c in ciudades]
    counts = dict(
        db.session.query(Hospital.ciudad_id, func.count(Hospital.id))
        .filter(Hospital.ciudad_id.in_(ids))
        .group_by(Hospital.ciudad_id).all()
    )
    return jsonify([
        {"id": c.id, "nombre": c.nombre, "count": counts.get(c.id, 0)}
        for c in ciudades
    ])


@bp.get("/api/hospitales")
def api_hospitales():
    ciudad_id = request.args.get("ciudad_id", type=int)
    if not ciudad_id:
        return jsonify([])
    hospitales = Hospital.query.filter_by(ciudad_id=ciudad_id).order_by(Hospital.nombre).all()
    ids = [h.id for h in hospitales]
    counts = dict(
        db.session.query(Unidad.hospital_id, func.count(Unidad.id))
        .filter(Unidad.hospital_id.in_(ids))
        .group_by(Unidad.hospital_id).all()
    )
    return jsonify([
        {"id": h.id, "nombre": h.nombre, "count": counts.get(h.id, 0)}
        for h in hospitales
    ])


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
    ids = [u.id for u in unidades]
    counts = dict(
        db.session.query(Usuario.unidad_id, func.count(Usuario.id))
        .filter(Usuario.unidad_id.in_(ids))
        .group_by(Usuario.unidad_id).all()
    )
    return jsonify([
        {"id": u.id, "nombre": u.nombre, "count": counts.get(u.id, 0)}
        for u in unidades
    ])


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

        hospital_nombre = resolver_hospital(hospital_id, form.hospital_nuevo.data)
        unidad_nombre = resolver_unidad(unidad_id, form.unidad_nuevo.data)
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

            usuario_actualizado = actualizar_perfil(
                usuario=current_user,
                hospital_nombre=hospital_nombre,
                unidad_nombre=unidad_nombre,
                categoria_id=categoria_id if categoria_id != _OPCION_NUEVA_CATEGORIA else None,
                categoria_nueva_nombre=categoria_nueva,
                pais_nombre=pais_nombre,
                provincia_nombre=provincia_nombre,
                ciudad_nombre=ciudad_nombre,
            )
            db.session.commit()
            flash(_("Perfil actualizado correctamente."), "success")
            if getattr(usuario_actualizado, "_es_nueva_unidad", False):
                flash(_("Has creado una nueva unidad. Configura sus turnos."), "info")
                return redirect(url_for("unidad.turnos"))
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


# ---------------------------------------------------------------------------
# Perfil — pestaña Cuenta (nombre, email, contraseña)
# ---------------------------------------------------------------------------

@bp.route("/perfil/cuenta", methods=["GET", "POST"])
@login_required
def perfil_cuenta():
    form = CuentaForm()

    if form.validate_on_submit():
        nuevo_email = form.email.data.strip().lower()
        cambio_email = nuevo_email != current_user.email
        cambio_password = bool(form.password_nuevo.data)

        if cambio_email or cambio_password:
            if not form.password_actual.data or not current_user.check_password(form.password_actual.data):
                flash(_("Debes introducir tu contraseña actual para cambiar el correo o la contraseña."), "danger")
                return redirect(url_for("auth.perfil_cuenta"))

        if cambio_email:
            if Usuario.query.filter(
                Usuario.email == nuevo_email, Usuario.id != current_user.id
            ).first():
                flash(_("Ese correo ya está registrado por otro usuario."), "danger")
                return redirect(url_for("auth.perfil_cuenta"))
            current_user.email = nuevo_email

        current_user.nombre = form.nombre.data.strip()

        if cambio_password:
            current_user.set_password(form.password_nuevo.data)

        db.session.commit()
        flash(_("Datos de cuenta actualizados correctamente."), "success")
        return redirect(url_for("auth.perfil_cuenta"))

    elif request.method == "GET":
        form.nombre.data = current_user.nombre
        form.email.data = current_user.email

    invite_url = url_for(
        "auth.registro",
        inv_hospital=current_user.unidad.hospital.id,
        inv_unidad=current_user.unidad_id,
        inv_categoria=current_user.categoria_id,
        _external=True,
    )
    hospital_nombre = current_user.unidad.hospital.nombre
    unidad_nombre = current_user.unidad.nombre
    texto_wa = _(
        "¡Únete a Turnero! En %(hospital)s / %(unidad)s usamos esta app para "
        "gestionar los cambios de turno entre compañeros. ¡Es muy fácil! "
        "Entra aquí: %(url)s",
        hospital=hospital_nombre,
        unidad=unidad_nombre,
        url=invite_url,
    )
    wa_url = "https://wa.me/?text=" + urlquote(texto_wa)
    eliminar_form = EliminarCuentaForm()
    return render_template(
        "auth/perfil_cuenta.html",
        form=form,
        invite_url=invite_url,
        wa_url=wa_url,
        eliminar_form=eliminar_form,
    )


# ---------------------------------------------------------------------------
# Eliminar cuenta
# ---------------------------------------------------------------------------

@bp.post("/perfil/cuenta/eliminar")
@login_required
def eliminar_cuenta_route():
    form = EliminarCuentaForm()
    if not form.validate_on_submit():
        flash(_("No se pudo procesar la solicitud."), "danger")
        return redirect(url_for("auth.perfil_cuenta"))

    if not current_user.check_password(form.password.data):
        flash(_("Contraseña incorrecta. La cuenta no ha sido eliminada."), "danger")
        return redirect(url_for("auth.perfil_cuenta"))

    eliminar_cuenta(current_user)
    logout_user()
    flash(_("Tu cuenta ha sido eliminada. Hasta pronto."), "info")
    return redirect(url_for("auth.login"))
