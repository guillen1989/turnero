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
    # hospital_id y unidad_id se leen de request.form en la ruta (no son campos WTForms)
    hospital_nuevo = StringField(
        _l("Nombre del nuevo hospital"),
        validators=[Optional(), Length(max=200)],
    )
    unidad_nuevo = StringField(
        _l("Nombre de la nueva unidad"),
        validators=[Optional(), Length(max=200)],
    )
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
    hospital_nuevo = StringField(
        _l("Nombre del nuevo hospital"),
        validators=[Optional(), Length(max=200)],
    )
    unidad_nuevo = StringField(
        _l("Nombre de la nueva unidad"),
        validators=[Optional(), Length(max=200)],
    )
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
