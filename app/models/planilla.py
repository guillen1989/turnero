from app.extensions import db

TIPOS_ESTADO_DIA = ("libre", "vacaciones", "no_disponible")


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
