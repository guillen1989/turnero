from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, SubmitField
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
