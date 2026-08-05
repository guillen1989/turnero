from app.extensions import db


class FeatureFlagUnidad(db.Model):
    """N:M entre un flag y las unidades donde está habilitado aunque
    activo_global sea False. Mismo patrón que UnidadSupervisada."""

    __tablename__ = "feature_flag_unidad"

    feature_flag_id = db.Column(db.Integer, db.ForeignKey("feature_flag.id"), primary_key=True)
    unidad_id = db.Column(db.Integer, db.ForeignKey("unidad.id"), primary_key=True)

    unidad = db.relationship(
        "Unidad", back_populates="feature_flags_unidad",
        overlaps="feature_flags_habilitados,unidades_habilitadas,feature_flags_unidad",
    )

    def __repr__(self):
        return f"<FeatureFlagUnidad feature_flag_id={self.feature_flag_id} unidad_id={self.unidad_id}>"
