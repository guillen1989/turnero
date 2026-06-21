from app.extensions import db


class Pais(db.Model):
    __tablename__ = "pais"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False, unique=True)

    provincias = db.relationship("Provincia", back_populates="pais", lazy="dynamic")

    def __repr__(self):
        return f"<Pais {self.nombre}>"
