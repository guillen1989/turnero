"""Tests para el comando flask broadcast-push."""
from unittest.mock import patch

from app.models import Categoria, insertar_categorias_semilla
from app.services.registro import registrar_usuario


def _categoria():
    insertar_categorias_semilla()
    return Categoria.query.filter_by(nombre="Enfermería").first()


def _usuario(nombre, email, con_suscripcion=True, push_activo=True):
    cat = _categoria()
    usuario = registrar_usuario(nombre, email, "pw", "HospitalX", "UrgenciasX", cat.id)
    usuario.push_subscription = '{"endpoint": "https://push.example/x"}' if con_suscripcion else None
    usuario.push_activo = push_activo
    from app.extensions import db
    db.session.commit()
    return usuario


def test_broadcast_push_envia_a_usuarios_suscritos_con_push_activo(app):
    ana = _usuario("Ana", "ana@broadcast.es")
    pedro = _usuario("Pedro", "pedro@broadcast.es", con_suscripcion=False)
    lucia = _usuario("Lucía", "lucia@broadcast.es", push_activo=False)

    runner = app.test_cli_runner()
    with patch("app.push.sender.enviar_push") as mock_enviar:
        result = runner.invoke(args=["broadcast-push", "Título", "Cuerpo del mensaje"])

    assert result.exit_code == 0, result.output
    assert mock_enviar.call_count == 1
    enviado_a = mock_enviar.call_args.args[0]
    assert enviado_a.id == ana.id
    assert "Notificaciones enviadas: 1" in result.output


def test_broadcast_push_usa_titulo_y_cuerpo_dados(app):
    ana = _usuario("Ana", "ana2@broadcast.es")

    runner = app.test_cli_runner()
    with patch("app.push.sender.enviar_push") as mock_enviar:
        runner.invoke(args=["broadcast-push", "Turnero", "Mensaje de prueba"])

    mock_enviar.assert_called_once_with(ana, "Turnero", "Mensaje de prueba", url="/avisos")
