from datetime import datetime, timezone

from app.extensions import db


class BusquedaGuardada(db.Model):
    __tablename__ = "busqueda_guardada"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    nombre = db.Column(db.String(100), nullable=True)
    filtros = db.Column(db.JSON, nullable=False)
    creada_en = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    usuario = db.relationship("Usuario", back_populates="busquedas_guardadas")

    @property
    def url_params(self):
        """Returns URL params dict for applying this search in /cambios."""
        params = {}
        for filtro_key, url_key in [
            ("mes", "mes"),
            ("dia", "dia"),
            ("franja_id", "franja"),
            ("tipo", "tipo"),
            ("nombre", "usuario"),
            ("tipo_fecha", "tipo_fecha"),
        ]:
            v = self.filtros.get(filtro_key)
            if v:
                params[url_key] = v
        return params
