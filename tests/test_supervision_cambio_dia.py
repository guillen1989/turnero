"""Paso 4.2 del plan de cambios en el día: un DocumentoCambio cuyo cede y
recibe caen el mismo día (distinta franja) debe pasar por el flujo de
supervisión exactamente igual que uno normal -- ni el listado, ni
autorizar/denegar, ni anular distinguen por fecha_cede == fecha_recibe."""
from datetime import date, timedelta

from tests.helpers_documento_cambio import (
    _setup,
    _login,
    _FIRMA_PNG,
    _crear_documento_completo,
    _fecha_futura,
)


def test_supervisora_ve_documento_cambio_dia_pendiente_de_decision(db, client):
    crear_usuario, manyana, tarde = _setup(db, "cd1")
    claudia = crear_usuario("Claudia Pérez", "claudiacd1@h.es")
    juan = crear_usuario("Juan Rodríguez", "juancd1@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martacd1@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    fecha = _fecha_futura(10)
    doc = _crear_documento_completo(db, claudia, juan, manyana, tarde, fecha, fecha)
    assert doc.decision_supervisora == "pendiente"

    _login(client, supervisora.email)
    resp = client.get("/documentos-cambio/supervisora",
                       query_string={"anyo": fecha.year, "mes": fecha.month})
    assert f"<td>cambio #{doc.numero_unidad} del {doc.fecha_creacion.strftime('%d/%m/%Y')}</td>".encode() in resp.data


def test_solo_supervisora_puede_autorizar_documento_cambio_dia(db, client):
    crear_usuario, manyana, tarde = _setup(db, "cd2")
    claudia = crear_usuario("Claudia Pérez", "claudiacd2@h.es")
    juan = crear_usuario("Juan Rodríguez", "juancd2@h.es")

    fecha = _fecha_futura(10)
    doc = _crear_documento_completo(db, claudia, juan, manyana, tarde, fecha, fecha)

    _login(client, claudia.email)
    resp = client.post(f"/documentos-cambio/{doc.id}/autorizar", data={"imagen_firma": _FIRMA_PNG})
    assert resp.status_code == 403


def test_supervisora_autoriza_documento_cambio_dia_y_vuelca_planillas_del_mismo_dia(db, client):
    from app.models import TurnoPlanilla

    crear_usuario, manyana, tarde = _setup(db, "cd3")
    claudia = crear_usuario("Claudia Pérez", "claudiacd3@h.es")
    juan = crear_usuario("Juan Rodríguez", "juancd3@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martacd3@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    fecha = _fecha_futura(10)
    doc = _crear_documento_completo(db, claudia, juan, manyana, tarde, fecha, fecha)

    _login(client, supervisora.email)
    resp = client.post(f"/documentos-cambio/{doc.id}/autorizar", data={"imagen_firma": _FIRMA_PNG})
    assert resp.status_code == 302

    assert doc.decision_supervisora == "autorizado"
    assert TurnoPlanilla.query.filter_by(
        usuario_id=claudia.id, fecha=fecha, franja_horaria_id=tarde.id
    ).first() is not None
    assert TurnoPlanilla.query.filter_by(
        usuario_id=claudia.id, fecha=fecha, franja_horaria_id=manyana.id
    ).first() is None


def test_supervisora_anula_documento_cambio_dia_autorizado(db, client):
    from app.services.documento_cambio import autorizar_documento

    crear_usuario, manyana, tarde = _setup(db, "cd4")
    claudia = crear_usuario("Claudia Pérez", "claudiacd4@h.es")
    juan = crear_usuario("Juan Rodríguez", "juancd4@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martacd4@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    fecha = _fecha_futura(10)
    doc = _crear_documento_completo(db, claudia, juan, manyana, tarde, fecha, fecha)
    autorizar_documento(doc, supervisora)

    _login(client, supervisora.email)
    resp = client.post(f"/documentos-cambio/{doc.id}/anular",
                       data={"motivo": "Error de planificación"}, follow_redirects=True)
    assert resp.status_code == 200

    assert doc.anulado is True
    from app.models import TurnoPlanilla
    assert TurnoPlanilla.query.filter_by(
        usuario_id=claudia.id, fecha=fecha, franja_horaria_id=manyana.id
    ).first() is not None
