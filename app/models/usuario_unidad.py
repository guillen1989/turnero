from app.extensions import db


class UsuarioUnidad(db.Model):
    """Membresía de un usuario en una unidad distinta de su unidad principal
    (`Usuario.unidad_id`), con la categoría profesional específica que tiene
    en esa unidad (independiente de `Usuario.categoria_id`, la de la unidad
    principal)."""

    __tablename__ = "usuario_unidad"

    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), primary_key=True)
    unidad_id = db.Column(db.Integer, db.ForeignKey("unidad.id"), primary_key=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey("categoria.id"), nullable=False)

    usuario = db.relationship(
        "Usuario", back_populates="membresias_unidad", overlaps="miembros,unidades"
    )
    unidad = db.relationship(
        "Unidad", back_populates="membresias_unidad", overlaps="miembros"
    )
    categoria = db.relationship("Categoria")

    def __repr__(self):
        return f"<UsuarioUnidad usuario_id={self.usuario_id} unidad_id={self.unidad_id} categoria_id={self.categoria_id}>"
