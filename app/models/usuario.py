from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db, login_manager


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuario"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(254), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    unidad_id = db.Column(db.Integer, db.ForeignKey("unidad.id"), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey("categoria.id"), nullable=False, index=True)
    locale = db.Column(db.String(10), nullable=False, default="es")
    push_subscription = db.Column(db.Text, nullable=True)
    push_activo = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    notif_match = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    notif_confirmacion_parcial = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    notif_confirmado_total = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    notif_publicacion = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    notif_busqueda_guardada = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    notif_email_documento_cambio = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    mostrar_oportunidad_3 = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    mostrar_oportunidad_4 = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    mostrar_disponibilidad = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    es_admin = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    es_supervisora = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    onboarding_visto = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    firma_guardada = db.Column(db.Text, nullable=True)
    fecha_registro = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    unidad = db.relationship("Unidad", back_populates="usuarios")
    categoria = db.relationship("Categoria", back_populates="usuarios")
    publicaciones = db.relationship("PublicacionCambio", back_populates="usuario", lazy="dynamic")
    notificaciones = db.relationship("Notificacion", back_populates="usuario", lazy="dynamic")
    suscripciones = db.relationship(
        "SuscripcionPublicaciones",
        foreign_keys="SuscripcionPublicaciones.suscriptor_id",
        backref="suscriptor",
        lazy="dynamic",
    )
    suscriptores_pub = db.relationship(
        "SuscripcionPublicaciones",
        foreign_keys="SuscripcionPublicaciones.publicador_id",
        backref="publicador",
        lazy="dynamic",
    )
    busquedas_guardadas = db.relationship(
        "BusquedaGuardada", back_populates="usuario", lazy="dynamic"
    )
    turnos_planilla = db.relationship(
        "TurnoPlanilla", back_populates="usuario", lazy="dynamic"
    )
    planillas_mes = db.relationship(
        "PlanillaMes", back_populates="usuario", lazy="dynamic"
    )
    estados_dia_planilla = db.relationship(
        "EstadoDiaPlanilla", back_populates="usuario", lazy="dynamic"
    )
    notas_dia = db.relationship(
        "NotaDia", back_populates="usuario", lazy="dynamic"
    )
    salientes_dia = db.relationship(
        "SalienteDia", back_populates="usuario", lazy="dynamic"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def grupo_intercambio(self):
        return self.unidad.grupo_intercambio

    @property
    def es_demo(self):
        return (
            self.email.endswith("@demo.turnero.com")
            or self.email in ("demo1@turnero.com", "demo2@turnero.com", "demo3@turnero.com")
        )

    @property
    def eliminado(self):
        return self.password_hash == "CUENTA_ELIMINADA"

    def __repr__(self):
        return f"<Usuario {self.email}>"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))
