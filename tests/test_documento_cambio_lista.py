from datetime import date, time, timedelta

from app.extensions import db
from app.models import Categoria, FranjaHoraria, GrupoIntercambio, Hospital, Unidad, Usuario
from tests.helpers_documento_cambio import _setup, _login, _mes_actual_y_siguiente, _crear_documento_completo


def test_lista_muestra_documentos_donde_soy_participante(db, client):
    crear_usuario, manyana, tarde = _setup(db, "hh")
    claudia = crear_usuario("Claudia Pérez", "claudiahh@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanhh@h.es")
    otro = crear_usuario("Otro Usuario", "otrohh@h.es")
    _login(client, claudia.email)

    client.post("/documentos-cambio/nuevo", data={
        "companero_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
    })

    resp = client.get("/documentos-cambio/")
    assert resp.status_code == 200
    assert b"Juan Rodr\xc3\xadguez" in resp.data
    assert b"Otro Usuario" not in resp.data

    client.get("/auth/logout")
    _login(client, juan.email)
    resp = client.get("/documentos-cambio/")
    assert b"Claudia P\xc3\xa9rez" in resp.data

    client.get("/auth/logout")
    _login(client, otro.email)
    resp = client.get("/documentos-cambio/")
    assert b"Claudia P\xc3\xa9rez" not in resp.data
    assert b"Juan Rodr\xc3\xadguez" not in resp.data


def test_lista_muestra_badge_de_papel_en_cambio_registrado_desde_papel(db, client):
    from app.services.documento_cambio import registrar_documento_cambio_papel

    crear_usuario, manyana, tarde = _setup(db, "papellista")
    claudia = crear_usuario("Claudia Pérez", "claudiapapellista@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanpapellista@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martapapellista@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    fecha_este_mes, _ = _mes_actual_y_siguiente()
    registrar_documento_cambio_papel(
        supervisora=supervisora, usuario1=claudia, usuario2=juan,
        turno1_cede_fecha=fecha_este_mes, turno1_cede_franja_id=manyana.id,
        turno1_recibe_fecha=fecha_este_mes + timedelta(days=1), turno1_recibe_franja_id=manyana.id,
    )

    _login(client, claudia.email)
    resp = client.get("/documentos-cambio/")

    assert resp.status_code == 200
    assert "Papel".encode("utf-8") in resp.data


def test_supervisora_ve_los_cambios_completos_de_su_grupo(db, client):
    crear_usuario, manyana, tarde = _setup(db, "ii")
    claudia = crear_usuario("Claudia Pérez", "claudiaii@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanii@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martaii@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    fecha_este_mes, _ = _mes_actual_y_siguiente()
    doc = _crear_documento_completo(db, claudia, juan, manyana, tarde,
                                     fecha_este_mes, fecha_este_mes + timedelta(days=1))

    _login(client, supervisora.email)
    resp = client.get("/documentos-cambio/supervisora")
    assert resp.status_code == 200
    assert f"<td>cambio #{doc.numero_unidad} del {doc.fecha_creacion.strftime('%d/%m/%Y')}</td>".encode() in resp.data
    assert b"Claudia P\xc3\xa9rez" in resp.data
    assert b"Juan Rodr\xc3\xadguez" in resp.data
    assert "<table".encode() in resp.data


def test_supervisora_sigue_viendo_el_nombre_real_tras_eliminar_la_cuenta(db, client):
    """Una hoja de cambio completa hace de equivalente firmado en papel: si
    uno de los participantes elimina luego su cuenta, el nombre congelado
    en el momento de completarse debe seguir viéndose, en vez de caer al
    'Usuario eliminado' de la cuenta anonimizada."""
    from app.services.registro import eliminar_cuenta

    crear_usuario, manyana, tarde = _setup(db, "ii3")
    claudia = crear_usuario("Claudia Pérez", "claudiaii3@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanii3@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martaii3@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    fecha_este_mes, _ = _mes_actual_y_siguiente()
    doc = _crear_documento_completo(db, claudia, juan, manyana, tarde,
                                     fecha_este_mes, fecha_este_mes + timedelta(days=1))

    eliminar_cuenta(claudia)

    _login(client, supervisora.email)
    resp = client.get("/documentos-cambio/supervisora")
    assert resp.status_code == 200
    assert "<td>Claudia Pérez</td>".encode("utf-8") in resp.data


def test_supervisora_ve_el_motivo_de_denegacion_en_la_tabla(db, client):
    from app.services.documento_cambio import denegar_documento

    crear_usuario, manyana, tarde = _setup(db, "ii2")
    claudia = crear_usuario("Claudia Pérez", "claudiaii2@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanii2@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martaii2@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    fecha_este_mes, _ = _mes_actual_y_siguiente()
    doc = _crear_documento_completo(db, claudia, juan, manyana, tarde,
                                     fecha_este_mes, fecha_este_mes + timedelta(days=1))
    denegar_documento(doc, supervisora, motivo="Pedro ya tenía otro cambio ese día.")

    _login(client, supervisora.email)
    resp = client.get("/documentos-cambio/supervisora")
    assert resp.status_code == 200
    assert "Pedro ya tenía otro cambio ese día.".encode("utf-8") in resp.data


def test_no_supervisora_no_puede_ver_la_pagina_de_supervisora(db, client):
    crear_usuario, manyana, tarde = _setup(db, "jj")
    claudia = crear_usuario("Claudia Pérez", "claudiajj@h.es")
    _login(client, claudia.email)

    resp = client.get("/documentos-cambio/supervisora")
    assert resp.status_code == 403
