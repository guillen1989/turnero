"""
Tests de integración HTTP para registro, login y logout.
"""
from app.models import Usuario, Hospital, Unidad, Categoria, GrupoIntercambio, insertar_categorias_semilla


def _cat_id(db):
    insertar_categorias_semilla()
    return Categoria.query.filter_by(nombre="Enfermería").first().id


def _datos_registro(db, **overrides):
    datos = {
        "nombre": "Ana García",
        "email": "ana@test.es",
        "password": "contraseña123",
        "password2": "contraseña123",
        "hospital_id": 0,
        "hospital_nuevo": "Hospital Test",
        "unidad_id": 0,
        "unidad_nuevo": "Urgencias",
        "categoria_id": _cat_id(db),
        "categoria_nueva": "",
    }
    datos.update(overrides)
    return datos


def test_get_registro_devuelve_200(client):
    resp = client.get("/auth/registro")
    assert resp.status_code == 200


def test_registro_exitoso_redirige(client, db):
    resp = client.post("/auth/registro", data=_datos_registro(db), follow_redirects=False)
    assert resp.status_code == 302
    # Unidad nueva → redirige al configurador de turnos; unidad existente → al inicio
    assert resp.headers["Location"].endswith("/") or "/unidad/turnos" in resp.headers["Location"]


def test_registro_crea_usuario_en_bd(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    assert Usuario.query.filter_by(email="ana@test.es").count() == 1


def test_registro_crea_hospital_nuevo(client, db):
    client.post("/auth/registro", data=_datos_registro(db, hospital_id=0, hospital_nuevo="Hospital Nuevo"))
    assert Hospital.query.filter_by(nombre="Hospital Nuevo").count() == 1


def test_registro_crea_unidad_nueva_con_grupo(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    unidad = Unidad.query.filter_by(nombre="Urgencias").first()
    assert unidad is not None
    assert unidad.grupo_intercambio is not None


def test_registro_email_duplicado_muestra_error(client, db):
    datos = _datos_registro(db)
    client.post("/auth/registro", data=datos)
    client.get("/auth/logout")  # el registro hace login_user; hay que salir antes del segundo intento
    resp = client.post("/auth/registro", data=datos, follow_redirects=True)
    assert resp.status_code == 200
    assert "ya está registrado".encode() in resp.data


def test_registro_con_categoria_nueva(client, db):
    insertar_categorias_semilla()
    datos = _datos_registro(db)
    datos["categoria_id"] = 0
    datos["categoria_nueva"] = "Técnico/a de farmacia"
    client.post("/auth/registro", data=datos)
    assert Categoria.query.filter_by(nombre="Técnico/a de farmacia").count() == 1


def test_get_login_devuelve_200(client, db):
    resp = client.get("/auth/login")
    assert resp.status_code == 200


def test_login_exitoso_redirige(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    resp = client.post(
        "/auth/login",
        data={"email": "ana@test.es", "password": "contraseña123"},
        follow_redirects=False,
    )
    assert resp.status_code == 302


def test_login_credenciales_incorrectas(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    client.get("/auth/logout")  # el registro hace login_user; salir para probar login con mal password
    resp = client.post(
        "/auth/login",
        data={"email": "ana@test.es", "password": "mal"},
        follow_redirects=True,
    )
    assert "incorrectos".encode() in resp.data


def test_logout_requiere_autenticacion(client, db):
    resp = client.get("/auth/logout", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_logout_cierra_sesion(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    resp = client.get("/auth/logout", follow_redirects=True)
    assert "cerrado sesión".encode() in resp.data


# --- API de unidades ---

def test_api_unidades_sin_hospital_devuelve_lista_vacia(client):
    resp = client.get("/auth/api/unidades")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_api_unidades_hospital_inexistente_devuelve_lista_vacia(client):
    resp = client.get("/auth/api/unidades?hospital=NoExiste")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_api_unidades_devuelve_unidades_del_hospital(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    hospital = Hospital.query.filter_by(nombre="Hospital Test").first()
    resp = client.get(f"/auth/api/unidades?hospital_id={hospital.id}")
    assert resp.status_code == 200
    nombres = [u["nombre"] for u in resp.get_json()]
    assert "Urgencias" in nombres


# --- Perfil ---

def test_get_perfil_requiere_autenticacion(client):
    resp = client.get("/auth/perfil", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_get_perfil_devuelve_200(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    resp = client.get("/auth/perfil")
    assert resp.status_code == 200


def test_perfil_prerellena_datos_actuales(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    resp = client.get("/auth/perfil")
    assert b"Hospital Test" in resp.data
    assert b"Urgencias" in resp.data


def test_perfil_actualiza_hospital_y_unidad(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    usuario = Usuario.query.filter_by(email="ana@test.es").first()
    resp = client.post(
        "/auth/perfil",
        data={
            "hospital_id": 0,
            "hospital_nuevo": "Hospital Nuevo",
            "unidad_id": 0,
            "unidad_nuevo": "UCI",
            "categoria_id": _cat_id(db),
            "categoria_nueva": "",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    from app.extensions import db as _db
    _db.session.refresh(usuario)
    assert usuario.unidad.nombre == "UCI"
    assert usuario.unidad.hospital.nombre == "Hospital Nuevo"


# --- Perfil / Cuenta ---

def test_get_perfil_cuenta_requiere_autenticacion(client):
    resp = client.get("/auth/perfil/cuenta", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_get_perfil_cuenta_devuelve_200(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    resp = client.get("/auth/perfil/cuenta")
    assert resp.status_code == 200
    assert b"Ana" in resp.data


def test_perfil_cuenta_actualiza_nombre(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    usuario = Usuario.query.filter_by(email="ana@test.es").first()
    client.post(
        "/auth/perfil/cuenta",
        data={"nombre": "Ana Pérez", "email": "ana@test.es", "password_actual": "", "password_nuevo": "", "password_nuevo2": ""},
        follow_redirects=True,
    )
    from app.extensions import db as _db
    _db.session.refresh(usuario)
    assert usuario.nombre == "Ana Pérez"


def test_perfil_cuenta_actualiza_email_con_contraseña_correcta(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    usuario = Usuario.query.filter_by(email="ana@test.es").first()
    resp = client.post(
        "/auth/perfil/cuenta",
        data={"nombre": "Ana García", "email": "nueva@test.es", "password_actual": "contraseña123", "password_nuevo": "", "password_nuevo2": ""},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    from app.extensions import db as _db
    _db.session.refresh(usuario)
    assert usuario.email == "nueva@test.es"


def test_perfil_cuenta_rechaza_cambio_email_sin_contraseña(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    usuario = Usuario.query.filter_by(email="ana@test.es").first()
    client.post(
        "/auth/perfil/cuenta",
        data={"nombre": "Ana García", "email": "nueva@test.es", "password_actual": "", "password_nuevo": "", "password_nuevo2": ""},
        follow_redirects=True,
    )
    from app.extensions import db as _db
    _db.session.refresh(usuario)
    assert usuario.email == "ana@test.es"


def test_perfil_cuenta_cambia_contraseña(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    usuario = Usuario.query.filter_by(email="ana@test.es").first()
    client.post(
        "/auth/perfil/cuenta",
        data={"nombre": "Ana García", "email": "ana@test.es", "password_actual": "contraseña123", "password_nuevo": "nueva_clave_99", "password_nuevo2": "nueva_clave_99"},
        follow_redirects=True,
    )
    from app.extensions import db as _db
    _db.session.refresh(usuario)
    assert usuario.check_password("nueva_clave_99")


def test_perfil_cuenta_rechaza_contraseña_nueva_sin_actual(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    usuario = Usuario.query.filter_by(email="ana@test.es").first()
    client.post(
        "/auth/perfil/cuenta",
        data={"nombre": "Ana García", "email": "ana@test.es", "password_actual": "", "password_nuevo": "nueva_clave_99", "password_nuevo2": "nueva_clave_99"},
        follow_redirects=True,
    )
    from app.extensions import db as _db
    _db.session.refresh(usuario)
    assert not usuario.check_password("nueva_clave_99")


# --- Ronda 2, Paso 6: el calendario pasa a ser la pantalla de inicio ---

def test_login_exitoso_con_onboarding_visto_redirige_a_calendario(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    Usuario.query.filter_by(email="ana@test.es").update({"onboarding_visto": True})
    db.session.commit()
    client.get("/auth/logout")

    resp = client.post(
        "/auth/login",
        data={"email": "ana@test.es", "password": "contraseña123"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/calendario/")


def test_login_ya_autenticado_redirige_a_calendario(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    resp = client.get("/auth/login", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/calendario/")


def test_registro_ya_autenticado_redirige_a_calendario(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    resp = client.get("/auth/registro", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/calendario/")


# --- Login con cuenta demo ---

def test_login_no_muestra_boton_demo_si_no_configurado(client, db):
    resp = client.get("/auth/login")
    assert "Probar con una cuenta demo".encode() not in resp.data


def test_login_muestra_boton_demo_si_configurado(client, db, app, monkeypatch):
    monkeypatch.setitem(app.config, "DEMO_LOGIN_EMAIL", "ana.garcia@test.es")
    monkeypatch.setitem(app.config, "DEMO_LOGIN_PASSWORD", "Staging2026!")
    resp = client.get("/auth/login")
    assert "Probar con una cuenta demo".encode() in resp.data


def test_login_demo_deshabilitado_devuelve_404(client, db):
    resp = client.post("/auth/login/demo", follow_redirects=False)
    assert resp.status_code == 404


# --- Botón demo en la portada (junto a "Crear cuenta"/"Entrar") ---

def test_portada_no_muestra_boton_demo_si_no_configurado(client, db):
    resp = client.get("/")
    assert "Probar con una cuenta demo".encode() not in resp.data


def test_portada_muestra_boton_demo_si_configurado(client, db, app, monkeypatch):
    monkeypatch.setitem(app.config, "DEMO_LOGIN_EMAIL", "ana.garcia@test.es")
    monkeypatch.setitem(app.config, "DEMO_LOGIN_PASSWORD", "Staging2026!")
    resp = client.get("/")
    assert "Probar con una cuenta demo".encode() in resp.data


def test_portada_ofrece_eleccion_trabajador_supervisora_si_ambas_configuradas(client, db, app, monkeypatch):
    monkeypatch.setitem(app.config, "DEMO_LOGIN_EMAIL", "ana.garcia@test.es")
    monkeypatch.setitem(app.config, "DEMO_LOGIN_PASSWORD", "Staging2026!")
    monkeypatch.setitem(app.config, "DEMO_SUPERVISORA_LOGIN_EMAIL", "sup.garcia@test.es")
    monkeypatch.setitem(app.config, "DEMO_SUPERVISORA_LOGIN_PASSWORD", "Staging2026!")
    resp = client.get("/")
    assert "trabajador".encode() in resp.data.lower()
    assert "supervisora".encode() in resp.data.lower()


def test_login_demo_exitoso_redirige(client, db, app, monkeypatch):
    client.post("/auth/registro", data=_datos_registro(db, email="ana.garcia@test.es", password="Staging2026!", password2="Staging2026!"))
    Usuario.query.filter_by(email="ana.garcia@test.es").update({"onboarding_visto": True})
    db.session.commit()
    client.get("/auth/logout")

    monkeypatch.setitem(app.config, "DEMO_LOGIN_EMAIL", "ana.garcia@test.es")
    monkeypatch.setitem(app.config, "DEMO_LOGIN_PASSWORD", "Staging2026!")
    resp = client.post("/auth/login/demo", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/calendario/")


def test_login_demo_usuario_inexistente_muestra_error(client, db, app, monkeypatch):
    monkeypatch.setitem(app.config, "DEMO_LOGIN_EMAIL", "no-existe@test.es")
    monkeypatch.setitem(app.config, "DEMO_LOGIN_PASSWORD", "Staging2026!")
    resp = client.post("/auth/login/demo", follow_redirects=True)
    assert "no se pudo iniciar sesión con la cuenta demo".encode() in resp.data.lower()


# --- Sesión persistente ("remember me") ---
# El login debe comportarse como el de una app: el usuario permanece
# autenticado aunque se cierre el navegador/PWA, hasta que él mismo
# cierre sesión explícitamente.

def test_login_establece_cookie_remember_me(client, db):
    resp = client.post(
        "/auth/login",
        data={"email": "no-existe@test.es", "password": "x"},
    )
    # Sin login exitoso no debe fijarse la cookie de "recuérdame".
    assert client.get_cookie("remember_token") is None

    client.post("/auth/registro", data=_datos_registro(db))
    assert client.get_cookie("remember_token") is not None


def test_login_demo_establece_cookie_remember_me(client, db, app, monkeypatch):
    client.post("/auth/registro", data=_datos_registro(db, email="ana.garcia@test.es", password="Staging2026!", password2="Staging2026!"))
    client.get("/auth/logout")

    monkeypatch.setitem(app.config, "DEMO_LOGIN_EMAIL", "ana.garcia@test.es")
    monkeypatch.setitem(app.config, "DEMO_LOGIN_PASSWORD", "Staging2026!")
    client.post("/auth/login/demo")
    assert client.get_cookie("remember_token") is not None


def test_sesion_persiste_sin_cookie_de_sesion_activa(client, db):
    """Simula cerrar y reabrir la app: se pierde la cookie de sesión (no
    permanente) pero se conserva la de "recuérdame". El usuario debe seguir
    autenticado gracias a esa cookie."""
    client.post("/auth/registro", data=_datos_registro(db))
    assert client.get_cookie("remember_token") is not None

    client.delete_cookie("session")

    resp = client.get("/auth/perfil", follow_redirects=False)
    assert resp.status_code == 200


def test_logout_borra_cookie_remember_me(client, db):
    client.post("/auth/registro", data=_datos_registro(db))
    assert client.get_cookie("remember_token") is not None

    client.get("/auth/logout")
    assert client.get_cookie("remember_token") is None

    client.delete_cookie("session")
    resp = client.get("/auth/perfil", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_login_demo_ya_autenticado_redirige_a_calendario(client, db, app, monkeypatch):
    client.post("/auth/registro", data=_datos_registro(db, email="ana.garcia@test.es", password="Staging2026!", password2="Staging2026!"))

    monkeypatch.setitem(app.config, "DEMO_LOGIN_EMAIL", "ana.garcia@test.es")
    monkeypatch.setitem(app.config, "DEMO_LOGIN_PASSWORD", "Staging2026!")
    resp = client.post("/auth/login/demo", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/calendario/")


# --- Elegir cuenta demo de trabajador o de supervisora ---

def _configurar_ambas_cuentas_demo(app, monkeypatch):
    monkeypatch.setitem(app.config, "DEMO_LOGIN_EMAIL", "ana.garcia@test.es")
    monkeypatch.setitem(app.config, "DEMO_LOGIN_PASSWORD", "Staging2026!")
    monkeypatch.setitem(app.config, "DEMO_SUPERVISORA_LOGIN_EMAIL", "sup.garcia@test.es")
    monkeypatch.setitem(app.config, "DEMO_SUPERVISORA_LOGIN_PASSWORD", "Staging2026!")


def test_login_no_ofrece_eleccion_supervisora_si_no_esta_configurada(client, db, app, monkeypatch):
    monkeypatch.setitem(app.config, "DEMO_LOGIN_EMAIL", "ana.garcia@test.es")
    monkeypatch.setitem(app.config, "DEMO_LOGIN_PASSWORD", "Staging2026!")
    resp = client.get("/auth/login")
    assert "Probar con una cuenta demo".encode() in resp.data
    assert "Supervisora".encode() not in resp.data


def test_login_ofrece_eleccion_trabajador_supervisora_si_ambas_configuradas(client, db, app, monkeypatch):
    _configurar_ambas_cuentas_demo(app, monkeypatch)
    resp = client.get("/auth/login")
    assert "Trabajador".encode() in resp.data
    assert "Supervisora".encode() in resp.data


def test_login_demo_tipo_supervisora_inicia_sesion_con_esa_cuenta(client, db, app, monkeypatch):
    client.post("/auth/registro", data=_datos_registro(db, email="sup.garcia@test.es", password="Staging2026!", password2="Staging2026!"))
    Usuario.query.filter_by(email="sup.garcia@test.es").update({"onboarding_visto": True})
    db.session.commit()
    client.get("/auth/logout")

    _configurar_ambas_cuentas_demo(app, monkeypatch)
    resp = client.post("/auth/login/demo", data={"tipo": "supervisora"}, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/calendario/")

    with client.session_transaction() as sess:
        assert sess.get("_user_id") == str(
            Usuario.query.filter_by(email="sup.garcia@test.es").first().id
        )


def test_login_demo_tipo_trabajador_por_defecto(client, db, app, monkeypatch):
    """Sin indicar `tipo`, se conserva el comportamiento anterior (trabajador)."""
    client.post("/auth/registro", data=_datos_registro(db, email="ana.garcia@test.es", password="Staging2026!", password2="Staging2026!"))
    Usuario.query.filter_by(email="ana.garcia@test.es").update({"onboarding_visto": True})
    db.session.commit()
    client.get("/auth/logout")

    _configurar_ambas_cuentas_demo(app, monkeypatch)
    resp = client.post("/auth/login/demo", follow_redirects=False)
    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert sess.get("_user_id") == str(
            Usuario.query.filter_by(email="ana.garcia@test.es").first().id
        )


def test_login_demo_supervisora_deshabilitada_devuelve_404(client, db, app, monkeypatch):
    monkeypatch.setitem(app.config, "DEMO_LOGIN_EMAIL", "ana.garcia@test.es")
    monkeypatch.setitem(app.config, "DEMO_LOGIN_PASSWORD", "Staging2026!")
    resp = client.post("/auth/login/demo", data={"tipo": "supervisora"}, follow_redirects=False)
    assert resp.status_code == 404
