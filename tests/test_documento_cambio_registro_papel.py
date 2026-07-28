from datetime import date, time, timedelta

from app.extensions import db
from app.models import Categoria, FranjaHoraria, GrupoIntercambio, Hospital, Unidad, Usuario
from tests.helpers_documento_cambio import _setup, _login, _mes_actual_y_siguiente


def test_registrar_papel_requiere_login(client):
    resp = client.get("/documentos-cambio/registrar-papel")
    assert resp.status_code == 302


def test_no_supervisora_no_puede_ver_registrar_papel(db, client):
    crear_usuario, manyana, tarde = _setup(db, "papelno")
    claudia = crear_usuario("Claudia Pérez", "claudiapapelno@h.es")
    _login(client, claudia.email)

    resp = client.get("/documentos-cambio/registrar-papel")
    assert resp.status_code == 403


def test_get_registrar_papel_lista_trabajadores_del_grupo(db, client):
    crear_usuario, manyana, tarde = _setup(db, "papelget")
    claudia = crear_usuario("Claudia Pérez", "claudiapapelget@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanpapelget@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martapapelget@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    _login(client, supervisora.email)
    resp = client.get("/documentos-cambio/registrar-papel")

    assert resp.status_code == 200
    assert "Claudia Pérez".encode("utf-8") in resp.data
    assert "Juan Rodríguez".encode("utf-8") in resp.data


def test_get_registrar_papel_preselecciona_trabajador_y_fecha_desde_query(db, client):
    """Enlace desde /planilla/supervision al hacer clic en el día de un
    trabajador: preselecciona a ese trabajador y esa fecha en el formulario."""
    crear_usuario, manyana, tarde = _setup(db, "papelprefill")
    claudia = crear_usuario("Claudia Pérez", "claudiapapelprefill@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martapapelprefill@h.es")
    supervisora.es_supervisora = True
    db.session.commit()
    _login(client, supervisora.email)

    resp = client.get(
        f"/documentos-cambio/registrar-papel?usuario1_id={claudia.id}&fecha=2026-07-15"
    )

    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert f'<option value="{claudia.id}" selected>' in html
    assert 'value="2026-07-15"' in html
    # El filtro de turnos debe dispararse al cargar cuando hay valores preseleccionados
    assert "actualizarCede();" in html


def test_post_registrar_papel_crea_documento_autorizado_y_redirige(db, client):
    crear_usuario, manyana, tarde = _setup(db, "papelpost")
    claudia = crear_usuario("Claudia Pérez", "claudiapapelpost@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanpapelpost@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martapapelpost@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    _login(client, supervisora.email)
    resp = client.post("/documentos-cambio/registrar-papel", data={
        "usuario1_id": claudia.id,
        "usuario2_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
    })

    assert resp.status_code == 302
    assert "/documentos-cambio/" in resp.headers["Location"]

    from app.models import DocumentoCambio
    documento = DocumentoCambio.query.order_by(DocumentoCambio.id.desc()).first()
    assert documento.origen_papel is True
    assert documento.decision_supervisora == "autorizado"


def test_post_registrar_papel_no_factible_avisa_y_no_aplica(db, client):
    from app.models import DocumentoCambio, PlanillaMes

    crear_usuario, manyana, tarde = _setup(db, "papelnofact")
    claudia = crear_usuario("Claudia Pérez", "claudiapapelnofact@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanpapelnofact@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martapapelnofact@h.es")
    supervisora.es_supervisora = True
    db.session.add_all([
        PlanillaMes(usuario=claudia, anyo=2026, mes=7, publicada=True),
        PlanillaMes(usuario=juan, anyo=2026, mes=7, publicada=True),
    ])
    db.session.commit()
    _login(client, supervisora.email)

    numero_antes = DocumentoCambio.query.count()
    resp = client.post("/documentos-cambio/registrar-papel", data={
        "usuario1_id": claudia.id,
        "usuario2_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert "no es factible".encode("utf-8") in resp.data
    assert DocumentoCambio.query.count() == numero_antes


def test_post_registrar_papel_exige_misma_categoria(db, client):
    hospital = None
    from app.models import Hospital, GrupoIntercambio, Unidad, Categoria
    hospital = Hospital(nombre="Hospital catx")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()
    unidad = Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo)
    cat_a = Categoria(nombre="Enfermería catx")
    cat_b = Categoria(nombre="Auxiliar catx")
    db.session.add_all([unidad, cat_a, cat_b])
    db.session.commit()

    claudia = Usuario(nombre="Claudia Pérez", email="claudiacatx@h.es", unidad=unidad, categoria=cat_a)
    claudia.set_password("password123")
    juan = Usuario(nombre="Juan Rodríguez", email="juancatx@h.es", unidad=unidad, categoria=cat_b)
    juan.set_password("password123")
    supervisora = Usuario(nombre="Marta Supervisora", email="martacatx@h.es", unidad=unidad, categoria=cat_a)
    supervisora.set_password("password123")
    supervisora.es_supervisora = True
    db.session.add_all([claudia, juan, supervisora])
    db.session.commit()

    manyana = FranjaHoraria(nombre="Mañana", hora_inicio=time(7, 0), hora_fin=time(15, 0), grupo_intercambio=grupo)
    db.session.add(manyana)
    db.session.commit()

    _login(client, supervisora.email)
    resp = client.post("/documentos-cambio/registrar-papel", data={
        "usuario1_id": claudia.id,
        "usuario2_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
    })

    assert resp.status_code == 200
    assert "misma categoría".encode("utf-8") in resp.data


def test_supervisora_ve_badge_de_papel_en_la_tabla(db, client):
    from app.services.documento_cambio import registrar_documento_cambio_papel

    crear_usuario, manyana, tarde = _setup(db, "papelbadge")
    claudia = crear_usuario("Claudia Pérez", "claudiapapelbadge@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanpapelbadge@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martapapelbadge@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    fecha_este_mes, _ = _mes_actual_y_siguiente()
    registrar_documento_cambio_papel(
        supervisora=supervisora, usuario1=claudia, usuario2=juan,
        turno1_cede_fecha=fecha_este_mes, turno1_cede_franja_id=manyana.id,
        turno1_recibe_fecha=fecha_este_mes + timedelta(days=1), turno1_recibe_franja_id=manyana.id,
    )

    _login(client, supervisora.email)
    resp = client.get("/documentos-cambio/supervisora")

    assert resp.status_code == 200
    assert "Papel".encode("utf-8") in resp.data
