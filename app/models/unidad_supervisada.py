from app.extensions import db


class UnidadSupervisada(db.Model):
    """Relación N:M entre una supervisora y las unidades que puede gestionar
    en /planilla/supervision, independiente de Usuario.unidad_id (la unidad
    propia del usuario, usada en matching y planilla personal)."""

    __tablename__ = "unidad_supervisada"

    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), primary_key=True)
    unidad_id = db.Column(db.Integer, db.ForeignKey("unidad.id"), primary_key=True)

    def __repr__(self):
        return f"<UnidadSupervisada usuario_id={self.usuario_id} unidad_id={self.unidad_id}>"
