from app.extensions import db


class MapeoCodigoTurno(db.Model):
    """Traduce un código de turno tal como aparece en un archivo de planilla
    importado (p. ej. 'M', 'TC', 'D1') a la FranjaHoraria real de la app.
    Se configura una vez por grupo de intercambio y se reutiliza en cada
    carga mensual.
    """
    __tablename__ = "mapeo_codigo_turno"

    id = db.Column(db.Integer, primary_key=True)
    grupo_intercambio_id = db.Column(
        db.Integer, db.ForeignKey("grupo_intercambio.id"), nullable=False
    )
    codigo = db.Column(db.String(10), nullable=False)
    franja_horaria_id = db.Column(
        db.Integer, db.ForeignKey("franja_horaria.id"), nullable=False
    )

    grupo_intercambio = db.relationship("GrupoIntercambio")
    franja_horaria = db.relationship("FranjaHoraria")

    __table_args__ = (
        db.UniqueConstraint(
            "grupo_intercambio_id", "codigo", name="uq_mapeo_codigo_grupo_codigo"
        ),
    )

    def __repr__(self):
        return f"<MapeoCodigoTurno {self.codigo} -> franja={self.franja_horaria_id}>"


class MapeoTrabajadorPlanilla(db.Model):
    """Asocia de forma persistente a un trabajador tal como aparece en los
    archivos de planilla (identificado por su número de empleado, estable
    entre cargas mensuales) con su Usuario real en la app. usuario_id es
    nulo mientras el trabajador no tiene cuenta o no se ha confirmado la
    asociación.
    """
    __tablename__ = "mapeo_trabajador_planilla"

    id = db.Column(db.Integer, primary_key=True)
    unidad_id = db.Column(db.Integer, db.ForeignKey("unidad.id"), nullable=False)
    numero_empleado = db.Column(db.String(20), nullable=False)
    nombre_planilla = db.Column(db.String(200), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=True)

    unidad = db.relationship("Unidad")
    usuario = db.relationship("Usuario")

    __table_args__ = (
        db.UniqueConstraint(
            "unidad_id", "numero_empleado", name="uq_mapeo_trabajador_unidad_numero"
        ),
    )

    def __repr__(self):
        estado = f"usuario={self.usuario_id}" if self.usuario_id else "sin vincular"
        return f"<MapeoTrabajadorPlanilla {self.nombre_planilla} [{estado}]>"
