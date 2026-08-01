from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional
from flask_babel import lazy_gettext as _l


class RegistroForm(FlaskForm):
    nombre = StringField(
        _l("Nombre completo"),
        validators=[DataRequired(), Length(min=2, max=200)],
    )
    email = StringField(
        _l("Correo electrónico"),
        validators=[DataRequired(), Email()],
    )
    password = PasswordField(
        _l("Contraseña"),
        validators=[DataRequired(), Length(min=8, message=_l("Mínimo 8 caracteres"))],
    )
    password2 = PasswordField(
        _l("Repite la contraseña"),
        validators=[DataRequired(), EqualTo("password", message=_l("Las contraseñas no coinciden"))],
    )
    # pais_id, provincia_id, ciudad_id, hospital_id, unidad_id se leen de request.form
    pais_nuevo = StringField(_l("Nuevo país"), validators=[Optional(), Length(max=100)])
    provincia_nueva = StringField(_l("Nueva provincia"), validators=[Optional(), Length(max=100)])
    ciudad_nueva = StringField(_l("Nueva ciudad"), validators=[Optional(), Length(max=100)])
    hospital_nuevo = StringField(_l("Nombre del nuevo hospital"), validators=[Optional(), Length(max=200)])
    unidad_nuevo = StringField(_l("Nombre de la nueva unidad"), validators=[Optional(), Length(max=200)])
    categoria_id = SelectField(
        _l("Categoría profesional"),
        coerce=int,
        choices=[],
        validators=[Optional()],
    )
    categoria_nueva = StringField(
        _l("Nombre de la nueva categoría"),
        validators=[Optional(), Length(max=100)],
    )
    # Segundo servicio opcional (multi-unidad): mismo bloque que el principal,
    # con prefijo "extra". Los selects de país/provincia/ciudad/hospital/unidad
    # se leen de request.form con prefijo extra_ (igual que los del principal).
    extra_servicio = BooleanField(_l("Añadir otro servicio"), validators=[Optional()])
    extra_pais_nuevo = StringField(_l("Nuevo país (segundo servicio)"), validators=[Optional(), Length(max=100)])
    extra_provincia_nueva = StringField(_l("Nueva provincia (segundo servicio)"), validators=[Optional(), Length(max=100)])
    extra_ciudad_nueva = StringField(_l("Nueva ciudad (segundo servicio)"), validators=[Optional(), Length(max=100)])
    extra_hospital_nuevo = StringField(_l("Nombre del nuevo hospital (segundo servicio)"), validators=[Optional(), Length(max=200)])
    extra_unidad_nuevo = StringField(_l("Nombre de la nueva unidad (segundo servicio)"), validators=[Optional(), Length(max=200)])
    extra_categoria_id = SelectField(
        _l("Categoría profesional (segundo servicio)"),
        coerce=int,
        choices=[],
        validators=[Optional()],
    )
    extra_categoria_nueva = StringField(
        _l("Nombre de la nueva categoría (segundo servicio)"),
        validators=[Optional(), Length(max=100)],
    )
    submit = SubmitField(_l("Crear cuenta"))


class PerfilForm(FlaskForm):
    pais_nuevo = StringField(_l("Nuevo país"), validators=[Optional(), Length(max=100)])
    provincia_nueva = StringField(_l("Nueva provincia"), validators=[Optional(), Length(max=100)])
    ciudad_nueva = StringField(_l("Nueva ciudad"), validators=[Optional(), Length(max=100)])
    hospital_nuevo = StringField(_l("Nombre del nuevo hospital"), validators=[Optional(), Length(max=200)])
    unidad_nuevo = StringField(_l("Nombre de la nueva unidad"), validators=[Optional(), Length(max=200)])
    categoria_id = SelectField(
        _l("Categoría profesional"),
        coerce=int,
        choices=[],
        validators=[Optional()],
    )
    categoria_nueva = StringField(
        _l("Nombre de la nueva categoría"),
        validators=[Optional(), Length(max=100)],
    )
    submit = SubmitField(_l("Guardar cambios"))


class CuentaForm(FlaskForm):
    nombre = StringField(
        _l("Nombre completo"),
        validators=[DataRequired(), Length(min=2, max=200)],
    )
    email = StringField(
        _l("Correo electrónico"),
        validators=[DataRequired(), Email()],
    )
    password_actual = PasswordField(_l("Contraseña actual"), validators=[Optional()])
    password_nuevo = PasswordField(
        _l("Nueva contraseña"),
        validators=[Optional(), Length(min=8, message=_l("Mínimo 8 caracteres"))],
    )
    password_nuevo2 = PasswordField(
        _l("Repite la nueva contraseña"),
        validators=[Optional(), EqualTo("password_nuevo", message=_l("Las contraseñas no coinciden"))],
    )
    submit = SubmitField(_l("Guardar cambios"))


class AgregarUnidadForm(FlaskForm):
    pais_nuevo = StringField(_l("Nuevo país"), validators=[Optional(), Length(max=100)])
    provincia_nueva = StringField(_l("Nueva provincia"), validators=[Optional(), Length(max=100)])
    ciudad_nueva = StringField(_l("Nueva ciudad"), validators=[Optional(), Length(max=100)])
    hospital_nuevo = StringField(_l("Nombre del nuevo hospital"), validators=[Optional(), Length(max=200)])
    unidad_nuevo = StringField(_l("Nombre de la nueva unidad"), validators=[Optional(), Length(max=200)])
    categoria_id = SelectField(
        _l("Categoría profesional"),
        coerce=int,
        choices=[],
        validators=[Optional()],
    )
    categoria_nueva = StringField(
        _l("Nombre de la nueva categoría"),
        validators=[Optional(), Length(max=100)],
    )
    submit = SubmitField(_l("Añadir servicio"))


class EliminarCuentaForm(FlaskForm):
    password = PasswordField(
        _l("Contraseña"),
        validators=[DataRequired()],
    )
    submit = SubmitField(_l("Eliminar mi cuenta definitivamente"))


class LoginForm(FlaskForm):
    email = StringField(
        _l("Correo electrónico"),
        validators=[DataRequired(), Email()],
    )
    password = PasswordField(
        _l("Contraseña"),
        validators=[DataRequired()],
    )
    submit = SubmitField(_l("Entrar"))


class SolicitarResetForm(FlaskForm):
    email = StringField(
        _l("Correo electrónico"),
        validators=[DataRequired(), Email()],
    )
    submit = SubmitField(_l("Enviar enlace de recuperación"))


class RestablecerPasswordForm(FlaskForm):
    password = PasswordField(
        _l("Nueva contraseña"),
        validators=[DataRequired(), Length(min=8, message=_l("Mínimo 8 caracteres"))],
    )
    password2 = PasswordField(
        _l("Repite la nueva contraseña"),
        validators=[DataRequired(), EqualTo("password", message=_l("Las contraseñas no coinciden"))],
    )
    submit = SubmitField(_l("Cambiar contraseña"))
