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
    color = db.Column(db.String(7), nullable=True)

    grupo_intercambio = db.relationship("GrupoIntercambio", back_populates="franjas_horarias")

    __table_args__ = (
        db.UniqueConstraint(
            "nombre", "grupo_intercambio_id", name="uq_franja_nombre_grupo"
        ),
    )

    @property
    def color_texto(self):
        """'#ffffff' o '#1e293b' según la luminosidad del color de fondo."""
        c = self.color or "#3B82F6"
        r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
        luma = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return "#ffffff" if luma < 0.55 else "#1e293b"

    def __repr__(self):
        return f"<FranjaHoraria {self.nombre} ({self.hora_inicio}-{self.hora_fin})>"
