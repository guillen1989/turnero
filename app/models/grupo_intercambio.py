from app.extensions import db


class GrupoIntercambio(db.Model):
    __tablename__ = "grupo_intercambio"

    id = db.Column(db.Integer, primary_key=True)

    unidades = db.relationship("Unidad", back_populates="grupo_intercambio", lazy="dynamic")

    def __repr__(self):
        return f"<GrupoIntercambio {self.id}>"
