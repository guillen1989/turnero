from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional
from flask_babel import lazy_gettext as _l


class AdminUsuarioForm(FlaskForm):
    nombre = StringField(_l("Nombre"), validators=[DataRequired(), Length(max=200)])
    email = StringField(_l("Correo electrónico"), validators=[DataRequired(), Email()])
    password = PasswordField(_l("Contraseña (dejar vacío para no cambiar)"), validators=[Optional(), Length(min=8)])
    hospital_nuevo = StringField(_l("Nuevo hospital"), validators=[Optional(), Length(max=200)])
    unidad_nuevo = StringField(_l("Nueva unidad"), validators=[Optional(), Length(max=200)])
    categoria_id = SelectField(_l("Categoría"), coerce=int, choices=[], validators=[Optional()])
    categoria_nueva = StringField(_l("Nueva categoría"), validators=[Optional(), Length(max=100)])
    es_admin = BooleanField(_l("Administrador"))
    submit = SubmitField(_l("Guardar"))


class AdminNombreForm(FlaskForm):
    """Formulario genérico para entidades con solo campo nombre (hospital, categoría)."""
    nombre = StringField(_l("Nombre"), validators=[DataRequired(), Length(max=200)])
    submit = SubmitField(_l("Guardar"))


class AdminUnidadForm(FlaskForm):
    nombre = StringField(_l("Nombre de la unidad"), validators=[DataRequired(), Length(max=200)])
    hospital_id = SelectField(_l("Hospital"), coerce=int, choices=[], validators=[DataRequired()])
    categoria_id = SelectField(_l("Categoría"), coerce=int, choices=[], validators=[Optional()])
    submit = SubmitField(_l("Guardar"))
