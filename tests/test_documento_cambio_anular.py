from datetime import date, time, timedelta

from app.extensions import db
from app.models import Categoria, FranjaHoraria, GrupoIntercambio, Hospital, Unidad, Usuario
from tests.helpers_documento_cambio import _setup, _login, _crear_documento_completo, _fecha_futura, _crear_y_autorizar


def test_anular_requiere_supervisora(db, client):
    crear_usuario, manyana, tarde = _setup(db, "xx")
    claudia = crear_usuario("Claudia Pérez", "claudiaxx@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanxx@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martaxx@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    doc = _crear_y_autorizar(db, client, claudia, juan, supervisora, manyana)

    _login(client, claudia.email)
    resp = client.post(f"/documentos-cambio/{doc.id}/anular", data={"motivo": "x"})
    assert resp.status_code == 403


def test_anular_exitoso_marca_anulado_y_deshace_planilla(db, client):
    from app.models import TurnoPlanilla

    crear_usuario, manyana, tarde = _setup(db, "yy")
    claudia = crear_usuario("Claudia Pérez", "claudiayy@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanyy@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martayy@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    fecha_cede, fecha_recibe = _fecha_futura(10), _fecha_futura(20)
    from app.services.documento_cambio import autorizar_documento
    doc = _crear_documento_completo(db, claudia, juan, manyana, manyana, fecha_cede, fecha_recibe)
    autorizar_documento(doc, supervisora)

    _login(client, supervisora.email)
    resp = client.post(f"/documentos-cambio/{doc.id}/anular",
                       data={"motivo": "Ya no hace falta"}, follow_redirects=True)
    assert resp.status_code == 200

    assert doc.anulado is True
    assert doc.motivo_anulacion == "Ya no hace falta"
    assert TurnoPlanilla.query.filter_by(
        usuario_id=claudia.id, fecha=fecha_cede, franja_horaria_id=manyana.id
    ).first() is not None


def test_anular_sin_motivo_no_anula(db, client):
    crear_usuario, manyana, tarde = _setup(db, "zz")
    claudia = crear_usuario("Claudia Pérez", "claudiazz@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanzz@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martazz@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    doc = _crear_y_autorizar(db, client, claudia, juan, supervisora, manyana)

    _login(client, supervisora.email)
    client.post(f"/documentos-cambio/{doc.id}/anular", data={"motivo": ""})
    assert doc.anulado is False


def test_no_se_puede_anular_si_el_turno_ya_paso(db, client):
    from app.services.documento_cambio import autorizar_documento

    crear_usuario, manyana, tarde = _setup(db, "a2")
    claudia = crear_usuario("Claudia Pérez", "claudiaa2@h.es")
    juan = crear_usuario("Juan Rodríguez", "juana2@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martaa2@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    hoy = date.today()
    doc = _crear_documento_completo(
        db, claudia, juan, manyana, manyana, hoy - timedelta(days=3), hoy + timedelta(days=10),
    )
    autorizar_documento(doc, supervisora)

    _login(client, supervisora.email)
    client.post(f"/documentos-cambio/{doc.id}/anular", data={"motivo": "motivo"})
    assert doc.anulado is False


def test_no_se_puede_anular_dos_veces(db, client):
    crear_usuario, manyana, tarde = _setup(db, "b2")
    claudia = crear_usuario("Claudia Pérez", "claudiab2@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanb2@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martab2@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    doc = _crear_y_autorizar(db, client, claudia, juan, supervisora, manyana)

    _login(client, supervisora.email)
    client.post(f"/documentos-cambio/{doc.id}/anular", data={"motivo": "primera"})
    client.post(f"/documentos-cambio/{doc.id}/anular", data={"motivo": "segunda"})
    assert doc.motivo_anulacion == "primera"


def test_ver_muestra_boton_anular_cuando_es_elegible(db, client):
    crear_usuario, manyana, tarde = _setup(db, "c2")
    claudia = crear_usuario("Claudia Pérez", "claudiac2@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanc2@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martac2@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    doc = _crear_y_autorizar(db, client, claudia, juan, supervisora, manyana)

    _login(client, supervisora.email)
    resp = client.get(f"/documentos-cambio/{doc.id}")
    assert "Anular".encode("utf-8") in resp.data
    assert f'action="/documentos-cambio/{doc.id}/anular"'.encode() in resp.data


def test_supervisora_filtra_por_anulado(db, client):
    crear_usuario, manyana, tarde = _setup(db, "d2")
    claudia = crear_usuario("Claudia Pérez", "claudiad2@h.es")
    juan = crear_usuario("Juan Rodríguez", "juand2@h.es")
    ana = crear_usuario("Ana Gómez", "anad2@h.es")
    luis = crear_usuario("Luis Ibáñez", "luisd2@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martad2@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    from app.services.documento_cambio import autorizar_documento, anular_documento

    doc_anulado = _crear_documento_completo(db, claudia, juan, manyana, manyana, _fecha_futura(10), _fecha_futura(20))
    autorizar_documento(doc_anulado, supervisora)
    anular_documento(doc_anulado, supervisora, "motivo")

    doc_vigente = _crear_documento_completo(db, ana, luis, manyana, manyana, _fecha_futura(10), _fecha_futura(21))
    autorizar_documento(doc_vigente, supervisora)

    _login(client, supervisora.email)
    resp = client.get("/documentos-cambio/supervisora",
                       query_string={"anyo": _fecha_futura(10).year, "mes": _fecha_futura(10).month,
                                     "estado_decision": "anulado"})
    assert f"<td>cambio #{doc_anulado.numero_unidad} del {doc_anulado.fecha_creacion.strftime('%d/%m/%Y')}</td>".encode() in resp.data
    assert f"<td>cambio #{doc_vigente.numero_unidad} del {doc_vigente.fecha_creacion.strftime('%d/%m/%Y')}</td>".encode() not in resp.data

    resp_autorizado = client.get("/documentos-cambio/supervisora",
                                  query_string={"anyo": _fecha_futura(10).year, "mes": _fecha_futura(10).month,
                                                "estado_decision": "autorizado"})
    assert f"<td>cambio #{doc_vigente.numero_unidad} del {doc_vigente.fecha_creacion.strftime('%d/%m/%Y')}</td>".encode() in resp_autorizado.data
    assert f"<td>cambio #{doc_anulado.numero_unidad} del {doc_anulado.fecha_creacion.strftime('%d/%m/%Y')}</td>".encode() not in resp_autorizado.data
