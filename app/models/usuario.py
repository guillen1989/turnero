from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db, login_manager


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuario"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(254), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    unidad_id = db.Column(db.Integer, db.ForeignKey("unidad.id"), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey("categoria.id"), nullable=False)
    locale = db.Column(db.String(10), nullable=False, default="es")
    push_subscription = db.Column(db.Text, nullable=True)
    fecha_registro = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    unidad = db.relationship("Unidad", back_populates="usuarios")
    categoria = db.relationship("Categoria", back_populates="usuarios")
    publicaciones = db.relationship("PublicacionCambio", back_populates="usuario", lazy="dynamic")
    notificaciones = db.relationship("Notificacion", back_populates="usuario", lazy="dynamic")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def grupo_intercambio(self):
        return self.unidad.grupo_intercambio

    def __repr__(self):
        return f"<Usuario {self.email}>"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))
