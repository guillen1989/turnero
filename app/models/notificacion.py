from datetime import datetime, timezone
from app.extensions import db

TIPOS_NOTIFICACION = ("nuevo_match", "confirmacion_parcial", "rechazo", "caducidad", "nueva_publicacion_seguido", "contraoferta", "alerta_busqueda_guardada", "aviso_interes", "aviso_sintetica")


class Notificacion(db.Model):
    __tablename__ = "notificacion"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    match_id = db.Column(db.Integer, db.ForeignKey("match_cambio.id"), nullable=True)
    publicacion_id = db.Column(db.Integer, db.ForeignKey("publicacion_cambio.id"), nullable=True)
    busqueda_guardada_id = db.Column(
        db.Integer,
        db.ForeignKey("busqueda_guardada.id", ondelete="SET NULL"),
        nullable=True,
    )
    tipo = db.Column(db.String(50), nullable=False)
    fecha = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    leida = db.Column(db.Boolean, nullable=False, default=False)

    usuario = db.relationship("Usuario", back_populates="notificaciones")
    match = db.relationship("MatchCambio", back_populates="notificaciones")
    publicacion = db.relationship("PublicacionCambio")
    busqueda_guardada = db.relationship("BusquedaGuardada")

    def __repr__(self):
        return f"<Notificacion {self.tipo} usuario={self.usuario_id} leida={self.leida}>"
