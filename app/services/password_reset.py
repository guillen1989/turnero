import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import PasswordResetToken

TOKEN_TTL_MINUTOS = 60


def _hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generar_token_reset(usuario):
    """Crea un token de un solo uso para restablecer la contraseña de `usuario`.

    Invalida cualquier token anterior sin usar del mismo usuario, para que
    solo el enlace del email más reciente pueda usarse.
    """
    PasswordResetToken.query.filter_by(usuario_id=usuario.id, usado=False).update(
        {"usado": True}
    )

    token = secrets.token_urlsafe(32)
    ahora = datetime.now(timezone.utc)
    fila = PasswordResetToken(
        usuario_id=usuario.id,
        token_hash=_hash(token),
        fecha_creacion=ahora,
        fecha_expiracion=ahora + timedelta(minutes=TOKEN_TTL_MINUTOS),
        usado=False,
    )
    db.session.add(fila)
    db.session.commit()
    return token


def _fila_valida(token):
    fila = PasswordResetToken.query.filter_by(token_hash=_hash(token)).first()
    if fila is None or fila.usado:
        return None
    if fila.fecha_expiracion < datetime.now(timezone.utc):
        return None
    return fila


def obtener_usuario_por_token(token):
    """Devuelve el Usuario dueño de un token válido (no usado, no expirado), o None."""
    fila = _fila_valida(token)
    return fila.usuario if fila else None


def consumir_token(token):
    """Marca el token como usado, para que no pueda reutilizarse."""
    fila = PasswordResetToken.query.filter_by(token_hash=_hash(token)).first()
    if fila is None:
        return
    fila.usado = True
    db.session.commit()
