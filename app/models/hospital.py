from app.extensions import db


class Hospital(db.Model):
    __tablename__ = "hospital"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False, unique=True)

    unidades = db.relationship("Unidad", back_populates="hospital", lazy="dynamic")

    def __repr__(self):
        return f"<Hospital {self.nombre}>"
