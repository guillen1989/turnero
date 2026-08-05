from app.extensions import db


class Unidad(db.Model):
    __tablename__ = "unidad"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey("hospital.id"), nullable=False)
    grupo_intercambio_id = db.Column(db.Integer, db.ForeignKey("grupo_intercambio.id"), nullable=False, index=True)

    categoria_id = db.Column(db.Integer, db.ForeignKey("categoria.id"), nullable=True)

    hospital = db.relationship("Hospital", back_populates="unidades")
    grupo_intercambio = db.relationship("GrupoIntercambio", back_populates="unidades")
    categoria = db.relationship("Categoria")
    usuarios = db.relationship("Usuario", back_populates="unidad", lazy="dynamic")
    supervisoras = db.relationship(
        "Usuario", secondary="unidad_supervisada", back_populates="unidades_supervisadas"
    )
    miembros = db.relationship(
        "Usuario", secondary="usuario_unidad", back_populates="unidades",
        overlaps="membresias_unidad",
    )
    membresias_unidad = db.relationship(
        "UsuarioUnidad", back_populates="unidad", overlaps="miembros",
        cascade="all, delete-orphan",
    )
    supervisoras_rel = db.relationship(
        "UnidadSupervisada", back_populates="unidad", cascade="all, delete-orphan",
        overlaps="supervisoras,unidades_supervisadas",
    )
    feature_flags_unidad = db.relationship(
        "FeatureFlagUnidad", back_populates="unidad", cascade="all, delete-orphan",
        overlaps="feature_flags_habilitados",
    )
    feature_flags_habilitados = db.relationship(
        "FeatureFlag", secondary="feature_flag_unidad",
        back_populates="unidades_habilitadas", viewonly=True,
        overlaps="feature_flags_unidad",
    )

    __table_args__ = (
        db.UniqueConstraint("nombre", "hospital_id", "categoria_id", name="uq_unidad_nombre_hospital_categoria"),
    )

    def __repr__(self):
        return f"<Unidad {self.nombre}>"
