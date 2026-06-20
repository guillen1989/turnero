from app.extensions import db

CATEGORIAS_SEMILLA = [
    "Médico/a",
    "Enfermería",
    "Auxiliar de enfermería (TCAE)",
    "Celador/a",
    "Matrón/a",
    "Fisioterapeuta",
    "Técnico/a (laboratorio/radiología)",
    "Farmacéutico/a",
]


class Categoria(db.Model):
    __tablename__ = "categoria"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False, unique=True)

    def __repr__(self):
        return f"<Categoria {self.nombre}>"


def insertar_categorias_semilla():
    """Inserta las categorías predefinidas si no existen todavía."""
    for nombre in CATEGORIAS_SEMILLA:
        if not Categoria.query.filter_by(nombre=nombre).first():
            db.session.add(Categoria(nombre=nombre))
    db.session.commit()
