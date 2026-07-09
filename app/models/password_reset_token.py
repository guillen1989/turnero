from datetime import datetime, timezone

from app.extensions import db


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_token"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    # timezone=True (TIMESTAMPTZ): la comparación de expiración cruza un
    # commit/recarga desde BD, y con TIMESTAMP naive Postgres reinterpreta el
    # datetime aware UTC en la zona horaria de la sesión (Europe/Madrid en
    # local), desplazando la expiración ~2h y rompiendo la comparación.
    fecha_creacion = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    fecha_expiracion = db.Column(db.DateTime(timezone=True), nullable=False)
    usado = db.Column(db.Boolean, nullable=False, default=False)

    usuario = db.relationship("Usuario")

    def __repr__(self):
        return f"<PasswordResetToken usuario={self.usuario_id} usado={self.usado}>"
