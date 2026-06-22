from app.extensions import db


class SuscripcionPublicaciones(db.Model):
    __tablename__ = "suscripcion_publicaciones"

    id = db.Column(db.Integer, primary_key=True)
    suscriptor_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    publicador_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("suscriptor_id", "publicador_id", name="uq_suscripcion"),
    )
