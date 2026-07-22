from datetime import datetime, timezone

from flask_babel import lazy_gettext as _l

from app.extensions import db

TIPOS_ESTADO_DIA = ("libre", "vacaciones", "no_disponible")

ETIQUETAS_ESTADO = {
    "libre": _l("Libre"),
    "vacaciones": _l("Vacaciones"),
    "no_disponible": _l("No disponible para cambios"),
}


class EstadoDiaPlanilla(db.Model):
    """Marca un día como Libre / Vacaciones / No Disponible para Cambios.
    Mutuamente exclusivo con TurnoPlanilla: un día tiene estado O turnos, nunca ambos.
    """
    __tablename__ = "estado_dia_planilla"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # libre | vacaciones | no_disponible

    usuario = db.relationship("Usuario", back_populates="estados_dia_planilla")

    __table_args__ = (
        db.UniqueConstraint("usuario_id", "fecha", name="uq_estado_dia_usuario_fecha"),
    )

    def __repr__(self):
        return f"<EstadoDiaPlanilla {self.fecha} [{self.tipo}]>"


class CompatibilidadPlanilla(db.Model):
    """Resultado persistido de cruzar una publicación con las planillas de compañeros.
    Una fila por (publicacion, usuario_compatible). Se recalcula cuando cambia la planilla
    del usuario o cuando el usuario publica un nuevo cambio.
    """
    __tablename__ = "compatibilidad_planilla"

    id = db.Column(db.Integer, primary_key=True)
    publicacion_id = db.Column(
        db.Integer, db.ForeignKey("publicacion_cambio.id", ondelete="CASCADE"), nullable=False
    )
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    # 'libre' tiene prioridad sobre 'compatible' si el usuario aparece en varias fechas
    tipo = db.Column(db.String(20), nullable=False)

    usuario = db.relationship("Usuario")
    publicacion = db.relationship("PublicacionCambio")

    __table_args__ = (
        db.UniqueConstraint(
            "publicacion_id", "usuario_id", name="uq_compat_planilla_pub_usuario"
        ),
    )

    def __repr__(self):
        return f"<CompatibilidadPlanilla pub={self.publicacion_id} u={self.usuario_id} [{self.tipo}]>"


class TurnoPlanilla(db.Model):
    __tablename__ = "turno_planilla"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    franja_horaria_id = db.Column(
        db.Integer, db.ForeignKey("franja_horaria.id"), nullable=False
    )

    usuario = db.relationship("Usuario", back_populates="turnos_planilla")
    franja_horaria = db.relationship("FranjaHoraria")

    # Permite doblajes (varias franjas el mismo día) pero impide duplicar la misma franja
    __table_args__ = (
        db.UniqueConstraint(
            "usuario_id", "fecha", "franja_horaria_id",
            name="uq_turno_planilla_usuario_fecha_franja",
        ),
    )

    def __repr__(self):
        return f"<TurnoPlanilla {self.fecha} franja={self.franja_horaria_id}>"


class PlanillaMes(db.Model):
    __tablename__ = "planilla_mes"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    anyo = db.Column(db.Integer, nullable=False)
    mes = db.Column(db.Integer, nullable=False)
    publicada = db.Column(db.Boolean, nullable=False, default=False)

    usuario = db.relationship("Usuario", back_populates="planillas_mes")

    __table_args__ = (
        db.UniqueConstraint("usuario_id", "anyo", "mes", name="uq_planilla_mes_usuario"),
    )

    def __repr__(self):
        estado = "publicada" if self.publicada else "borrador"
        return f"<PlanillaMes {self.anyo}-{self.mes:02d} [{estado}]>"


class SalienteDia(db.Model):
    """Marca que el usuario es saliente en esa fecha (día posterior a un turno de noche).
    Independiente de EstadoDiaPlanilla y TurnoPlanilla: puede coexistir con turnos (doblaje).
    Los salientes no hacen match con ofertas de mañana o Diurno (hora_inicio < 12:00).
    """
    __tablename__ = "saliente_dia"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    fecha = db.Column(db.Date, nullable=False)

    usuario = db.relationship("Usuario", back_populates="salientes_dia")

    __table_args__ = (
        db.UniqueConstraint("usuario_id", "fecha", name="uq_saliente_dia_usuario_fecha"),
    )

    def __repr__(self):
        return f"<SalienteDia {self.fecha}>"


class NotaDia(db.Model):
    """Nota libre del usuario para un día concreto de su planilla."""
    __tablename__ = "nota_dia"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    texto = db.Column(db.Text, nullable=False, default="")

    usuario = db.relationship("Usuario", back_populates="notas_dia")

    __table_args__ = (
        db.UniqueConstraint("usuario_id", "fecha", name="uq_nota_dia_usuario_fecha"),
    )

    def __repr__(self):
        return f"<NotaDia {self.fecha}>"


class AjustePlanillaSupervisora(db.Model):
    """Rastro de auditoría de una modificación unilateral de la supervisora
    sobre el turno/estado del día de un trabajador (p. ej. asignarle un día
    libre). No encaja en ParticipanteDocumentoCambio porque aquí no hay dos
    partes que se ceden turno entre sí -- por eso necesita su propio registro.
    """
    __tablename__ = "ajuste_planilla_supervisora"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    realizado_por_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    descripcion_anterior = db.Column(db.String(200), nullable=False)
    descripcion_nueva = db.Column(db.String(200), nullable=False)
    motivo = db.Column(db.Text, nullable=True)
    fecha_creacion = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    usuario = db.relationship("Usuario", foreign_keys=[usuario_id])
    realizado_por = db.relationship("Usuario", foreign_keys=[realizado_por_id])

    def __repr__(self):
        return f"<AjustePlanillaSupervisora usuario={self.usuario_id} fecha={self.fecha}>"
