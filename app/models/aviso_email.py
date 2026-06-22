from datetime import datetime, timezone
from app.extensions import db


class AvisoEmail(db.Model):
    __tablename__ = "aviso_email"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    publicacion_id = db.Column(db.Integer, db.ForeignKey("publicacion_cambio.id"), nullable=True)
    enviado_en = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    usuario = db.relationship("Usuario")
