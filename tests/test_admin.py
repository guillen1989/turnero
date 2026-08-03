"""Tests de integración para el panel de administración."""
import pytest
from datetime import date
from app.models import (
    Usuario, Hospital, Unidad, Categoria, insertar_categorias_semilla,
    Notificacion, PublicacionCambio, TurnoCedido, TurnoAceptado, FranjaHoraria,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cat_id(db):
    insertar_categorias_semilla()
    return Categoria.query.filter_by(nombre="Enfermería").first().id


def _crear_usuario(client, db, email="user@test.es", es_admin=False):
    insertar_categorias_semilla()
    from app.services.registro import registrar_usuario
    u = registrar_usuario(
        nombre="Usuario Test",
        email=email,
        password="contraseña123",
        hospital_nombre="Hospital Admin Test",
        unidad_nombre="Urgencias",
        categoria_id=_cat_id(db),
    )
    u.es_admin = es_admin
    from app.extensions import db as _db
    _db.session.commit()
    return u


def _login(client, email, password="contraseña123"):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def _login_admin(client, db):
    _crear_usuario(client, db, email="admin@test.es", es_admin=True)
    _login(client, "admin@test.es")


def _login_normal(client, db):
    _crear_usuario(client, db, email="normal@test.es", es_admin=False)
    _login(client, "normal@test.es")


# ---------------------------------------------------------------------------
# Acceso y permisos
# ---------------------------------------------------------------------------

def test_admin_redirige_si_no_autenticado(client):
    resp = client.get("/admin/", follow_redirects=False)
    assert resp.status_code == 302


def test_admin_403_para_usuario_normal(client, db):
    _login_normal(client, db)
    resp = client.get("/admin/")
    assert resp.status_code == 403


def test_admin_index_accesible_para_admin(client, db):
    _login_admin(client, db)
    resp = client.get("/admin/")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------

def test_admin_lista_usuarios(client, db):
    _login_admin(client, db)
    resp = client.get("/admin/usuarios")
    assert resp.status_code == 200
    assert b"admin@test.es" in resp.data


def test_admin_crea_usuario(client, db):
    from unittest.mock import patch
    _login_admin(client, db)
    with patch("app.services.registro.enviar_email", return_value=True):
        resp = client.post(
            "/admin/usuarios/nuevo",
            data={
                "nombre": "Nuevo Enfermero",
                "email": "nuevo@test.es",
                "hospital_id": "0",
                "hospital_nuevo": "Hospital Admin Test",
                "unidad_id": "0",
                "unidad_nuevo": "UCI",
                "categoria_id": _cat_id(db),
                "categoria_nueva": "",
                "es_admin": False,
            },
            follow_redirects=True,
        )
    assert resp.status_code == 200
    assert Usuario.query.filter_by(email="nuevo@test.es").count() == 1


def test_admin_edita_usuario(client, db):
    _login_admin(client, db)
    u = _crear_usuario(client, db, email="editar@test.es")
    from app.extensions import db as _db
    _db.session.refresh(u)
    resp = client.post(
        f"/admin/usuarios/{u.id}/editar",
        data={
            "nombre": "Nombre Modificado",
            "email": "editar@test.es",
            "password": "",
            "hospital_id": "0",
            "hospital_nuevo": "Hospital Admin Test",
            "unidad_id": "0",
            "unidad_nuevo": "Urgencias",
            "categoria_id": _cat_id(db),
            "categoria_nueva": "",
            "es_admin": False,
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    _db.session.refresh(u)
    assert u.nombre == "Nombre Modificado"


def test_admin_elimina_usuario(client, db):
    _login_admin(client, db)
    u = _crear_usuario(client, db, email="borrar@test.es")
    from app.extensions import db as _db
    resp = client.post(
        f"/admin/usuarios/{u.id}/eliminar",
        data={"csrf_token": ""},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert Usuario.query.filter_by(email="borrar@test.es").count() == 0


def test_admin_elimina_supervisora_con_unidad_supervisada(client, db):
    """Regression: borrar una supervisora con filas en unidad_supervisada
    violaba la FK al no limpiarlas antes de borrar el usuario."""
    from app.extensions import db as _db
    from app.models import UnidadSupervisada
    _login_admin(client, db)
    u = _crear_usuario(client, db, email="supervisora@test.es")
    u.es_supervisora = True
    _db.session.commit()
    _db.session.add(UnidadSupervisada(usuario_id=u.id, unidad_id=u.unidad_id))
    _db.session.commit()

    resp = client.post(
        f"/admin/usuarios/{u.id}/eliminar",
        data={"csrf_token": ""},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert Usuario.query.filter_by(email="supervisora@test.es").count() == 0


def test_admin_crea_supervisora_asigna_unidades_supervisadas(client, db):
    from app.extensions import db as _db
    from app.models import UnidadSupervisada
    from app.services.registro import encontrar_o_crear_unidad
    _login_admin(client, db)
    hospital = Hospital.query.filter_by(nombre="Hospital Admin Test").first()
    unidad_extra, _is_new = encontrar_o_crear_unidad("UCI Extra", hospital)
    _db.session.commit()

    resp = client.post(
        "/admin/usuarios/nuevo",
        data={
            "nombre": "Nueva Supervisora",
            "email": "supervisora_nueva@test.es",
            "password": "contraseña123",
            "hospital_id": "0",
            "hospital_nuevo": "Hospital Admin Test",
            "unidad_id": "0",
            "unidad_nuevo": "Urgencias Nueva",
            "categoria_id": _cat_id(db),
            "categoria_nueva": "",
            "es_admin": False,
            "es_supervisora": True,
            "unidades_supervisadas": [str(unidad_extra.id)],
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    u = Usuario.query.filter_by(email="supervisora_nueva@test.es").first()
    assert u is not None
    unidades_ids = {us.unidad_id for us in UnidadSupervisada.query.filter_by(usuario_id=u.id).all()}
    assert unidades_ids == {u.unidad_id, unidad_extra.id}


def test_admin_crea_supervisora_no_exige_password_y_envia_invitacion(client, db):
    from unittest.mock import patch
    _login_admin(client, db)

    with patch("app.services.registro.enviar_email", return_value=True) as mock_enviar:
        resp = client.post(
            "/admin/usuarios/nuevo",
            data={
                "nombre": "Supervisora Invitada",
                "email": "invitada@test.es",
                "password": "",
                "hospital_id": "0",
                "hospital_nuevo": "Hospital Admin Test",
                "unidad_id": "0",
                "unidad_nuevo": "Urgencias Invitada",
                "categoria_id": _cat_id(db),
                "categoria_nueva": "",
                "es_admin": False,
                "es_supervisora": True,
            },
            follow_redirects=True,
        )
    assert resp.status_code == 200
    u = Usuario.query.filter_by(email="invitada@test.es").first()
    assert u is not None

    mock_enviar.assert_called_once()
    destinatario = mock_enviar.call_args[0][0]
    assert destinatario == "invitada@test.es"
    cuerpo_html = mock_enviar.call_args[0][2]
    assert "/auth/restablecer-contrasena/" in cuerpo_html


def test_admin_crea_supervisora_password_generada_no_es_conocida(client, db):
    from unittest.mock import patch
    _login_admin(client, db)

    with patch("app.services.registro.enviar_email", return_value=True):
        client.post(
            "/admin/usuarios/nuevo",
            data={
                "nombre": "Supervisora Sin Password",
                "email": "sinpassword@test.es",
                "password": "",
                "hospital_id": "0",
                "hospital_nuevo": "Hospital Admin Test",
                "unidad_id": "0",
                "unidad_nuevo": "Urgencias Sin Password",
                "categoria_id": _cat_id(db),
                "categoria_nueva": "",
                "es_admin": False,
                "es_supervisora": True,
            },
            follow_redirects=True,
        )
    u = Usuario.query.filter_by(email="sinpassword@test.es").first()
    assert u is not None
    assert not u.check_password("")
    assert not u.check_password("contraseña123")


def test_admin_crea_usuario_normal_no_exige_password_y_envia_invitacion(client, db):
    from unittest.mock import patch
    _login_admin(client, db)

    with patch("app.services.registro.enviar_email", return_value=True) as mock_enviar:
        resp = client.post(
            "/admin/usuarios/nuevo",
            data={
                "nombre": "Usuario Normal Invitado",
                "email": "normal_invitado@test.es",
                "hospital_id": "0",
                "hospital_nuevo": "Hospital Admin Test",
                "unidad_id": "0",
                "unidad_nuevo": "Urgencias Normal",
                "categoria_id": _cat_id(db),
                "categoria_nueva": "",
                "es_admin": False,
            },
            follow_redirects=True,
        )
    assert resp.status_code == 200
    u = Usuario.query.filter_by(email="normal_invitado@test.es").first()
    assert u is not None
    assert not u.check_password("")

    mock_enviar.assert_called_once()
    destinatario = mock_enviar.call_args[0][0]
    assert destinatario == "normal_invitado@test.es"
    cuerpo_html = mock_enviar.call_args[0][2]
    assert "/auth/restablecer-contrasena/" in cuerpo_html


def test_admin_crea_usuario_avisa_si_falla_el_envio_de_invitacion(client, db):
    """Regression: si Resend falla (p. ej. RESEND_API_KEY sin configurar en el
    entorno), el admin veía "Usuario creado" sin ninguna pista de que el email
    de invitación no había llegado."""
    from unittest.mock import patch
    _login_admin(client, db)

    with patch("app.services.registro.enviar_email", return_value=False):
        resp = client.post(
            "/admin/usuarios/nuevo",
            data={
                "nombre": "Usuario Sin Email",
                "email": "sin_email@test.es",
                "hospital_id": "0",
                "hospital_nuevo": "Hospital Admin Test",
                "unidad_id": "0",
                "unidad_nuevo": "Urgencias Sin Email",
                "categoria_id": _cat_id(db),
                "categoria_nueva": "",
                "es_admin": False,
            },
            follow_redirects=True,
        )
    assert resp.status_code == 200
    assert Usuario.query.filter_by(email="sin_email@test.es").count() == 1
    assert "no se ha podido enviar" in resp.get_data(as_text=True).lower()


def test_admin_crea_usuario_con_email_duplicado_muestra_error(client, db):
    _login_admin(client, db)
    u_existente = _crear_usuario(client, db, email="duplicado@test.es")

    resp = client.post(
        "/admin/usuarios/nuevo",
        data={
            "nombre": "Otro Usuario",
            "email": "duplicado@test.es",
            "hospital_id": "0",
            "hospital_nuevo": "Hospital Admin Test",
            "unidad_id": "0",
            "unidad_nuevo": "Urgencias Duplicado",
            "categoria_id": _cat_id(db),
            "categoria_nueva": "",
            "es_admin": False,
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert Usuario.query.filter_by(email="duplicado@test.es").count() == 1


def test_admin_edita_usuario_con_email_duplicado_muestra_error(client, db):
    from app.extensions import db as _db
    _login_admin(client, db)
    _crear_usuario(client, db, email="ya_existe@test.es")
    u = _crear_usuario(client, db, email="a_editar@test.es")

    resp = client.post(
        f"/admin/usuarios/{u.id}/editar",
        data={
            "nombre": u.nombre,
            "email": "ya_existe@test.es",
            "password": "",
            "hospital_id": "0",
            "hospital_nuevo": "Hospital Admin Test",
            "unidad_id": "0",
            "unidad_nuevo": "Urgencias",
            "categoria_id": _cat_id(db),
            "categoria_nueva": "",
            "es_admin": False,
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    _db.session.refresh(u)
    assert u.email == "a_editar@test.es"


def test_admin_edita_usuario_actualiza_unidades_supervisadas(client, db):
    from app.extensions import db as _db
    from app.models import UnidadSupervisada
    from app.services.registro import encontrar_o_crear_unidad
    _login_admin(client, db)
    u = _crear_usuario(client, db, email="supervisora_editar@test.es")
    u.es_supervisora = True
    _db.session.commit()

    hospital = Hospital.query.filter_by(nombre="Hospital Admin Test").first()
    unidad_extra, _is_new = encontrar_o_crear_unidad("UCI Extra Editar", hospital)
    _db.session.commit()

    resp = client.post(
        f"/admin/usuarios/{u.id}/editar",
        data={
            "nombre": u.nombre,
            "email": u.email,
            "password": "",
            "hospital_id": "0",
            "hospital_nuevo": "Hospital Admin Test",
            "unidad_id": "0",
            "unidad_nuevo": "Urgencias",
            "categoria_id": _cat_id(db),
            "categoria_nueva": "",
            "es_admin": False,
            "es_supervisora": True,
            "unidades_supervisadas": [str(unidad_extra.id)],
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    _db.session.refresh(u)
    unidades_ids = {us.unidad_id for us in UnidadSupervisada.query.filter_by(usuario_id=u.id).all()}
    assert unidades_ids == {u.unidad_id, unidad_extra.id}


def test_admin_desmarca_es_supervisora_limpia_unidades_supervisadas(client, db):
    from app.extensions import db as _db
    from app.models import UnidadSupervisada
    _login_admin(client, db)
    u = _crear_usuario(client, db, email="ex_supervisora@test.es")
    u.es_supervisora = True
    _db.session.commit()
    _db.session.add(UnidadSupervisada(usuario_id=u.id, unidad_id=u.unidad_id))
    _db.session.commit()

    resp = client.post(
        f"/admin/usuarios/{u.id}/editar",
        data={
            "nombre": u.nombre,
            "email": u.email,
            "password": "",
            "hospital_id": "0",
            "hospital_nuevo": "Hospital Admin Test",
            "unidad_id": "0",
            "unidad_nuevo": "Urgencias",
            "categoria_id": _cat_id(db),
            "categoria_nueva": "",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert UnidadSupervisada.query.filter_by(usuario_id=u.id).count() == 0


def test_admin_elimina_supervisora_con_datos_planilla_y_documentos(client, db):
    """Regression: borrar una supervisora con filas en planilla, hojas de
    cambio y tokens de reseteo de contraseña violaba varias FKs NOT NULL
    (visto en producción como NotNullViolation en estado_dia_planilla)."""
    from app.extensions import db as _db
    from app.models import (
        EstadoDiaPlanilla, CompatibilidadPlanilla, TurnoPlanilla, PlanillaMes,
        SalienteDia, NotaDia, AjustePlanillaSupervisora, MapeoTrabajadorPlanilla,
        PasswordResetToken, DocumentoCambio, ParticipanteDocumentoCambio,
        FirmaDocumentoCambio, PublicacionCambio,
    )
    from app.services.password_reset import generar_token_reset

    _login_admin(client, db)
    u = _crear_usuario(client, db, email="supervisora_planilla@test.es")
    u.es_supervisora = True
    _db.session.commit()
    otro = _crear_usuario(client, db, email="companero_planilla@test.es")

    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u.unidad.grupo_intercambio_id, nombre="Mañana"
    ).first()
    pub = PublicacionCambio(usuario_id=otro.id)
    _db.session.add(pub)
    _db.session.flush()

    _db.session.add(EstadoDiaPlanilla(usuario_id=u.id, fecha=date(2026, 9, 1), tipo="libre", unidad_id=u.unidad_id))
    _db.session.add(CompatibilidadPlanilla(publicacion_id=pub.id, usuario_id=u.id, tipo="compatible"))
    _db.session.add(TurnoPlanilla(usuario_id=u.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id, unidad_id=u.unidad_id))
    _db.session.add(PlanillaMes(usuario_id=u.id, anyo=2026, mes=9, unidad_id=u.unidad_id))
    _db.session.add(SalienteDia(usuario_id=u.id, fecha=date(2026, 9, 3), unidad_id=u.unidad_id))
    _db.session.add(NotaDia(usuario_id=u.id, fecha=date(2026, 9, 4), texto="nota", unidad_id=u.unidad_id))
    _db.session.add(AjustePlanillaSupervisora(
        usuario_id=otro.id, realizado_por_id=u.id, fecha=date(2026, 9, 5),
        descripcion_anterior="Turno", descripcion_nueva="Libre",
    ))
    _db.session.add(MapeoTrabajadorPlanilla(
        unidad_id=u.unidad_id, numero_empleado="123", nombre_planilla="Nombre Planilla", usuario_id=u.id,
    ))
    _db.session.commit()

    generar_token_reset(u)
    assert PasswordResetToken.query.filter_by(usuario_id=u.id).count() == 1

    doc = DocumentoCambio(creado_por_id=u.id, unidad_id=u.unidad_id, numero_unidad=1, supervisora_id=u.id)
    _db.session.add(doc)
    _db.session.flush()
    _db.session.add(ParticipanteDocumentoCambio(
        documento_id=doc.id, usuario_id=u.id,
        turno_cede_fecha=date(2026, 9, 6), turno_cede_franja_id=franja.id,
        turno_recibe_fecha=date(2026, 9, 7), turno_recibe_franja_id=franja.id,
    ))
    _db.session.add(FirmaDocumentoCambio(
        documento_id=doc.id, usuario_id=u.id, imagen_firma="data:image/png;base64,x",
        hash_documento="hash",
    ))
    _db.session.commit()

    resp = client.post(
        f"/admin/usuarios/{u.id}/eliminar",
        data={"csrf_token": ""},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert Usuario.query.filter_by(email="supervisora_planilla@test.es").count() == 0
    assert MapeoTrabajadorPlanilla.query.filter_by(numero_empleado="123").first().usuario_id is None


def test_admin_elimina_usuario_con_publicaciones(client, db):
    """Regression: deleting a user with publications used to raise Internal Server Error."""
    from app.extensions import db as _db
    _login_admin(client, db)
    u = _crear_usuario(client, db, email="con_pubs@test.es")

    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u.unidad.grupo_intercambio_id, nombre="Mañana"
    ).first()
    pub = PublicacionCambio(usuario_id=u.id)
    _db.session.add(pub)
    _db.session.flush()
    _db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id))
    _db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=date(2026, 9, 30), franja_horaria_id=franja.id))
    _db.session.commit()

    resp = client.post(
        f"/admin/usuarios/{u.id}/eliminar",
        data={"csrf_token": ""},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert Usuario.query.filter_by(email="con_pubs@test.es").count() == 0


# ---------------------------------------------------------------------------
# Hospitales
# ---------------------------------------------------------------------------

def test_admin_lista_hospitales(client, db):
    _login_admin(client, db)
    resp = client.get("/admin/hospitales")
    assert resp.status_code == 200
    assert b"Hospital Admin Test" in resp.data


def test_admin_crea_hospital(client, db):
    _login_admin(client, db)
    resp = client.post(
        "/admin/hospitales",
        data={"nuevo-nombre": "Hospital Nuevo Admin", "nuevo-submit": "Guardar"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert Hospital.query.filter_by(nombre="Hospital Nuevo Admin").count() == 1


def test_admin_no_elimina_hospital_con_unidades_con_usuarios(client, db):
    """Bloquea si alguna unidad del hospital tiene usuarios."""
    _login_admin(client, db)
    h = Hospital.query.filter_by(nombre="Hospital Admin Test").first()
    resp = client.post(
        f"/admin/hospitales/{h.id}/eliminar",
        data={"csrf_token": ""},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert Hospital.query.filter_by(nombre="Hospital Admin Test").count() == 1


def test_admin_elimina_hospital_con_unidades_sin_usuarios(client, db):
    """Permite eliminar un hospital con unidades vacías; borra también las unidades."""
    from app.extensions import db as _db
    from app.models import GrupoIntercambio
    _login_admin(client, db)
    grupo = GrupoIntercambio()
    _db.session.add(grupo)
    _db.session.flush()
    h = Hospital(nombre="Hospital Vacío")
    _db.session.add(h)
    _db.session.flush()
    u1 = Unidad(nombre="Planta A", hospital_id=h.id, grupo_intercambio_id=grupo.id)
    u2 = Unidad(nombre="Planta B", hospital_id=h.id, grupo_intercambio_id=grupo.id)
    _db.session.add_all([u1, u2])
    _db.session.commit()

    assert Unidad.query.filter_by(hospital_id=h.id).count() == 2
    resp = client.post(
        f"/admin/hospitales/{h.id}/eliminar",
        data={"csrf_token": ""},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert Hospital.query.filter_by(nombre="Hospital Vacío").count() == 0
    assert Unidad.query.filter_by(hospital_id=h.id).count() == 0


# ---------------------------------------------------------------------------
# Categorías
# ---------------------------------------------------------------------------

def test_admin_lista_categorias(client, db):
    _login_admin(client, db)
    insertar_categorias_semilla()
    resp = client.get("/admin/categorias")
    assert resp.status_code == 200
    assert "Enfermer".encode() in resp.data


def test_admin_crea_categoria(client, db):
    _login_admin(client, db)
    resp = client.post(
        "/admin/categorias",
        data={"nuevo-nombre": "Podólogo/a", "nuevo-submit": "Guardar"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert Categoria.query.filter_by(nombre="Podólogo/a").count() == 1


# ---------------------------------------------------------------------------
# Publicaciones
# ---------------------------------------------------------------------------

def test_admin_lista_publicaciones(client, db):
    _login_admin(client, db)
    resp = client.get("/admin/publicaciones")
    assert resp.status_code == 200


def test_admin_elimina_publicacion_sin_matches(client, db):
    """El admin puede eliminar una publicación sin matches asociados."""
    from app.extensions import db as _db
    _login_admin(client, db)
    u = _crear_usuario(client, db, email="pub_owner@test.es")
    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u.unidad.grupo_intercambio_id, nombre="Mañana"
    ).first()
    pub = PublicacionCambio(usuario_id=u.id)
    _db.session.add(pub)
    _db.session.flush()
    _db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id))
    _db.session.commit()
    pub_id = pub.id

    resp = client.post(
        f"/admin/publicaciones/{pub_id}/eliminar",
        data={"csrf_token": ""},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert PublicacionCambio.query.get(pub_id) is None


def test_admin_elimina_publicacion_con_matches(client, db):
    """El admin puede eliminar una publicación que tiene matches asociados (no crash)."""
    from unittest.mock import patch
    from app.extensions import db as _db
    from app.models import MatchCambio, MatchParticipacion, Notificacion
    from app.matching.service import crear_match_directo
    from app.services.registro import registrar_usuario as reg
    insertar_categorias_semilla()
    cat_id = _cat_id(db)

    _login_admin(client, db)

    u1 = reg("Owner", "owner_m@test.es", "pass", "H1", "Urgencias", cat_id)
    u2 = reg("Other", "other_m@test.es", "pass", "H1", "Urgencias", cat_id)

    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u1.unidad.grupo_intercambio_id, nombre="Mañana"
    ).first()

    pub1 = PublicacionCambio(usuario_id=u1.id, tipo="cambio")
    pub2 = PublicacionCambio(usuario_id=u2.id, tipo="cambio")
    _db.session.add_all([pub1, pub2])
    _db.session.flush()
    _db.session.add(TurnoCedido(publicacion_id=pub1.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id))
    _db.session.add(TurnoAceptado(publicacion_id=pub1.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id))
    _db.session.add(TurnoCedido(publicacion_id=pub2.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id))
    _db.session.add(TurnoAceptado(publicacion_id=pub2.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id))
    _db.session.commit()

    with patch("app.push.sender.webpush"):
        match = crear_match_directo(pub1, pub2)
    pub1_id = pub1.id
    match_id = match.id

    resp = client.post(
        f"/admin/publicaciones/{pub1_id}/eliminar",
        data={"csrf_token": ""},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert PublicacionCambio.query.get(pub1_id) is None
    # El match se rechaza (avisando a la contraparte) en vez de desaparecer en silencio.
    match = MatchCambio.query.get(match_id)
    assert match is not None
    assert match.estado == "rechazado"


def test_admin_elimina_publicacion_y_notifica_rechazo_a_la_contraparte(client, db):
    """Eliminar una publicación con match activo notifica el rechazo a la
    contraparte en vez de borrar sus notificaciones en silencio."""
    from unittest.mock import patch
    from app.extensions import db as _db
    from app.models import MatchCambio, Notificacion
    from app.matching.service import crear_match_directo
    from app.services.registro import registrar_usuario as reg
    insertar_categorias_semilla()
    cat_id = _cat_id(db)

    _login_admin(client, db)

    u1 = reg("Ow2", "ow2@test.es", "pass", "H1", "Urgencias", cat_id)
    u2 = reg("Ot2", "ot2@test.es", "pass", "H1", "Urgencias", cat_id)

    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u1.unidad.grupo_intercambio_id, nombre="Mañana"
    ).first()

    pub1 = PublicacionCambio(usuario_id=u1.id, tipo="cambio")
    pub2 = PublicacionCambio(usuario_id=u2.id, tipo="cambio")
    _db.session.add_all([pub1, pub2])
    _db.session.flush()
    _db.session.add(TurnoCedido(publicacion_id=pub1.id, fecha=date(2026, 9, 3), franja_horaria_id=franja.id))
    _db.session.add(TurnoAceptado(publicacion_id=pub1.id, fecha=date(2026, 9, 4), franja_horaria_id=franja.id))
    _db.session.add(TurnoCedido(publicacion_id=pub2.id, fecha=date(2026, 9, 4), franja_horaria_id=franja.id))
    _db.session.add(TurnoAceptado(publicacion_id=pub2.id, fecha=date(2026, 9, 3), franja_horaria_id=franja.id))
    _db.session.commit()

    with patch("app.push.sender.webpush"):
        match = crear_match_directo(pub1, pub2)
    match_id = match.id
    pub1_id = pub1.id

    client.post(
        f"/admin/publicaciones/{pub1_id}/eliminar",
        data={"csrf_token": ""},
        follow_redirects=True,
    )
    n = Notificacion.query.filter_by(match_id=match_id, usuario_id=u2.id, tipo="rechazo").first()
    assert n is not None


def test_admin_elimina_publicacion_con_notificacion_publicacion_id(client, db):
    """Regresión: admin eliminar pub con notificacion.publicacion_id FK falla sin borrar antes."""
    from app.extensions import db as _db
    from app.models import Notificacion
    from app.services.registro import registrar_usuario as reg
    insertar_categorias_semilla()
    cat_id = _cat_id(db)

    _login_admin(client, db)

    u1 = reg("Own3", "own3@test.es", "pass", "H1", "Urgencias", cat_id)
    u2 = reg("Sub3", "sub3@test.es", "pass", "H1", "Urgencias", cat_id)

    pub = PublicacionCambio(usuario_id=u1.id)
    _db.session.add(pub)
    _db.session.flush()
    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u1.unidad.grupo_intercambio_id
    ).first()
    _db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=date(2026, 10, 1), franja_horaria_id=franja.id))
    notif = Notificacion(usuario_id=u2.id, unidad_id=u2.unidad_id, publicacion_id=pub.id, tipo="nueva_publicacion_seguido")
    _db.session.add(notif)
    _db.session.commit()
    pub_id = pub.id
    notif_id = notif.id

    resp = client.post(
        f"/admin/publicaciones/{pub_id}/eliminar",
        data={"csrf_token": ""},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert _db.session.get(PublicacionCambio, pub_id) is None


# ---------------------------------------------------------------------------
# Eliminar usuario — página de confirmación y casos FK complejos
# ---------------------------------------------------------------------------

def test_admin_confirmar_eliminar_usuario_muestra_pagina(client, db):
    _login_admin(client, db)
    u = _crear_usuario(client, db, email="borrar@test.es")
    resp = client.get(f"/admin/usuarios/{u.id}/eliminar")
    assert resp.status_code == 200
    assert "borrar@test.es".encode() in resp.data


def test_admin_confirmar_eliminar_requiere_admin(client, db):
    _crear_usuario(client, db, email="normal@test.es", es_admin=False)
    _login(client, "normal@test.es")
    u = _crear_usuario(client, db, email="borrar@test.es")
    resp = client.get(f"/admin/usuarios/{u.id}/eliminar")
    assert resp.status_code == 403


def test_admin_elimina_usuario_con_busquedas_guardadas(client, db):
    from app.extensions import db as _db
    from app.models import BusquedaGuardada
    _login_admin(client, db)
    u = _crear_usuario(client, db, email="borrar@test.es")
    _db.session.add(BusquedaGuardada(usuario_id=u.id, filtros={}))
    _db.session.commit()

    uid = u.id
    resp = client.post(f"/admin/usuarios/{u.id}/eliminar", data={"csrf_token": ""}, follow_redirects=True)
    assert resp.status_code == 200
    assert Usuario.query.filter_by(id=uid).count() == 0
    assert BusquedaGuardada.query.filter_by(usuario_id=uid).count() == 0


def test_admin_elimina_usuario_con_suscripciones(client, db):
    from app.extensions import db as _db
    from app.models import SuscripcionPublicaciones
    _login_admin(client, db)
    u = _crear_usuario(client, db, email="borrar@test.es")
    admin = Usuario.query.filter_by(email="admin@test.es").first()
    _db.session.add(SuscripcionPublicaciones(suscriptor_id=u.id, publicador_id=admin.id))
    _db.session.commit()

    uid = u.id
    resp = client.post(f"/admin/usuarios/{u.id}/eliminar", data={"csrf_token": ""}, follow_redirects=True)
    assert resp.status_code == 200
    assert Usuario.query.filter_by(id=uid).count() == 0


def test_admin_elimina_usuario_con_notificaciones_ajenas_sobre_sus_pubs(client, db):
    """Regression: otras-user notifications with publicacion_id → pub must be deleted first."""
    from app.extensions import db as _db
    from app.models import Notificacion
    _login_admin(client, db)
    u = _crear_usuario(client, db, email="borrar@test.es")
    observer = _crear_usuario(client, db, email="observer@test.es")

    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u.unidad.grupo_intercambio_id, nombre="Mañana"
    ).first()
    pub = PublicacionCambio(usuario_id=u.id)
    _db.session.add(pub)
    _db.session.flush()
    _db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id))
    # Notification for the observer referencing this publication
    _db.session.add(Notificacion(usuario_id=observer.id, unidad_id=observer.unidad_id, publicacion_id=pub.id, tipo="nueva_publicacion_seguido"))
    _db.session.commit()

    uid = u.id
    resp = client.post(f"/admin/usuarios/{u.id}/eliminar", data={"csrf_token": ""}, follow_redirects=True)
    assert resp.status_code == 200
    assert Usuario.query.filter_by(id=uid).count() == 0
    # Notification for the observer should also have been cleaned up
    assert Notificacion.query.filter_by(usuario_id=observer.id, tipo="nueva_publicacion_seguido").count() == 0


def test_admin_elimina_usuario_con_documentos_y_notificaciones(client, db):
    """Paso 1: al borrar un usuario, las notificaciones ajenas que referencian
    sus DocumentoCambio no rompen el FK notificacion_documento_cambio_id_fkey."""
    from app.extensions import db as _db
    from app.models import DocumentoCambio
    _login_admin(client, db)
    u = _crear_usuario(client, db, email="borrar@test.es")
    observer = _crear_usuario(client, db, email="observer@test.es")

    doc = DocumentoCambio(
        creado_por_id=u.id,
        unidad_id=u.unidad_id,
        numero_unidad=1,
    )
    _db.session.add(doc)
    _db.session.flush()
    _db.session.add(Notificacion(
        usuario_id=observer.id,
        unidad_id=observer.unidad_id,
        documento_cambio_id=doc.id,
        tipo="documento_cambio_pendiente_firma",
    ))
    _db.session.commit()

    uid = u.id
    doc_id = doc.id
    resp = client.post(
        f"/admin/usuarios/{u.id}/eliminar",
        data={"csrf_token": ""},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert Usuario.query.filter_by(id=uid).count() == 0
    assert Notificacion.query.filter_by(documento_cambio_id=doc_id).count() == 0


def test_admin_elimina_usuario_sin_notificaciones_sigue_funcionando(client, db):
    """Paso 1 — regresión: borrar un usuario sin notificaciones no se rompe
    tras el fix de las notificaciones con FK a documento_cambio."""
    _login_admin(client, db)
    u = _crear_usuario(client, db, email="borrar@test.es")
    uid = u.id
    resp = client.post(
        f"/admin/usuarios/{u.id}/eliminar",
        data={"csrf_token": ""},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert Usuario.query.filter_by(id=uid).count() == 0
