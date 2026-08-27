from datetime import datetime

from app.extensions import db


class ParseoAsistente(db.Model):
    """Registro mínimo de cada llamada al asistente de parseo de WhatsApp.

    Solo guarda quién y cuándo, no el texto ni la propuesta: sirve para
    aplicar el límite diario por usuario sin depender de la política de
    privacidad (pendiente) que exigiría guardar contenido.
    """
    __tablename__ = "parseo_asistente"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    creado_en = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    usuario = db.relationship("Usuario", backref="parseos_asistente")
