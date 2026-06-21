from app.extensions import db


class Hospital(db.Model):
    __tablename__ = "hospital"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    ciudad_id = db.Column(db.Integer, db.ForeignKey("ciudad.id"), nullable=True)

    ciudad = db.relationship("Ciudad", back_populates="hospitales")
    unidades = db.relationship("Unidad", back_populates="hospital", lazy="dynamic")

    __table_args__ = (
        db.UniqueConstraint("nombre", "ciudad_id", name="uq_hospital_nombre_ciudad"),
    )

    def __repr__(self):
        return f"<Hospital {self.nombre}>"
