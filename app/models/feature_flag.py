from app.extensions import db


class FeatureFlag(db.Model):
    __tablename__ = "feature_flag"

    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(80), unique=True, nullable=False)
    descripcion = db.Column(db.String(255), nullable=True)
    activo_global = db.Column(db.Boolean, nullable=False, default=False)

    unidades_habilitadas = db.relationship(
        "Unidad", secondary="feature_flag_unidad",
        back_populates="feature_flags_habilitados",
        overlaps="feature_flags_unidad",
    )

    def __repr__(self):
        return f"<FeatureFlag {self.clave}>"
