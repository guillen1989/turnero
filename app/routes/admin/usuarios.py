import secrets

from flask import abort, flash, redirect, render_template, request, url_for
from flask_babel import _
from flask_login import current_user

from app.extensions import db
from app.forms.admin import AdminUsuarioForm
from app.models import Ciudad, Hospital, Pais, Provincia, Unidad, Usuario
from app.routes.admin import admin_required, bp
from app.routes.admin.helpers import _OPCION_NUEVA_CATEGORIA, _choices_cats, _choices_unidades
from app.services.registro import (
    crear_usuario_con_invitacion,
    encontrar_o_crear_categoria,
    encontrar_o_crear_hospital,
    encontrar_o_crear_unidad,
    eliminar_usuario_admin,
    resolver_geo,
    resolver_hospital,
    resolver_unidad,
)
from app.services.supervision import sincronizar_unidades_supervisadas


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
    form.unidades_supervisadas.choices = _choices_unidades()
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
        email = form.email.data.strip().lower()
        if Usuario.query.filter_by(email=email).first():
            flash(_("Ya existe un usuario con ese email."), "danger")
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
                email=email,
                unidad=unidad,
                categoria=categoria,
                es_admin=form.es_admin.data,
                es_supervisora=form.es_supervisora.data,
            )
            u.set_password(secrets.token_urlsafe(32))
            db.session.add(u)
            db.session.flush()
            if u.es_supervisora:
                sincronizar_unidades_supervisadas(
                    u, set(form.unidades_supervisadas.data) | {unidad.id}
                )
            db.session.commit()
            email_enviado = crear_usuario_con_invitacion(u)
            flash(_("Usuario creado."), "success")
            if not email_enviado:
                flash(
                    _("No se ha podido enviar el email de invitación. "
                      "El usuario puede usar \"He olvidado mi contraseña\" en la "
                      "pantalla de acceso para recibir un enlace."),
                    "danger",
                )
            return redirect(url_for("admin.usuarios"))

    paises = Pais.query.order_by(Pais.nombre).all()
    return render_template(
        "admin/usuario_form.html", form=form, titulo=_("Nuevo usuario"), es_creacion=True,
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
    form.unidades_supervisadas.choices = _choices_unidades()
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
        email = form.email.data.strip().lower()
        if Usuario.query.filter(Usuario.email == email, Usuario.id != u.id).first():
            flash(_("Ya existe un usuario con ese email."), "danger")
            errores = True

        if not errores:
            hospital = encontrar_o_crear_hospital(hospital_nombre, ciudad)
            categoria = encontrar_o_crear_categoria(
                cat_id if cat_id != _OPCION_NUEVA_CATEGORIA else None,
                cat_nueva,
            )
            unidad, _is_new = encontrar_o_crear_unidad(unidad_nombre, hospital, categoria)
            u.nombre = form.nombre.data.strip()
            u.email = email
            u.unidad = unidad
            u.categoria = categoria
            u.es_admin = form.es_admin.data
            u.es_supervisora = form.es_supervisora.data
            if form.password.data:
                u.set_password(form.password.data)
            if u.es_supervisora:
                sincronizar_unidades_supervisadas(
                    u, set(form.unidades_supervisadas.data) | {unidad.id}
                )
            else:
                sincronizar_unidades_supervisadas(u, set())
            db.session.commit()
            flash(_("Usuario actualizado."), "success")
            return redirect(url_for("admin.usuarios"))
    elif request.method == "GET":
        form.categoria_id.data = u.categoria_id
        form.unidades_supervisadas.data = [
            unidad_sup.id for unidad_sup in u.unidades_supervisadas if unidad_sup.id != u.unidad_id
        ]

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
        "admin/usuario_form.html", form=form, titulo=_("Editar usuario"), es_creacion=False,
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
