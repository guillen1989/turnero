from datetime import date, time, timedelta

from app.extensions import db
from app.models import Categoria, FranjaHoraria, GrupoIntercambio, Hospital, Unidad, Usuario
from tests.helpers_documento_cambio import _setup, _login, _FIRMA_PNG, _crear_documento_completo, _fecha_futura


def test_bloque_requiere_supervisora(db, client):
    crear_usuario, manyana, tarde = _setup(db, "e2")
    claudia = crear_usuario("Claudia Pérez", "claudiae2@h.es")
    _login(client, claudia.email)

    resp = client.post("/documentos-cambio/supervisora/bloque/aceptar", data={"documento_ids": []})
    assert resp.status_code == 403


def test_bloque_aceptar_aplica_a_pendientes_y_omite_el_resto(db, client):
    crear_usuario, manyana, tarde = _setup(db, "f2")
    claudia = crear_usuario("Claudia Pérez", "claudiaf2@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanf2@h.es")
    ana = crear_usuario("Ana Gómez", "anaf2@h.es")
    luis = crear_usuario("Luis Ibáñez", "luisf2@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martaf2@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    from app.services.documento_cambio import autorizar_documento

    supervisora.firma_guardada = _FIRMA_PNG
    db.session.commit()

    doc_pendiente = _crear_documento_completo(db, claudia, juan, manyana, manyana, _fecha_futura(10), _fecha_futura(20))
    doc_ya_autorizado = _crear_documento_completo(db, ana, luis, manyana, manyana, _fecha_futura(10), _fecha_futura(21))
    autorizar_documento(doc_ya_autorizado, supervisora)

    _login(client, supervisora.email)
    resp = client.post("/documentos-cambio/supervisora/bloque/aceptar",
                       data={"documento_ids": [doc_pendiente.id, doc_ya_autorizado.id]},
                       follow_redirects=True)
    assert resp.status_code == 200
    assert doc_pendiente.decision_supervisora == "autorizado"
    assert doc_pendiente.firma_supervisora == _FIRMA_PNG
    assert "1 aceptados".encode("utf-8") in resp.data


def test_bloque_aceptar_requiere_firma_guardada(db, client):
    crear_usuario, manyana, tarde = _setup(db, "f3")
    claudia = crear_usuario("Claudia Pérez", "claudiaf3@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanf3@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martaf3@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    doc = _crear_documento_completo(db, claudia, juan, manyana, manyana, _fecha_futura(10), _fecha_futura(20))

    _login(client, supervisora.email)
    client.post("/documentos-cambio/supervisora/bloque/aceptar", data={"documento_ids": [doc.id]})
    assert doc.decision_supervisora == "pendiente"


def test_bloque_denegar_requiere_motivo(db, client):
    crear_usuario, manyana, tarde = _setup(db, "g2")
    claudia = crear_usuario("Claudia Pérez", "claudiag2@h.es")
    juan = crear_usuario("Juan Rodríguez", "juang2@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martag2@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    doc = _crear_documento_completo(db, claudia, juan, manyana, manyana, _fecha_futura(10), _fecha_futura(20))

    _login(client, supervisora.email)
    client.post("/documentos-cambio/supervisora/bloque/denegar",
               data={"documento_ids": [doc.id], "motivo": ""})
    assert doc.decision_supervisora == "pendiente"


def test_bloque_denegar_aplica_el_mismo_motivo_a_todos(db, client):
    crear_usuario, manyana, tarde = _setup(db, "h2")
    claudia = crear_usuario("Claudia Pérez", "claudiah2@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanh2@h.es")
    ana = crear_usuario("Ana Gómez", "anah2@h.es")
    luis = crear_usuario("Luis Ibáñez", "luish2@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martah2@h.es")
    supervisora.es_supervisora = True
    supervisora.firma_guardada = _FIRMA_PNG
    db.session.commit()

    doc1 = _crear_documento_completo(db, claudia, juan, manyana, manyana, _fecha_futura(10), _fecha_futura(20))
    doc2 = _crear_documento_completo(db, ana, luis, manyana, manyana, _fecha_futura(10), _fecha_futura(21))

    _login(client, supervisora.email)
    client.post("/documentos-cambio/supervisora/bloque/denegar",
               data={"documento_ids": [doc1.id, doc2.id], "motivo": "Motivo compartido"})

    assert doc1.decision_supervisora == "denegado"
    assert doc1.motivo_denegacion == "Motivo compartido"
    assert doc1.firma_supervisora == _FIRMA_PNG
    assert doc2.decision_supervisora == "denegado"
    assert doc2.motivo_denegacion == "Motivo compartido"


def test_bloque_denegar_requiere_firma_guardada(db, client):
    crear_usuario, manyana, tarde = _setup(db, "h3")
    claudia = crear_usuario("Claudia Pérez", "claudiah3@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanh3@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martah3@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    doc = _crear_documento_completo(db, claudia, juan, manyana, manyana, _fecha_futura(10), _fecha_futura(20))

    _login(client, supervisora.email)
    client.post("/documentos-cambio/supervisora/bloque/denegar",
               data={"documento_ids": [doc.id], "motivo": "motivo"})
    assert doc.decision_supervisora == "pendiente"


def test_bloque_anular_aplica_solo_a_elegibles(db, client):
    from app.services.documento_cambio import autorizar_documento

    crear_usuario, manyana, tarde = _setup(db, "i2")
    claudia = crear_usuario("Claudia Pérez", "claudiai2@h.es")
    juan = crear_usuario("Juan Rodríguez", "juani2@h.es")
    ana = crear_usuario("Ana Gómez", "anai2@h.es")
    luis = crear_usuario("Luis Ibáñez", "luisi2@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martai2@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    doc_autorizado = _crear_documento_completo(db, claudia, juan, manyana, manyana, _fecha_futura(10), _fecha_futura(20))
    autorizar_documento(doc_autorizado, supervisora)

    doc_pendiente = _crear_documento_completo(db, ana, luis, manyana, manyana, _fecha_futura(10), _fecha_futura(21))

    _login(client, supervisora.email)
    client.post("/documentos-cambio/supervisora/bloque/anular",
               data={"documento_ids": [doc_autorizado.id, doc_pendiente.id], "motivo": "motivo"})

    assert doc_autorizado.anulado is True
    assert doc_pendiente.anulado is False


def test_bloque_ignora_ids_que_no_pertenecen_al_grupo(db, client):
    crear_usuario, manyana, tarde = _setup(db, "j2")
    claudia = crear_usuario("Claudia Pérez", "claudiaj2@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanj2@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martaj2@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    crear_usuario_otro, manyana_otro, tarde_otro = _setup(db, "k2")
    ana = crear_usuario_otro("Ana Gómez", "anak2@h.es")
    luis = crear_usuario_otro("Luis Ibáñez", "luisk2@h.es")
    doc_otro_grupo = _crear_documento_completo(db, ana, luis, manyana_otro, manyana_otro, _fecha_futura(10), _fecha_futura(20))

    _login(client, supervisora.email)
    resp = client.post("/documentos-cambio/supervisora/bloque/aceptar",
                       data={"documento_ids": [doc_otro_grupo.id]}, follow_redirects=True)
    assert resp.status_code == 200
    assert doc_otro_grupo.decision_supervisora == "pendiente"


def test_bloque_pdf_combina_los_seleccionados(db, client):
    import io
    from pypdf import PdfReader

    crear_usuario, manyana, tarde = _setup(db, "l2")
    claudia = crear_usuario("Claudia Pérez", "claudial2@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanl2@h.es")
    ana = crear_usuario("Ana Gómez", "anal2@h.es")
    luis = crear_usuario("Luis Ibáñez", "luisl2@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martal2@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    doc1 = _crear_documento_completo(db, claudia, juan, manyana, manyana, _fecha_futura(10), _fecha_futura(20))
    doc2 = _crear_documento_completo(db, ana, luis, manyana, manyana, _fecha_futura(10), _fecha_futura(21))

    _login(client, supervisora.email)
    resp = client.post("/documentos-cambio/supervisora/bloque/pdf",
                       data={"documento_ids": [doc1.id, doc2.id]})
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "application/pdf"

    lector = PdfReader(io.BytesIO(resp.data))
    assert len(lector.pages) == 2
