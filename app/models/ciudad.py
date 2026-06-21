from app.extensions import db


class Ciudad(db.Model):
    __tablename__ = "ciudad"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    provincia_id = db.Column(db.Integer, db.ForeignKey("provincia.id"), nullable=False)

    provincia = db.relationship("Provincia", back_populates="ciudades")
    hospitales = db.relationship("Hospital", back_populates="ciudad", lazy="dynamic")

    __table_args__ = (
        db.UniqueConstraint("nombre", "provincia_id", name="uq_ciudad_nombre_provincia"),
    )

    def __repr__(self):
        return f"<Ciudad {self.nombre}>"
