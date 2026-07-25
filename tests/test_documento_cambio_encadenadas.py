from datetime import date, time, timedelta

from app.extensions import db
from app.models import Categoria, FranjaHoraria, GrupoIntercambio, Hospital, Unidad, Usuario
from tests.helpers_documento_cambio import _setup, _login, _mes_actual_y_siguiente, _crear_documento_pendiente


def test_get_nuevo_incluye_hojas_pendientes_en_select(db, client):
    """El select de dependencia lista las hojas pendientes de la misma unidad."""
    crear_usuario, manyana, tarde = _setup(db, "enc1")
    claudia = crear_usuario("Claudiaen1", "claudiaen1@h.es")
    juan = crear_usuario("Juanen1", "juanen1@h.es")

    # Crear un documento completo y pendiente
    fecha_este_mes, _ = _mes_actual_y_siguiente()
    doc_pendiente = _crear_documento_pendiente(
        db, claudia, juan, manyana, tarde,
        fecha_este_mes, fecha_este_mes + timedelta(days=1),
    )

    _login(client, claudia.email)
    resp = client.get("/documentos-cambio/nuevo")
    assert resp.status_code == 200

    html = resp.data.decode("utf-8")
    assert 'id="depende_de_id"' in html
    assert f'value="{doc_pendiente.id}"' in html
    assert f"Hoja nº {doc_pendiente.numero_unidad}" in html or f"Hoja n.º {doc_pendiente.numero_unidad}" in html


def test_post_nuevo_con_depende_de_id(db, client):
    """POST /nuevo con depende_de_id crea el documento con la FK correcta."""
    from app.models import DocumentoCambio

    crear_usuario, manyana, tarde = _setup(db, "enc2")
    claudia = crear_usuario("Claudiaen2", "claudiaen2@h.es")
    juan = crear_usuario("Juanen2", "juanen2@h.es")

    fecha_este_mes, _ = _mes_actual_y_siguiente()
    doc_pendiente = _crear_documento_pendiente(
        db, claudia, juan, manyana, tarde,
        fecha_este_mes, fecha_este_mes + timedelta(days=1),
    )

    _login(client, claudia.email)
    resp = client.post("/documentos-cambio/nuevo", data={
        "companero_id": juan.id,
        "turno_cede_fecha": fecha_este_mes.isoformat(),
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": (fecha_este_mes + timedelta(days=2)).isoformat(),
        "turno_recibe_franja_id": manyana.id,
        "depende_de_id": doc_pendiente.id,
    })

    assert resp.status_code == 302
    documento_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])
    documento = db.session.get(DocumentoCambio, documento_id)
    assert documento.depende_de_id == doc_pendiente.id


def test_get_registrar_papel_incluye_hojas_pendientes(db, client):
    """El formulario de registrar papel muestra las hojas pendientes de la unidad."""
    crear_usuario, manyana, tarde = _setup(db, "enc3")
    claudia = crear_usuario("Claudiaen3", "claudiaen3@h.es")
    juan = crear_usuario("Juanen3", "juanen3@h.es")
    supervisora = crear_usuario("Martaen3", "martaen3@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    fecha_este_mes, _ = _mes_actual_y_siguiente()
    doc_pendiente = _crear_documento_pendiente(
        db, claudia, juan, manyana, tarde,
        fecha_este_mes, fecha_este_mes + timedelta(days=1),
    )

    _login(client, supervisora.email)
    resp = client.get("/documentos-cambio/registrar-papel")
    assert resp.status_code == 200

    html = resp.data.decode("utf-8")
    assert 'id="depende_de_id"' in html
    assert f'value="{doc_pendiente.id}"' in html


def test_post_registrar_papel_con_depende_de_id(db, client):
    """POST /registrar-papel con depende_de_id crea el documento con la FK."""
    from app.models import DocumentoCambio

    crear_usuario, manyana, tarde = _setup(db, "enc4")
    claudia = crear_usuario("Claudiaen4", "claudiaen4@h.es")
    juan = crear_usuario("Juanen4", "juanen4@h.es")
    supervisora = crear_usuario("Martaen4", "martaen4@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    fecha_este_mes, _ = _mes_actual_y_siguiente()
    doc_pendiente = _crear_documento_pendiente(
        db, claudia, juan, manyana, tarde,
        fecha_este_mes, fecha_este_mes + timedelta(days=7),
    )

    _login(client, supervisora.email)
    resp = client.post("/documentos-cambio/registrar-papel", data={
        "usuario1_id": claudia.id,
        "usuario2_id": juan.id,
        "turno_cede_fecha": fecha_este_mes.isoformat(),
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": (fecha_este_mes + timedelta(days=7)).isoformat(),
        "turno_recibe_franja_id": manyana.id,
        "depende_de_id": doc_pendiente.id,
    })

    assert resp.status_code == 302
    documento_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])
    documento = db.session.get(DocumentoCambio, documento_id)
    assert documento.depende_de_id == doc_pendiente.id
