from datetime import datetime

from app.extensions import db


class Feedback(db.Model):
    __tablename__ = "feedback"

    id              = db.Column(db.Integer, primary_key=True)
    tipo            = db.Column(db.String(20), nullable=False)
    descripcion     = db.Column(db.Text, nullable=False)
    email_contacto  = db.Column(db.String(200), nullable=True)
    usuario_id      = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=True)
    fecha_creacion  = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    usuario = db.relationship("Usuario", backref="feedbacks")
