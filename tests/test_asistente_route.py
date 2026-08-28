"""Tests para la ruta POST /asistente/parsear."""
from types import SimpleNamespace
from unittest.mock import patch

from app.extensions import db as _db
from app.models import Categoria, ParseoAsistente, insertar_categorias_semilla
from app.services.asistente.cliente import ErrorAsistente
from app.services.asistente.schema import PropuestaPublicacion
from app.services.registro import registrar_usuario


def _login(client, email="u@test.es"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    u = registrar_usuario("Test", email, "pass1234", "H1", "Urgencias", cat.id)
    client.post("/auth/login", data={"email": email, "password": "pass1234"})
    return u


def _propuesta_valida():
    return PropuestaPublicacion(
        tipo="cambio",
        cedidos=[{"fecha": "2026-08-28", "franja": "Mañana"}],
        aceptados=[{"fecha": "2026-08-29", "franja": "Tarde"}],
        campos_faltantes=[],
    )


def test_parsear_requiere_login(client, db):
    resp = client.post("/asistente/parsear", data={"texto": "cambio turno"})
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_parsear_propuesta_valida_redirige_a_publicar_con_datos(client, db):
    _login(client)

    with patch("app.routes.asistente.extraer_propuesta", return_value=_propuesta_valida()):
        resp = client.post("/asistente/parsear", data={"texto": "cambio mi mañana del 28 por tu tarde del 29"},
                            follow_redirects=True)

    assert resp.status_code == 200
    assert b"2026-08-28" in resp.data
    assert b"2026-08-29" in resp.data


def test_parsear_propuesta_con_problemas_vuelve_a_formulario_vacio_con_aviso(client, db):
    _login(client)
    propuesta = PropuestaPublicacion(tipo="cambio", campos_faltantes=["franja de los aceptados"])

    with patch("app.routes.asistente.extraer_propuesta", return_value=propuesta):
        resp = client.post("/asistente/parsear", data={"texto": "cambio mi turno"}, follow_redirects=True)

    assert resp.status_code == 200
    assert b'id="prefill-asistente-data">{}</script>' in resp.data


def test_parsear_fallo_de_api_vuelve_a_formulario_vacio_sin_error_500(client, db):
    _login(client)

    with patch("app.routes.asistente.extraer_propuesta", side_effect=ErrorAsistente("boom")):
        resp = client.post("/asistente/parsear", data={"texto": "cambio mi turno"}, follow_redirects=True)

    assert resp.status_code == 200


def test_parsear_respeta_el_limite_diario_por_usuario(client, db, app):
    """El límite está desactivado temporalmente (LIMITE_PARSEOS_DIA_ACTIVO=False)
    mientras se prueba el asistente en staging; este test lo reactiva para
    seguir cubriendo la lógica de corte."""
    u = _login(client)
    with app.app_context():
        for _i in range(20):
            _db.session.add(ParseoAsistente(usuario_id=u.id))
        _db.session.commit()

    with patch("app.routes.asistente.LIMITE_PARSEOS_DIA_ACTIVO", True), \
         patch("app.routes.asistente.extraer_propuesta", return_value=_propuesta_valida()) as mock_extraer:
        resp = client.post("/asistente/parsear", data={"texto": "cambio mi turno"}, follow_redirects=True)

    assert resp.status_code == 200
    mock_extraer.assert_not_called()


def test_parsear_registra_log_de_auditoria_en_caso_exitoso(client, db, caplog):
    _login(client)

    with patch("app.routes.asistente.extraer_propuesta", return_value=_propuesta_valida()):
        with caplog.at_level("INFO", logger="asistente.parser"):
            client.post("/asistente/parsear", data={"texto": "cambio mi mañana del 28 por tu tarde del 29"})

    mensajes = [r.message for r in caplog.records]
    assert any("resultado=ok" in m and "cambio mi mañana del 28 por tu tarde del 29" in m for m in mensajes)


def test_parsear_registra_log_de_auditoria_cuando_hay_problemas(client, db, caplog):
    _login(client)
    propuesta = PropuestaPublicacion(tipo="cambio", campos_faltantes=["franja de los aceptados"])

    with patch("app.routes.asistente.extraer_propuesta", return_value=propuesta):
        with caplog.at_level("INFO", logger="asistente.parser"):
            client.post("/asistente/parsear", data={"texto": "cambio mi turno"})

    mensajes = [r.message for r in caplog.records]
    assert any("resultado=problemas" in m and "franja de los aceptados" in m for m in mensajes)


def test_parsear_registra_log_de_auditoria_cuando_falla_la_api(client, db, caplog):
    _login(client)

    with patch("app.routes.asistente.extraer_propuesta", side_effect=ErrorAsistente("boom")):
        with caplog.at_level("INFO", logger="asistente.parser"):
            client.post("/asistente/parsear", data={"texto": "cambio mi turno"})

    mensajes = [r.message for r in caplog.records]
    assert any("resultado=error_extraccion" in m and "boom" in m for m in mensajes)


def test_consejos_requiere_login(client, db):
    resp = client.get("/asistente/consejos")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_consejos_muestra_la_pantalla_de_consejos(client, db):
    _login(client)

    resp = client.get("/asistente/consejos")

    assert resp.status_code == 200
    assert "Consejos".encode() in resp.data



def _propuesta_aceptado_con_franja_desconocida():
    return PropuestaPublicacion(
        tipo="cambio",
        cedidos=[{"fecha": "2026-08-28", "franja": "Mañana"}],
        aceptados=[{"fecha": "2026-08-29", "franja": "Turno Fantasma"}],
        campos_faltantes=[],
    )


def test_parsear_con_problema_solo_en_aceptados_prellena_los_cedidos(client, db):
    _login(client)

    with patch("app.routes.asistente.extraer_propuesta", return_value=_propuesta_aceptado_con_franja_desconocida()):
        resp = client.post("/asistente/parsear", data={"texto": "cambio mi mañana del 28 por algo el 29"},
                            follow_redirects=True)

    assert resp.status_code == 200
    assert b"2026-08-28" in resp.data


def test_parsear_parcial_incluye_enlace_a_consejos_de_redaccion(client, db):
    _login(client)

    with patch("app.routes.asistente.extraer_propuesta", return_value=_propuesta_aceptado_con_franja_desconocida()):
        resp = client.post("/asistente/parsear", data={"texto": "cambio mi turno"}, follow_redirects=True)

    assert resp.status_code == 200
    assert b"/asistente/consejos" in resp.data
    assert "cómo redactar el mensaje".encode() in resp.data


def test_parsear_registra_log_de_auditoria_cuando_es_parcial(client, db, caplog):
    _login(client)

    with patch("app.routes.asistente.extraer_propuesta", return_value=_propuesta_aceptado_con_franja_desconocida()):
        with caplog.at_level("INFO", logger="asistente.parser"):
            client.post("/asistente/parsear", data={"texto": "cambio mi turno"})

    mensajes = [r.message for r in caplog.records]
    assert any("resultado=parcial" in m and "Turno Fantasma" in m for m in mensajes)
