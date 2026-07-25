from datetime import datetime, timezone

from app.extensions import db


class MatchCambio(db.Model):
    """
    Representa un acuerdo de cambio potencial entre 2 o más publicaciones.
    Diseñado para soportar cadenas de N bandas: match_participaciones puede
    tener 2 filas (directo) o N filas (cadena), sin cambiar este modelo.
    """
    __tablename__ = "match_cambio"

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False, default="directo_2")
    estado = db.Column(db.String(30), nullable=False, default="propuesto")
    # tipo:  directo_2 | cadena_3 | cadena_4 | cadena_n
    # estado: propuesto | confirmado_parcial | confirmado_total | rechazado | anulado
    # 'anulado': una supervisora deshizo un DocumentoCambio ya autorizado que
    # venía de este match (ver anular_documento) -- distinto de 'rechazado',
    # que es un rechazo previo a la confirmación, nunca llegó a resolver turnos.
    fecha_creacion = db.Column(
        db.DateTime, nullable=True, default=lambda: datetime.now(timezone.utc)
    )
    fecha_confirmacion_total = db.Column(db.DateTime, nullable=True)

    participaciones = db.relationship(
        "MatchParticipacion",
        back_populates="match",
        cascade="all, delete-orphan",
    )
    notificaciones = db.relationship("Notificacion", back_populates="match", lazy="dynamic")
    documento_cambio = db.relationship("DocumentoCambio", back_populates="match", uselist=False)

    def todas_confirmadas(self):
        return all(p.confirmado for p in self.participaciones)

    def __repr__(self):
        return f"<MatchCambio {self.id} [{self.tipo}/{self.estado}]>"


class MatchParticipacion(db.Model):
    """
    Una fila por publicación implicada en el match.
    En un match directo (2 bandas):
      - fila 1: publicacion A cede turno_cedido X (que B recibirá)
      - fila 2: publicacion B cede turno_cedido Y (que A recibirá)
    En una cadena de 3:
      - fila 1: A cede X → B
      - fila 2: B cede Y → C
      - fila 3: C cede Z → A
    """
    __tablename__ = "match_participacion"

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("match_cambio.id"), nullable=False)
    publicacion_id = db.Column(
        db.Integer, db.ForeignKey("publicacion_cambio.id"), nullable=False
    )
    turno_cedido_id = db.Column(
        db.Integer, db.ForeignKey("turno_cedido.id"), nullable=True
    )
    turno_aceptado_id = db.Column(
        db.Integer, db.ForeignKey("turno_aceptado.id"), nullable=True
    )
    confirmado = db.Column(db.Boolean, nullable=False, default=False)
    fecha_confirmacion = db.Column(db.DateTime, nullable=True)
    volcado_planilla = db.Column(db.Boolean, nullable=False, default=False, server_default="false")

    match = db.relationship("MatchCambio", back_populates="participaciones")
    publicacion = db.relationship("PublicacionCambio")
    turno_cedido = db.relationship("TurnoCedido", foreign_keys=[turno_cedido_id])
    turno_aceptado = db.relationship("TurnoAceptado", foreign_keys=[turno_aceptado_id])

    __table_args__ = (
        db.UniqueConstraint("match_id", "publicacion_id", name="uq_match_publicacion"),
    )

    def __repr__(self):
        return f"<MatchParticipacion match={self.match_id} pub={self.publicacion_id} confirmado={self.confirmado}>"
