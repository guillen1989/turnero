from app.extensions import db


class FranjaHoraria(db.Model):
    __tablename__ = "franja_horaria"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)
    grupo_intercambio_id = db.Column(
        db.Integer, db.ForeignKey("grupo_intercambio.id"), nullable=False
    )

    grupo_intercambio = db.relationship("GrupoIntercambio", back_populates="franjas_horarias")

    __table_args__ = (
        db.UniqueConstraint(
            "nombre", "grupo_intercambio_id", name="uq_franja_nombre_grupo"
        ),
    )

    def __repr__(self):
        return f"<FranjaHoraria {self.nombre} ({self.hora_inicio}-{self.hora_fin})>"
