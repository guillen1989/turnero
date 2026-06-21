from app.extensions import db


class Provincia(db.Model):
    __tablename__ = "provincia"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    pais_id = db.Column(db.Integer, db.ForeignKey("pais.id"), nullable=False)

    pais = db.relationship("Pais", back_populates="provincias")
    ciudades = db.relationship("Ciudad", back_populates="provincia", lazy="dynamic")

    __table_args__ = (
        db.UniqueConstraint("nombre", "pais_id", name="uq_provincia_nombre_pais"),
    )

    def __repr__(self):
        return f"<Provincia {self.nombre}>"
