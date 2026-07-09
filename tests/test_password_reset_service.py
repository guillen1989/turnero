"""Tests del servicio de recuperación de contraseña: lógica pura, sin HTTP."""
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import Categoria, PasswordResetToken, insertar_categorias_semilla
from app.services.registro import registrar_usuario
from app.services.password_reset import (
    generar_token_reset,
    obtener_usuario_por_token,
    consumir_token,
)


def _usuario(email="u@test.es"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario("Test", email, "pass_original", "H", "U", cat.id)


def test_generar_token_reset_crea_fila_en_bd(db):
    usuario = _usuario()

    token = generar_token_reset(usuario)

    assert isinstance(token, str) and len(token) > 20
    assert PasswordResetToken.query.filter_by(usuario_id=usuario.id).count() == 1


def test_generar_token_reset_no_guarda_el_token_en_claro(db):
    usuario = _usuario()

    token = generar_token_reset(usuario)

    fila = PasswordResetToken.query.filter_by(usuario_id=usuario.id).first()
    assert fila.token_hash != token


def test_obtener_usuario_por_token_valido(db):
    usuario = _usuario()
    token = generar_token_reset(usuario)

    encontrado = obtener_usuario_por_token(token)

    assert encontrado is not None
    assert encontrado.id == usuario.id


def test_obtener_usuario_por_token_inexistente_devuelve_none(db):
    assert obtener_usuario_por_token("token-que-no-existe") is None


def test_obtener_usuario_por_token_expirado_devuelve_none(db):
    usuario = _usuario()
    token = generar_token_reset(usuario)
    fila = PasswordResetToken.query.filter_by(usuario_id=usuario.id).first()
    fila.fecha_expiracion = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.session.commit()

    assert obtener_usuario_por_token(token) is None


def test_obtener_usuario_por_token_usado_devuelve_none(db):
    usuario = _usuario()
    token = generar_token_reset(usuario)
    consumir_token(token)

    assert obtener_usuario_por_token(token) is None


def test_consumir_token_marca_usado(db):
    usuario = _usuario()
    token = generar_token_reset(usuario)

    consumir_token(token)

    fila = PasswordResetToken.query.filter_by(usuario_id=usuario.id).first()
    assert fila.usado is True


def test_generar_token_reset_invalida_tokens_previos_del_mismo_usuario(db):
    usuario = _usuario()
    token_viejo = generar_token_reset(usuario)
    token_nuevo = generar_token_reset(usuario)

    assert obtener_usuario_por_token(token_viejo) is None
    assert obtener_usuario_por_token(token_nuevo) is not None
