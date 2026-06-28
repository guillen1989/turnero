from datetime import datetime

from app.extensions import db


class AuditEliminacion(db.Model):
    """Registro inmutable de cada publicación eliminada para poder contarlas en analytics."""
    __tablename__ = "audit_eliminacion"

    id = db.Column(db.Integer, primary_key=True)
    unidad_id = db.Column(db.Integer, db.ForeignKey("unidad.id"), nullable=True)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
