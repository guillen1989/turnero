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
    hospital_nombre = StringField(
        _l("Hospital"),
        validators=[DataRequired()],
    )
    unidad_nombre = StringField(
        _l("Unidad / servicio"),
        validators=[DataRequired()],
    )
    # choices se asignan dinámicamente en la ruta
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
