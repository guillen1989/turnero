from datetime import date, time, timedelta

from app.extensions import db
from app.models import Categoria, FranjaHoraria, GrupoIntercambio, Hospital, Unidad, Usuario
from tests.helpers_documento_cambio import _setup, _login, _FIRMA_PNG, _mes_actual_y_siguiente, _crear_documento_completo, _crear_documento_completo_via_client


def test_supervisora_no_ve_cambios_pendientes_de_firma(db, client):
    """Un cambio con alguna firma pendiente todavía no le ha 'llegado' a la
    supervisora -- no debe aparecer en su lista ni ser accionable."""
    from app.services.documento_cambio import crear_documento_cambio

    crear_usuario, manyana, tarde = _setup(db, "nn")
    claudia = crear_usuario("Claudia Pérez", "claudiann@h.es")
    juan = crear_usuario("Juan Rodríguez", "juann@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martann@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    fecha_este_mes, _fecha_sig = _mes_actual_y_siguiente()
    doc = crear_documento_cambio(
        claudia, juan, fecha_este_mes, manyana.id,
        fecha_este_mes + timedelta(days=7), tarde.id,
    )
    assert doc.estado == "borrador"

    _login(client, supervisora.email)
    resp = client.get("/documentos-cambio/supervisora")
    assert f"<td>cambio #{doc.numero_unidad} del {doc.fecha_creacion.strftime('%d/%m/%Y')}</td>".encode() not in resp.data
    assert "No hay hojas de cambio completas".encode("utf-8") in resp.data


def test_filtro_mes_por_defecto_es_el_mes_en_curso(db, client):
    crear_usuario, manyana, tarde = _setup(db, "oo")
    claudia = crear_usuario("Claudia Pérez", "claudiaoo@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanoo@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martaoo@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    fecha_este_mes, fecha_mes_siguiente = _mes_actual_y_siguiente()
    doc_este_mes = _crear_documento_completo(db, claudia, juan, manyana, tarde,
                                              fecha_este_mes, fecha_este_mes + timedelta(days=3))
    doc_mes_siguiente = _crear_documento_completo(db, claudia, juan, manyana, tarde,
                                                   fecha_mes_siguiente, fecha_mes_siguiente + timedelta(days=3))

    _login(client, supervisora.email)
    resp = client.get("/documentos-cambio/supervisora")
    assert f"<td>cambio #{doc_este_mes.numero_unidad} del {doc_este_mes.fecha_creacion.strftime('%d/%m/%Y')}</td>".encode() in resp.data
    assert f"<td>cambio #{doc_mes_siguiente.numero_unidad} del {doc_mes_siguiente.fecha_creacion.strftime('%d/%m/%Y')}</td>".encode() not in resp.data


def test_filtro_mes_anyo_navega_a_otro_mes(db, client):
    crear_usuario, manyana, tarde = _setup(db, "pp")
    claudia = crear_usuario("Claudia Pérez", "claudiapp@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanpp@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martapp@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    fecha_este_mes, fecha_mes_siguiente = _mes_actual_y_siguiente()
    doc = _crear_documento_completo(db, claudia, juan, manyana, tarde,
                                     fecha_mes_siguiente, fecha_mes_siguiente + timedelta(days=3))

    _login(client, supervisora.email)
    resp = client.get("/documentos-cambio/supervisora",
                       query_string={"mes": fecha_mes_siguiente.month, "anyo": fecha_mes_siguiente.year})
    assert f"<td>cambio #{doc.numero_unidad} del {doc.fecha_creacion.strftime('%d/%m/%Y')}</td>".encode() in resp.data


def test_filtro_fecha_exacta_ignora_mes_anyo(db, client):
    crear_usuario, manyana, tarde = _setup(db, "qq")
    claudia = crear_usuario("Claudia Pérez", "claudiaqq@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanqq@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martaqq@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    fecha_este_mes, fecha_mes_siguiente = _mes_actual_y_siguiente()
    doc = _crear_documento_completo(db, claudia, juan, manyana, tarde,
                                     fecha_mes_siguiente, fecha_mes_siguiente + timedelta(days=10))

    _login(client, supervisora.email)
    resp = client.get("/documentos-cambio/supervisora",
                       query_string={"fecha": fecha_mes_siguiente.isoformat()})
    assert f"<td>cambio #{doc.numero_unidad} del {doc.fecha_creacion.strftime('%d/%m/%Y')}</td>".encode() in resp.data


def test_filtro_por_un_trabajador(db, client):
    crear_usuario, manyana, tarde = _setup(db, "rr")
    claudia = crear_usuario("Claudia Pérez", "claudiarr@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanrr@h.es")
    ana = crear_usuario("Ana Gómez", "anarr@h.es")
    luis = crear_usuario("Luis Ibáñez", "luisrr@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martarr@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    fecha_este_mes, _ = _mes_actual_y_siguiente()
    doc_claudia = _crear_documento_completo(db, claudia, juan, manyana, tarde, fecha_este_mes, fecha_este_mes + timedelta(days=1))
    doc_ana = _crear_documento_completo(db, ana, luis, manyana, tarde, fecha_este_mes, fecha_este_mes + timedelta(days=2))

    _login(client, supervisora.email)
    resp = client.get("/documentos-cambio/supervisora", query_string={"trabajador1_id": claudia.id})
    assert f"<td>cambio #{doc_claudia.numero_unidad} del {doc_claudia.fecha_creacion.strftime('%d/%m/%Y')}</td>".encode() in resp.data
    assert f"<td>cambio #{doc_ana.numero_unidad} del {doc_ana.fecha_creacion.strftime('%d/%m/%Y')}</td>".encode() not in resp.data


def test_filtro_por_dos_trabajadores_exige_el_cambio_exacto_entre_ambos(db, client):
    crear_usuario, manyana, tarde = _setup(db, "ss")
    claudia = crear_usuario("Claudia Pérez", "claudiass@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanss@h.es")
    ana = crear_usuario("Ana Gómez", "anass@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martass@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    fecha_este_mes, _ = _mes_actual_y_siguiente()
    doc_claudia_juan = _crear_documento_completo(db, claudia, juan, manyana, tarde, fecha_este_mes, fecha_este_mes + timedelta(days=1))
    doc_claudia_ana = _crear_documento_completo(db, claudia, ana, manyana, tarde, fecha_este_mes, fecha_este_mes + timedelta(days=2))

    _login(client, supervisora.email)
    resp = client.get("/documentos-cambio/supervisora",
                       query_string={"trabajador1_id": claudia.id, "trabajador2_id": juan.id})
    assert f"<td>cambio #{doc_claudia_juan.numero_unidad} del {doc_claudia_juan.fecha_creacion.strftime('%d/%m/%Y')}</td>".encode() in resp.data
    assert f"<td>cambio #{doc_claudia_ana.numero_unidad} del {doc_claudia_ana.fecha_creacion.strftime('%d/%m/%Y')}</td>".encode() not in resp.data


def test_filtro_por_turno_afectado(db, client):
    crear_usuario, manyana, tarde = _setup(db, "tt")
    claudia = crear_usuario("Claudia Pérez", "claudiatt@h.es")
    juan = crear_usuario("Juan Rodríguez", "juantt@h.es")
    ana = crear_usuario("Ana Gómez", "anatt@h.es")
    luis = crear_usuario("Luis Ibáñez", "luistt@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martatt@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    fecha_este_mes, _ = _mes_actual_y_siguiente()
    doc_manyana = _crear_documento_completo(db, claudia, juan, manyana, tarde, fecha_este_mes, fecha_este_mes + timedelta(days=1))
    doc_tarde = _crear_documento_completo(db, ana, luis, tarde, tarde, fecha_este_mes, fecha_este_mes + timedelta(days=2))

    _login(client, supervisora.email)
    resp = client.get("/documentos-cambio/supervisora", query_string={"franja_id": manyana.id})
    assert f"<td>cambio #{doc_manyana.numero_unidad} del {doc_manyana.fecha_creacion.strftime('%d/%m/%Y')}</td>".encode() in resp.data
    assert f"<td>cambio #{doc_tarde.numero_unidad} del {doc_tarde.fecha_creacion.strftime('%d/%m/%Y')}</td>".encode() not in resp.data


def test_filtro_por_estado_decision(db, client):
    from app.services.documento_cambio import autorizar_documento, denegar_documento

    crear_usuario, manyana, tarde = _setup(db, "uu")
    claudia = crear_usuario("Claudia Pérez", "claudiauu@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanuu@h.es")
    ana = crear_usuario("Ana Gómez", "anauu@h.es")
    luis = crear_usuario("Luis Ibáñez", "luisuu@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martauu@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    fecha_este_mes, _ = _mes_actual_y_siguiente()
    doc_a = _crear_documento_completo(db, claudia, juan, manyana, tarde, fecha_este_mes, fecha_este_mes + timedelta(days=1))
    doc_b = _crear_documento_completo(db, ana, luis, manyana, tarde, fecha_este_mes, fecha_este_mes + timedelta(days=2))
    autorizar_documento(doc_a, supervisora)
    denegar_documento(doc_b, supervisora, "motivo")

    _login(client, supervisora.email)
    resp = client.get("/documentos-cambio/supervisora", query_string={"estado_decision": "autorizado"})
    assert f"<td>cambio #{doc_a.numero_unidad} del {doc_a.fecha_creacion.strftime('%d/%m/%Y')}</td>".encode() in resp.data
    assert f"<td>cambio #{doc_b.numero_unidad} del {doc_b.fecha_creacion.strftime('%d/%m/%Y')}</td>".encode() not in resp.data


def test_filtro_por_factibilidad(db, client):
    crear_usuario, manyana, tarde = _setup(db, "vv")
    claudia = crear_usuario("Claudia Pérez", "claudiavv@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanvv@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martavv@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    fecha_este_mes, _ = _mes_actual_y_siguiente()
    doc = _crear_documento_completo(db, claudia, juan, manyana, tarde, fecha_este_mes, fecha_este_mes + timedelta(days=1))
    assert doc.factibilidad_estado == "no_verificado"

    _login(client, supervisora.email)
    resp = client.get("/documentos-cambio/supervisora", query_string={"factibilidad": "no_verificado"})
    assert f"<td>cambio #{doc.numero_unidad} del {doc.fecha_creacion.strftime('%d/%m/%Y')}</td>".encode() in resp.data
    resp_factible = client.get("/documentos-cambio/supervisora", query_string={"factibilidad": "factible"})
    assert f"<td>cambio #{doc.numero_unidad} del {doc.fecha_creacion.strftime('%d/%m/%Y')}</td>".encode() not in resp_factible.data


def test_filtro_por_numero_de_hoja(db, client):
    crear_usuario, manyana, tarde = _setup(db, "ww")
    claudia = crear_usuario("Claudia Pérez", "claudiaww@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanww@h.es")
    ana = crear_usuario("Ana Gómez", "anaww@h.es")
    luis = crear_usuario("Luis Ibáñez", "luisww@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martaww@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    fecha_este_mes, _ = _mes_actual_y_siguiente()
    doc_a = _crear_documento_completo(db, claudia, juan, manyana, tarde, fecha_este_mes, fecha_este_mes + timedelta(days=1))
    doc_b = _crear_documento_completo(db, ana, luis, manyana, tarde, fecha_este_mes, fecha_este_mes + timedelta(days=2))

    _login(client, supervisora.email)
    resp = client.get("/documentos-cambio/supervisora", query_string={"numero": doc_a.numero_unidad})
    assert f"<td>cambio #{doc_a.numero_unidad} del {doc_a.fecha_creacion.strftime('%d/%m/%Y')}</td>".encode() in resp.data
    assert f"<td>cambio #{doc_b.numero_unidad} del {doc_b.fecha_creacion.strftime('%d/%m/%Y')}</td>".encode() not in resp.data


def test_supervisora_autoriza_y_vuelca_a_planillas(db, client):
    from app.models import DocumentoCambio, TurnoPlanilla

    crear_usuario, manyana, tarde = _setup(db, "kk")
    claudia = crear_usuario("Claudia Pérez", "claudiakk@h.es")
    juan = crear_usuario("Juan Rodríguez", "juankk@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martakk@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    _login(client, claudia.email)
    documento_id = _crear_documento_completo_via_client(client, claudia, juan, manyana)

    client.get("/auth/logout")
    _login(client, supervisora.email)
    resp = client.post(f"/documentos-cambio/{documento_id}/autorizar", data={"imagen_firma": _FIRMA_PNG})
    assert resp.status_code == 302

    documento = db.session.get(DocumentoCambio, documento_id)
    assert documento.decision_supervisora == "autorizado"
    assert documento.supervisora_id == supervisora.id
    assert documento.firma_supervisora == _FIRMA_PNG
    assert TurnoPlanilla.query.filter_by(
        usuario_id=claudia.id, fecha=date(2026, 7, 28), franja_horaria_id=manyana.id
    ).first() is not None


def test_supervisora_deniega_sin_tocar_planillas(db, client):
    from app.models import DocumentoCambio, TurnoPlanilla

    crear_usuario, manyana, tarde = _setup(db, "ll")
    claudia = crear_usuario("Claudia Pérez", "claudiall@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanll@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martall@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    _login(client, claudia.email)
    documento_id = _crear_documento_completo_via_client(client, claudia, juan, manyana)

    client.get("/auth/logout")
    _login(client, supervisora.email)
    resp = client.post(
        f"/documentos-cambio/{documento_id}/denegar",
        data={"motivo": "No coincide con la planilla real de ese mes.", "imagen_firma": _FIRMA_PNG},
    )
    assert resp.status_code == 302

    documento = db.session.get(DocumentoCambio, documento_id)
    assert documento.decision_supervisora == "denegado"
    assert documento.motivo_denegacion == "No coincide con la planilla real de ese mes."
    assert documento.firma_supervisora == _FIRMA_PNG
    assert TurnoPlanilla.query.filter_by(usuario_id=claudia.id).count() == 0


def test_denegar_sin_motivo_no_deniega(db, client):
    from app.models import DocumentoCambio

    crear_usuario, manyana, tarde = _setup(db, "oo")
    claudia = crear_usuario("Claudia Pérez", "claudiaoo@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanoo@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martaoo@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    _login(client, claudia.email)
    documento_id = _crear_documento_completo_via_client(client, claudia, juan, manyana)

    client.get("/auth/logout")
    _login(client, supervisora.email)
    client.post(f"/documentos-cambio/{documento_id}/denegar", data={"motivo": "   "})

    documento = db.session.get(DocumentoCambio, documento_id)
    assert documento.decision_supervisora == "pendiente"


def test_participante_ve_el_motivo_de_denegacion(db, client):
    crear_usuario, manyana, tarde = _setup(db, "pp")
    claudia = crear_usuario("Claudia Pérez", "claudiapp@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanpp@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martapp@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    _login(client, claudia.email)
    documento_id = _crear_documento_completo_via_client(client, claudia, juan, manyana)

    client.get("/auth/logout")
    _login(client, supervisora.email)
    client.post(
        f"/documentos-cambio/{documento_id}/denegar",
        data={"motivo": "Pedro ya tenía otro cambio ese día.", "imagen_firma": _FIRMA_PNG},
    )

    client.get("/auth/logout")
    _login(client, claudia.email)
    resp = client.get(f"/documentos-cambio/{documento_id}")
    assert "Pedro ya tenía otro cambio ese día.".encode("utf-8") in resp.data


def test_no_supervisora_no_puede_autorizar(db, client):
    crear_usuario, manyana, tarde = _setup(db, "mm")
    claudia = crear_usuario("Claudia Pérez", "claudiamm@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanmm@h.es")
    _login(client, claudia.email)
    documento_id = _crear_documento_completo_via_client(client, claudia, juan, manyana)

    client.get("/auth/logout")
    _login(client, claudia.email)
    resp = client.post(f"/documentos-cambio/{documento_id}/autorizar")
    assert resp.status_code == 403


def test_no_se_puede_autorizar_dos_veces(db, client):
    crear_usuario, manyana, tarde = _setup(db, "nn")
    claudia = crear_usuario("Claudia Pérez", "claudiann@h.es")
    juan = crear_usuario("Juan Rodríguez", "juannn@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martann@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    _login(client, claudia.email)
    documento_id = _crear_documento_completo_via_client(client, claudia, juan, manyana)

    client.get("/auth/logout")
    _login(client, supervisora.email)
    client.post(f"/documentos-cambio/{documento_id}/autorizar", data={"imagen_firma": _FIRMA_PNG})
    resp = client.post(f"/documentos-cambio/{documento_id}/autorizar", data={"imagen_firma": _FIRMA_PNG})
    assert resp.status_code == 409


def test_autorizar_sin_firma_no_autoriza(db, client):
    from app.models import DocumentoCambio

    crear_usuario, manyana, tarde = _setup(db, "n2")
    claudia = crear_usuario("Claudia Pérez", "claudian2@h.es")
    juan = crear_usuario("Juan Rodríguez", "juann2@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martan2@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    _login(client, claudia.email)
    documento_id = _crear_documento_completo_via_client(client, claudia, juan, manyana)

    client.get("/auth/logout")
    _login(client, supervisora.email)
    client.post(f"/documentos-cambio/{documento_id}/autorizar")

    documento = db.session.get(DocumentoCambio, documento_id)
    assert documento.decision_supervisora == "pendiente"


def test_denegar_sin_firma_no_deniega(db, client):
    from app.models import DocumentoCambio

    crear_usuario, manyana, tarde = _setup(db, "n3")
    claudia = crear_usuario("Claudia Pérez", "claudian3@h.es")
    juan = crear_usuario("Juan Rodríguez", "juann3@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martan3@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    _login(client, claudia.email)
    documento_id = _crear_documento_completo_via_client(client, claudia, juan, manyana)

    client.get("/auth/logout")
    _login(client, supervisora.email)
    client.post(f"/documentos-cambio/{documento_id}/denegar", data={"motivo": "motivo"})

    documento = db.session.get(DocumentoCambio, documento_id)
    assert documento.decision_supervisora == "pendiente"


def test_decision_supervisora_muestra_un_unico_recuadro_de_firma(db, client):
    """La supervisora firma una sola vez para autorizar o denegar: no debe
    haber dos lienzos de firma duplicados en la misma pantalla de decisión."""
    crear_usuario, manyana, tarde = _setup(db, "n5")
    claudia = crear_usuario("Claudia Pérez", "claudian5@h.es")
    juan = crear_usuario("Juan Rodríguez", "juann5@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martan5@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    _login(client, claudia.email)
    documento_id = _crear_documento_completo_via_client(client, claudia, juan, manyana)

    client.get("/auth/logout")
    _login(client, supervisora.email)
    resp = client.get(f"/documentos-cambio/{documento_id}")
    html = resp.data.decode("utf-8")

    assert html.count('class="firma-canvas"') == 1


def test_autorizar_guarda_la_firma_si_se_pide_y_no_habia_ninguna(db, client):
    crear_usuario, manyana, tarde = _setup(db, "n4")
    claudia = crear_usuario("Claudia Pérez", "claudian4@h.es")
    juan = crear_usuario("Juan Rodríguez", "juann4@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martan4@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    _login(client, claudia.email)
    documento_id = _crear_documento_completo_via_client(client, claudia, juan, manyana)

    client.get("/auth/logout")
    _login(client, supervisora.email)
    client.post(f"/documentos-cambio/{documento_id}/autorizar",
                data={"imagen_firma": _FIRMA_PNG, "guardar_firma": "on"})

    db.session.refresh(supervisora)
    assert supervisora.firma_guardada == _FIRMA_PNG
