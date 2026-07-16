from datetime import datetime, timezone

from app.extensions import db

ESTADOS_DOCUMENTO_CAMBIO = ("borrador", "pendiente_firmas", "completo", "caducado")
ESTADOS_FACTIBILIDAD = ("no_verificado", "factible", "no_factible")
ESTADOS_DECISION_SUPERVISORA = ("pendiente", "autorizado", "denegado")


class DocumentoCambio(db.Model):
    """
    Hoja de cambio de turno digital (equivalente al impreso en papel que
    firman los dos trabajadores implicados).

    match_id es nullable a propósito: en la fase manual (datos introducidos
    a mano) no hay ningún MatchCambio de por medio; cuando el motor de
    matching genere el documento automáticamente, se enlazará aquí sin
    tener que rediseñar el modelo.
    """
    __tablename__ = "documento_cambio"

    id = db.Column(db.Integer, primary_key=True)
    estado = db.Column(db.String(20), nullable=False, default="borrador")
    fecha_creacion = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    creado_por_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    match_id = db.Column(db.Integer, db.ForeignKey("match_cambio.id"), nullable=True)
    # Unidad de quien crea el documento (congelada en el momento de crearlo,
    # igual que en el impreso de papel). Determina el ámbito de numero_unidad:
    # cada unidad lleva su propia numeración, como hacía la ayudante a mano.
    unidad_id = db.Column(db.Integer, db.ForeignKey("unidad.id"), nullable=False)
    # Número secuencial dentro de esa unidad (1, 2, 3...), no el id
    # autoincremental de Postgres (compartido por toda la app).
    numero_unidad = db.Column(db.Integer, nullable=False)
    # 'no_verificado': falta la planilla publicada de algún participante para
    # poder comprobarlo. server_default porque documento_cambio ya tiene filas
    # reales en staging (probadas manualmente por el usuario) -- ver CLAUDE.md,
    # columnas NOT NULL sin server_default fallan en una tabla ya poblada.
    factibilidad_estado = db.Column(
        db.String(20), nullable=False, default="no_verificado", server_default="no_verificado"
    )
    # Decisión de la supervisora sobre un documento ya completo (dos firmas).
    # Solo si queda 'autorizado' se vuelca el cambio a las planillas de los
    # implicados -- mientras esté 'pendiente' o si queda 'denegado', las
    # planillas no se tocan. server_default por la misma razón que
    # factibilidad_estado (filas ya existentes en producción).
    decision_supervisora = db.Column(
        db.String(20), nullable=False, default="pendiente", server_default="pendiente"
    )
    supervisora_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=True)
    fecha_decision_supervisora = db.Column(db.DateTime(timezone=True), nullable=True)
    # Solo se rellena al denegar; los participantes deben poder ver por qué.
    motivo_denegacion = db.Column(db.Text, nullable=True)

    creado_por = db.relationship("Usuario", foreign_keys=[creado_por_id])
    supervisora = db.relationship("Usuario", foreign_keys=[supervisora_id])
    unidad = db.relationship("Unidad")
    match = db.relationship("MatchCambio")
    participantes = db.relationship(
        "ParticipanteDocumentoCambio",
        back_populates="documento",
        cascade="all, delete-orphan",
    )
    firmas = db.relationship(
        "FirmaDocumentoCambio",
        back_populates="documento",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.UniqueConstraint("unidad_id", "numero_unidad", name="uq_documento_unidad_numero"),
    )

    def todos_han_firmado(self) -> bool:
        ids_participantes = {p.usuario_id for p in self.participantes}
        if not ids_participantes:
            return False
        ids_firmantes = {f.usuario_id for f in self.firmas}
        return ids_participantes.issubset(ids_firmantes)

    def __repr__(self):
        return f"<DocumentoCambio {self.id} [{self.estado}]>"


class ParticipanteDocumentoCambio(db.Model):
    """
    Una fila por trabajador implicado en el documento: qué turno cede y qué
    turno recibe a cambio. No depende de PublicacionCambio/TurnoCedido
    porque en la fase manual no existe ninguna publicación de por medio.
    """
    __tablename__ = "participante_documento_cambio"

    id = db.Column(db.Integer, primary_key=True)
    documento_id = db.Column(
        db.Integer, db.ForeignKey("documento_cambio.id"), nullable=False
    )
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    turno_cede_fecha = db.Column(db.Date, nullable=False)
    turno_cede_franja_id = db.Column(
        db.Integer, db.ForeignKey("franja_horaria.id"), nullable=False
    )
    turno_recibe_fecha = db.Column(db.Date, nullable=False)
    turno_recibe_franja_id = db.Column(
        db.Integer, db.ForeignKey("franja_horaria.id"), nullable=False
    )

    documento = db.relationship("DocumentoCambio", back_populates="participantes")
    usuario = db.relationship("Usuario")
    turno_cede_franja = db.relationship(
        "FranjaHoraria", foreign_keys=[turno_cede_franja_id]
    )
    turno_recibe_franja = db.relationship(
        "FranjaHoraria", foreign_keys=[turno_recibe_franja_id]
    )

    __table_args__ = (
        db.UniqueConstraint(
            "documento_id", "usuario_id", name="uq_participante_documento_usuario"
        ),
    )

    def __repr__(self):
        return f"<ParticipanteDocumentoCambio doc={self.documento_id} usuario={self.usuario_id}>"


class FirmaDocumentoCambio(db.Model):
    """
    Una fila por firma recogida. imagen_firma guarda el trazo dibujado
    (data URI); hash_documento es la huella del contenido exacto firmado,
    para poder demostrar qué se firmó aunque la plantilla cambie después.
    """
    __tablename__ = "firma_documento_cambio"

    id = db.Column(db.Integer, primary_key=True)
    documento_id = db.Column(
        db.Integer, db.ForeignKey("documento_cambio.id"), nullable=False
    )
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    fecha_firma = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    imagen_firma = db.Column(db.Text, nullable=False)
    hash_documento = db.Column(db.String(64), nullable=False)

    documento = db.relationship("DocumentoCambio", back_populates="firmas")
    usuario = db.relationship("Usuario")

    __table_args__ = (
        db.UniqueConstraint(
            "documento_id", "usuario_id", name="uq_firma_documento_usuario"
        ),
    )

    def __repr__(self):
        return f"<FirmaDocumentoCambio doc={self.documento_id} usuario={self.usuario_id}>"
