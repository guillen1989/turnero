from datetime import datetime, timezone
from sqlalchemy import event as sa_event
from app.extensions import db

ESTADOS_PUBLICACION = ("abierta", "parcialmente_resuelta", "confirmada", "cancelada", "caducada")
ESTADOS_TURNO_CEDIDO = ("abierto", "resuelto")
TIPOS_PUBLICACION = ("cambio", "regalo", "peticion", "junte", "cambio_dia")

_ESTADOS_CERRADO = frozenset(("confirmada", "cancelada", "caducada"))


class PublicacionCambio(db.Model):
    __tablename__ = "publicacion_cambio"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False, index=True)
    fecha_creacion = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    estado = db.Column(db.String(30), nullable=False, default="abierta", index=True)
    fecha_cierre = db.Column(db.DateTime, nullable=True)
    tipo = db.Column(db.String(20), nullable=False, default="cambio", index=True)
    mensaje = db.Column(db.String(200), nullable=True)
    es_sintetica = db.Column(db.Boolean, nullable=False, default=False, index=True)
    sintetica_pub_a_id = db.Column(
        db.Integer, db.ForeignKey("publicacion_cambio.id"), nullable=True
    )
    sintetica_pub_b_id = db.Column(
        db.Integer, db.ForeignKey("publicacion_cambio.id"), nullable=True
    )
    sintetica_pub_intermedio_id = db.Column(
        db.Integer, db.ForeignKey("publicacion_cambio.id"), nullable=True
    )
    # sintetica_pub_intermedio_id solo se usa en sintéticas de cadena_4: es la
    # banda real "B" del trío A→B→C ya cerrado, que la sintética completa
    # haciendo de "D" (C→D→A). En sintéticas de cadena_3 queda NULL.

    usuario = db.relationship("Usuario", back_populates="publicaciones")
    turnos_cedidos = db.relationship(
        "TurnoCedido", back_populates="publicacion", cascade="all, delete-orphan"
    )
    turnos_aceptados = db.relationship(
        "TurnoAceptado", back_populates="publicacion", cascade="all, delete-orphan"
    )

    def esta_activa(self):
        return self.estado in ("abierta", "parcialmente_resuelta")

    def actualizar_estado(self):
        """Recalcula el estado en función de los turnos cedidos pendientes.

        Para regalo/peticion: no hay resolución parcial, el estado lo gestiona
        confirmar_participacion directamente.
        """
        if self.tipo in ("regalo", "peticion"):
            return

        abiertos = sum(1 for t in self.turnos_cedidos if t.estado == "abierto")
        total = len(self.turnos_cedidos)

        if abiertos == total:
            self.estado = "abierta"
        elif abiertos == 0:
            self.estado = "confirmada"
        else:
            self.estado = "parcialmente_resuelta"

    def __repr__(self):
        return f"<PublicacionCambio {self.id} [{self.estado}]>"


class TurnoCedido(db.Model):
    __tablename__ = "turno_cedido"

    id = db.Column(db.Integer, primary_key=True)
    publicacion_id = db.Column(
        db.Integer, db.ForeignKey("publicacion_cambio.id"), nullable=False
    )
    fecha = db.Column(db.Date, nullable=False)
    franja_horaria_id = db.Column(
        db.Integer, db.ForeignKey("franja_horaria.id"), nullable=False
    )
    estado = db.Column(db.String(20), nullable=False, default="abierto")

    publicacion = db.relationship("PublicacionCambio", back_populates="turnos_cedidos")
    franja_horaria = db.relationship("FranjaHoraria")

    def __repr__(self):
        return f"<TurnoCedido {self.fecha} franja={self.franja_horaria_id} [{self.estado}]>"


class TurnoAceptado(db.Model):
    __tablename__ = "turno_aceptado"

    id = db.Column(db.Integer, primary_key=True)
    publicacion_id = db.Column(
        db.Integer, db.ForeignKey("publicacion_cambio.id"), nullable=False
    )
    fecha = db.Column(db.Date, nullable=False)
    franja_horaria_id = db.Column(
        db.Integer, db.ForeignKey("franja_horaria.id"), nullable=True
    )
    cualquier_franja = db.Column(db.Boolean, nullable=False, default=False)
    estado = db.Column(db.String(20), nullable=False, default="abierto")

    publicacion = db.relationship("PublicacionCambio", back_populates="turnos_aceptados")
    franja_horaria = db.relationship("FranjaHoraria")

    def __repr__(self):
        return f"<TurnoAceptado {self.fecha} franja={self.franja_horaria_id} [{self.estado}]>"


@sa_event.listens_for(PublicacionCambio.estado, "set")
def _auto_fecha_cierre(target, value, oldvalue, initiator):
    """Sella fecha_cierre la primera vez que el estado pasa a un estado cerrado."""
    if value in _ESTADOS_CERRADO and target.fecha_cierre is None:
        target.fecha_cierre = datetime.now(timezone.utc)
