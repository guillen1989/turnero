"""Tests para la ruta /feedback (formulario de contacto)."""
from unittest.mock import patch

from app.extensions import db as _db
from app.models import Categoria, Feedback, Notificacion, Usuario, insertar_categorias_semilla
from app.services.registro import registrar_usuario


def _login(client, email="u@test.es", es_admin=False):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    u = registrar_usuario("Test", email, "pass1234", "H", "U", cat.id)
    if es_admin:
        u.es_admin = True
        _db.session.commit()
    client.post("/auth/login", data={"email": email, "password": "pass1234"})
    return u


# --- GET ---

def test_get_feedback_anonimo_devuelve_200(client, db):
    resp = client.get("/feedback")
    assert resp.status_code == 200
    assert b"feedback" in resp.data.lower() or b"error" in resp.data.lower() or b"suger" in resp.data.lower()


def test_get_feedback_prerellena_email_si_autenticado(client, db):
    _login(client)
    resp = client.get("/feedback")
    assert b"u@test.es" in resp.data


# --- POST válido ---

def test_post_feedback_valido_redirige(client, db):
    resp = client.post("/feedback", data={
        "tipo": "error",
        "descripcion": "La app no carga en Safari.",
        "email_contacto": "usuario@test.es",
    }, follow_redirects=False)
    assert resp.status_code == 302


def test_post_feedback_valido_guarda_en_bd(client, db):
    client.post("/feedback", data={
        "tipo": "sugerencia",
        "descripcion": "Añadir filtro por fecha.",
        "email_contacto": "usuario@test.es",
    })
    fb = Feedback.query.first()
    assert fb is not None
    assert fb.tipo == "sugerencia"
    assert fb.descripcion == "Añadir filtro por fecha."
    assert fb.email_contacto == "usuario@test.es"


def test_post_feedback_autenticado_guarda_usuario_id(client, db):
    u = _login(client)
    client.post("/feedback", data={
        "tipo": "error",
        "descripcion": "Error de prueba.",
        "email_contacto": "",
    })
    fb = Feedback.query.first()
    assert fb.usuario_id == u.id


def test_post_feedback_valido_flash_confirmacion(client, db):
    resp = client.post("/feedback", data={
        "tipo": "sugerencia",
        "descripcion": "Añadir filtro por fecha.",
        "email_contacto": "usuario@test.es",
    }, follow_redirects=True)
    assert "Gracias" in resp.data.decode()


# --- POST inválido ---

def test_post_feedback_sin_descripcion_vuelve_al_form(client, db):
    resp = client.post("/feedback", data={
        "tipo": "error",
        "descripcion": "",
        "email_contacto": "usuario@test.es",
    })
    assert resp.status_code == 200
    assert Feedback.query.count() == 0


def test_post_feedback_sin_tipo_vuelve_al_form(client, db):
    resp = client.post("/feedback", data={
        "tipo": "",
        "descripcion": "Descripción válida.",
        "email_contacto": "usuario@test.es",
    })
    assert resp.status_code == 200
    assert Feedback.query.count() == 0


def test_post_feedback_tipo_invalido_vuelve_al_form(client, db):
    resp = client.post("/feedback", data={
        "tipo": "malicioso",
        "descripcion": "Descripción válida.",
        "email_contacto": "",
    })
    assert resp.status_code == 200
    assert Feedback.query.count() == 0


# --- Campo leido ---

def test_nuevo_feedback_tiene_leido_false(client, db):
    """Los mensajes nuevos se crean con leido=False."""
    client.post("/feedback", data={
        "tipo": "error",
        "descripcion": "La app no carga en Safari.",
        "email_contacto": "",
    })
    fb = Feedback.query.first()
    assert fb.leido is False



# --- Panel de feedback del admin ---

def _post_feedback(client, tipo="error", descripcion="Descripción de prueba."):
    client.post("/feedback", data={
        "tipo": tipo,
        "descripcion": descripcion,
        "email_contacto": "",
    })
    return Feedback.query.order_by(Feedback.id.desc()).first()


def test_admin_feedback_sin_leer_contiene_nuevos(client, db):
    """El panel admin muestra los mensajes nuevos en la pestaña sin leer."""
    _login(client, email="admin@test.es", es_admin=True)
    _post_feedback(client)
    resp = client.get("/admin/feedback")
    assert resp.status_code == 200
    assert b"sin_leer" in resp.data or "Descripción de prueba.".encode() in resp.data


def test_admin_marcar_leido(client, db):
    """El admin puede marcar un mensaje como leído."""
    _login(client, email="admin@test.es", es_admin=True)
    fb = _post_feedback(client)
    assert fb.leido is False

    resp = client.post(f"/admin/feedback/{fb.id}/marcar-leido", follow_redirects=False)
    assert resp.status_code == 302

    _db.session.refresh(fb)
    assert fb.leido is True


def test_admin_marcar_leido_mueve_a_pestana_leidos(client, db):
    """Un mensaje marcado como leído aparece en la pestaña de leídos."""
    _login(client, email="admin@test.es", es_admin=True)
    fb = _post_feedback(client)
    client.post(f"/admin/feedback/{fb.id}/marcar-leido")

    resp = client.get("/admin/feedback?tab=leidos")
    assert resp.status_code == 200
    assert "Descripción de prueba.".encode() in resp.data


def test_admin_feedback_requiere_admin(client, db):
    """Un usuario normal no puede acceder al panel de feedback."""
    _login(client, email="normal@test.es", es_admin=False)
    resp = client.get("/admin/feedback")
    assert resp.status_code == 403


def test_admin_marcar_leidos_bulk(client, db):
    """El admin puede marcar varios mensajes como leídos a la vez."""
    _login(client, email="admin@test.es", es_admin=True)
    fb1 = _post_feedback(client, descripcion="Mensaje 1")
    fb2 = _post_feedback(client, descripcion="Mensaje 2")
    fb3 = _post_feedback(client, descripcion="Mensaje 3")

    resp = client.post(
        "/admin/feedback/marcar-leidos",
        data={"ids": [fb1.id, fb2.id]},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    _db.session.refresh(fb1)
    _db.session.refresh(fb2)
    _db.session.refresh(fb3)
    assert fb1.leido is True
    assert fb2.leido is True
    assert fb3.leido is False


def test_admin_marcar_leidos_bulk_sin_ids_no_da_error(client, db):
    """Enviar el bulk form sin seleccionar nada no falla."""
    _login(client, email="admin@test.es", es_admin=True)
    resp = client.post("/admin/feedback/marcar-leidos", data={}, follow_redirects=False)
    assert resp.status_code == 302


# --- Restablecimiento manual por el admin (fallback si el email no llega) ---

# --- Push a administradores al recibir feedback ---

def _admin_con_push(app, client):
    admin = _login(client, email="admin@test.es", es_admin=True)
    admin.push_subscription = '{"endpoint": "https://push.example.com/x", "keys": {"p256dh": "A", "auth": "B"}}'
    _db.session.commit()
    client.get("/auth/logout", follow_redirects=False)
    old_key = app.config.get("VAPID_PRIVATE_KEY")
    old_email = app.config.get("VAPID_CLAIM_EMAIL")
    app.config["VAPID_PRIVATE_KEY"] = "fake-key"
    app.config["VAPID_CLAIM_EMAIL"] = "admin@test.es"
    return admin, old_key, old_email


def test_nuevo_feedback_envia_push_a_admin(app, client, db):
    admin, old_key, old_email = _admin_con_push(app, client)
    try:
        with patch("app.push.sender.webpush") as mock_wp:
            client.post("/feedback", data={
                "tipo": "error",
                "descripcion": "La app no carga en Safari.",
                "email_contacto": "usuario@test.es",
            })
            mock_wp.assert_called_once()
            assert mock_wp.call_args.kwargs.get("headers") is None
    finally:
        app.config["VAPID_PRIVATE_KEY"] = old_key
        app.config["VAPID_CLAIM_EMAIL"] = old_email


def test_feedback_sin_admins_no_falla(client, db):
    resp = client.post("/feedback", data={
        "tipo": "error",
        "descripcion": "Sin admins en el sistema.",
        "email_contacto": "usuario@test.es",
    }, follow_redirects=False)
    assert resp.status_code == 302


# --- Email a administradores al recibir feedback (excepto recuperación) ---

def _crear_admin(email="admin@test.es"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    admin = registrar_usuario("Admin", email, "pass1234", "H", "U", cat.id)
    admin.es_admin = True
    _db.session.commit()
    return admin


def test_nuevo_feedback_tipo_error_envia_email_al_admin(client, db):
    _crear_admin("admin@test.es")

    with patch("app.routes.feedback.enviar_email", return_value=True) as mock_enviar:
        client.post("/feedback", data={
            "tipo": "error",
            "descripcion": "La app no carga en Safari.",
            "email_contacto": "usuario@test.es",
        })

    mock_enviar.assert_called_once()
    assert mock_enviar.call_args[0][0] == "admin@test.es"


def test_nuevo_feedback_email_incluye_descripcion(client, db):
    _crear_admin("admin@test.es")

    with patch("app.routes.feedback.enviar_email", return_value=True) as mock_enviar:
        client.post("/feedback", data={
            "tipo": "sugerencia",
            "descripcion": "Sería genial poder exportar el calendario.",
            "email_contacto": "usuario@test.es",
        })

    mock_enviar.assert_called_once()
    cuerpo_html = mock_enviar.call_args.args[2]
    assert "Sería genial poder exportar el calendario." in cuerpo_html


def test_nuevo_feedback_tipo_recuperacion_no_envia_email(client, db):
    _crear_admin("admin@test.es")

    with patch("app.routes.feedback.enviar_email") as mock_enviar:
        client.post("/feedback", data={
            "tipo": "recuperacion",
            "descripcion": "Solicitud de recuperación.",
            "email_contacto": "usuario@test.es",
        })

    mock_enviar.assert_not_called()


def test_nuevo_feedback_envia_email_a_todos_los_admins(client, db):
    _crear_admin("admin1@test.es")
    _crear_admin("admin2@test.es")

    with patch("app.routes.feedback.enviar_email", return_value=True) as mock_enviar:
        client.post("/feedback", data={
            "tipo": "error",
            "descripcion": "Fallo visible para ambos admins.",
            "email_contacto": "usuario@test.es",
        })

    destinatarios = {llamada.args[0] for llamada in mock_enviar.call_args_list}
    assert destinatarios == {"admin1@test.es", "admin2@test.es"}


def test_feedback_sin_admins_no_envia_email_ni_falla(client, db):
    with patch("app.routes.feedback.enviar_email") as mock_enviar:
        resp = client.post("/feedback", data={
            "tipo": "error",
            "descripcion": "Sin admins en el sistema.",
            "email_contacto": "usuario@test.es",
        }, follow_redirects=False)

    assert resp.status_code == 302
    mock_enviar.assert_not_called()


def test_nuevo_feedback_email_usa_app_base_url_si_esta_configurada(app, client, db):
    # El enlace del email debe apuntar siempre al dominio propio configurado,
    # no al host de la petición entrante (p. ej. *.up.railway.app, que algunos
    # filtros de correo corporativos bloquean).
    _crear_admin("admin@test.es")

    app.config["APP_BASE_URL"] = "https://app.turnero.xyz"
    try:
        with patch("app.routes.feedback.enviar_email", return_value=True) as mock_enviar:
            client.post("/feedback", data={
                "tipo": "error",
                "descripcion": "La app no carga en Safari.",
                "email_contacto": "usuario@test.es",
            })
    finally:
        app.config["APP_BASE_URL"] = ""

    cuerpo_html = mock_enviar.call_args.args[2]
    assert "https://app.turnero.xyz/admin/feedback" in cuerpo_html
    assert "usuario@test.es" in cuerpo_html


def test_admin_restablecer_contrasena_cambia_password(client, db):
    u = _login(client, email="admin@test.es", es_admin=True)
    usuario_target = registrar_usuario("Víctima", "victima@test.es", "pass_original", "H", "U",
                                       Categoria.query.filter_by(nombre="Enfermería").first().id)
    fb = Feedback(tipo="recuperacion", descripcion="Solicitud.", email_contacto="victima@test.es")
    _db.session.add(fb)
    _db.session.commit()

    resp = client.post(f"/admin/feedback/{fb.id}/restablecer-contrasena", follow_redirects=False)
    assert resp.status_code == 302

    _db.session.refresh(usuario_target)
    assert not usuario_target.check_password("pass_original")


def test_admin_restablecer_contrasena_email_inexistente_muestra_error(client, db):
    _login(client, email="admin@test.es", es_admin=True)
    fb = Feedback(tipo="recuperacion", descripcion="Solicitud.", email_contacto="noexiste@test.es")
    _db.session.add(fb)
    _db.session.commit()

    resp = client.post(f"/admin/feedback/{fb.id}/restablecer-contrasena", follow_redirects=True)
    assert "noexiste@test.es" in resp.data.decode()


def test_admin_restablecer_contrasena_marca_feedback_leido(client, db):
    _login(client, email="admin@test.es", es_admin=True)
    registrar_usuario("Víctima", "victima2@test.es", "pass", "H", "U",
                      Categoria.query.filter_by(nombre="Enfermería").first().id)
    fb = Feedback(tipo="recuperacion", descripcion="Solicitud.", email_contacto="victima2@test.es")
    _db.session.add(fb)
    _db.session.commit()

    client.post(f"/admin/feedback/{fb.id}/restablecer-contrasena")
    _db.session.refresh(fb)
    assert fb.leido is True


def test_admin_restablecer_contrasena_crea_aviso_para_el_usuario(client, db):
    """La contraseña temporal se envía como aviso (campana) al usuario, no como flash al admin."""
    _login(client, email="admin@test.es", es_admin=True)
    usuario_target = registrar_usuario("Víctima", "victima3@test.es", "pass_original", "H", "U",
                                        Categoria.query.filter_by(nombre="Enfermería").first().id)
    fb = Feedback(tipo="recuperacion", descripcion="Solicitud.", email_contacto="victima3@test.es")
    _db.session.add(fb)
    _db.session.commit()

    client.post(f"/admin/feedback/{fb.id}/restablecer-contrasena")

    aviso = Notificacion.query.filter_by(usuario_id=usuario_target.id, tipo="contrasena_restablecida").first()
    assert aviso is not None
    assert aviso.mensaje
    contrasena_temporal = aviso.mensaje.split()[-1]
    assert usuario_target.check_password(contrasena_temporal)


def test_admin_restablecer_contrasena_no_muestra_flash_con_password(client, db):
    """No debe filtrarse la contraseña temporal en un flash message al admin."""
    _login(client, email="admin@test.es", es_admin=True)
    registrar_usuario("Víctima", "victima4@test.es", "pass_original", "H", "U",
                       Categoria.query.filter_by(nombre="Enfermería").first().id)
    fb = Feedback(tipo="recuperacion", descripcion="Solicitud.", email_contacto="victima4@test.es")
    _db.session.add(fb)
    _db.session.commit()

    resp = client.post(f"/admin/feedback/{fb.id}/restablecer-contrasena", follow_redirects=True)
    assert "Contraseña temporal para" not in resp.data.decode()
