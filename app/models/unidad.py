from app.extensions import db


class Unidad(db.Model):
    __tablename__ = "unidad"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey("hospital.id"), nullable=False)
    grupo_intercambio_id = db.Column(db.Integer, db.ForeignKey("grupo_intercambio.id"), nullable=False)

    categoria_id = db.Column(db.Integer, db.ForeignKey("categoria.id"), nullable=True)

    hospital = db.relationship("Hospital", back_populates="unidades")
    grupo_intercambio = db.relationship("GrupoIntercambio", back_populates="unidades")
    categoria = db.relationship("Categoria")
    usuarios = db.relationship("Usuario", back_populates="unidad", lazy="dynamic")

    __table_args__ = (
        db.UniqueConstraint("nombre", "hospital_id", "categoria_id", name="uq_unidad_nombre_hospital_categoria"),
    )

    def __repr__(self):
        return f"<Unidad {self.nombre}>"
