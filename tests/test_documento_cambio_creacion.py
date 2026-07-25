from datetime import date, time, timedelta

from app.extensions import db
from app.models import Categoria, FranjaHoraria, GrupoIntercambio, Hospital, Unidad, Usuario
from tests.helpers_documento_cambio import _setup, _login, _FIRMA_PNG


def test_nuevo_requiere_login(client):
    resp = client.get("/documentos-cambio/nuevo")
    assert resp.status_code == 302


def test_turnos_disponibles_requiere_login(client):
    resp = client.get("/documentos-cambio/api/turnos-disponibles?usuario_id=1&fecha=2026-07-01")
    assert resp.status_code == 302


def test_turnos_disponibles_devuelve_las_franjas_del_dia(db, client):
    from app.services.planilla import añadir_turno

    crear_usuario, manyana, tarde = _setup(db, "td")
    claudia = crear_usuario("Claudia", "claudiatd@h.es")
    añadir_turno(claudia, date(2026, 7, 1), manyana.id)
    _login(client, claudia.email)

    resp = client.get(
        f"/documentos-cambio/api/turnos-disponibles?usuario_id={claudia.id}&fecha=2026-07-01"
    )
    assert resp.status_code == 200
    assert resp.json == [{"id": manyana.id, "nombre": "Mañana"}]


def test_turnos_disponibles_vacio_si_no_trabaja_ese_dia(db, client):
    crear_usuario, manyana, tarde = _setup(db, "td2")
    claudia = crear_usuario("Claudia", "claudiatd2@h.es")
    _login(client, claudia.email)

    resp = client.get(
        f"/documentos-cambio/api/turnos-disponibles?usuario_id={claudia.id}&fecha=2026-07-01"
    )
    assert resp.status_code == 200
    assert resp.json == []


def test_turnos_disponibles_de_usuario_de_otro_grupo_da_vacio(db, client):
    from app.services.planilla import añadir_turno

    crear_usuario, manyana, tarde = _setup(db, "td3")
    claudia = crear_usuario("Claudia", "claudiatd3@h.es")
    _login(client, claudia.email)

    crear_usuario_otro, manyana_otro, _ = _setup(db, "td3b")
    ajeno = crear_usuario_otro("Ajeno", "ajenotd3@h.es")
    añadir_turno(ajeno, date(2026, 7, 1), manyana_otro.id)

    resp = client.get(
        f"/documentos-cambio/api/turnos-disponibles?usuario_id={ajeno.id}&fecha=2026-07-01"
    )
    assert resp.status_code == 200
    assert resp.json == []


def test_turnos_disponibles_fecha_invalida_da_vacio(db, client):
    crear_usuario, manyana, tarde = _setup(db, "td4")
    claudia = crear_usuario("Claudia", "claudiatd4@h.es")
    _login(client, claudia.email)

    resp = client.get(
        f"/documentos-cambio/api/turnos-disponibles?usuario_id={claudia.id}&fecha=no-es-una-fecha"
    )
    assert resp.status_code == 200
    assert resp.json == []


def test_get_nuevo_lista_companeros_misma_categoria_y_grupo(db, client):
    crear_usuario, manyana, tarde = _setup(db, "a")
    claudia = crear_usuario("Claudia Pérez", "claudiaa@h.es")
    juan = crear_usuario("Juan Rodríguez", "juana@h.es")
    _login(client, claudia.email)

    resp = client.get("/documentos-cambio/nuevo")
    assert resp.status_code == 200

    html = resp.data.decode("utf-8")
    inicio = html.index('id="companero_id"')
    fin = html.index("</select>", inicio)
    select_html = html[inicio:fin]

    assert "Juan Rodríguez" in select_html
    assert "Claudia Pérez" not in select_html  # no se lista a sí misma


def test_post_nuevo_crea_documento_y_redirige_a_ver(db, client):
    crear_usuario, manyana, tarde = _setup(db, "b")
    claudia = crear_usuario("Claudia Pérez", "claudiab@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanb@h.es")
    _login(client, claudia.email)

    resp = client.post("/documentos-cambio/nuevo", data={
        "companero_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
    })

    assert resp.status_code == 302
    assert "/documentos-cambio/" in resp.headers["Location"]


def test_post_nuevo_sin_firmar_ambos_deja_el_documento_sin_firmas(db, client):
    """Comportamiento por defecto (sin marcar la casilla): igual que
    siempre, nadie ha firmado todavía al crear el documento."""
    from app.models import DocumentoCambio

    crear_usuario, manyana, tarde = _setup(db, "n2")
    claudia = crear_usuario("Claudia Pérez", "claudian2@h.es")
    juan = crear_usuario("Juan Rodríguez", "juann2@h.es")
    _login(client, claudia.email)

    resp = client.post("/documentos-cambio/nuevo", data={
        "companero_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
    })
    documento_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])
    documento = db.session.get(DocumentoCambio, documento_id)
    assert documento.estado == "borrador"
    assert len(documento.firmas) == 0


def test_post_nuevo_firmando_ambos_completa_el_documento(db, client):
    from app.models import DocumentoCambio

    crear_usuario, manyana, tarde = _setup(db, "o2")
    claudia = crear_usuario("Claudia Pérez", "claudiao2@h.es")
    juan = crear_usuario("Juan Rodríguez", "juano2@h.es")
    _login(client, claudia.email)

    resp = client.post("/documentos-cambio/nuevo", data={
        "companero_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
        "firmar_ambos": "on",
        "imagen_firma_propia": _FIRMA_PNG,
        "imagen_firma_companero": _FIRMA_PNG,
    })
    documento_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])
    documento = db.session.get(DocumentoCambio, documento_id)

    assert documento.estado == "completo"
    assert {f.usuario_id for f in documento.firmas} == {claudia.id, juan.id}


def test_post_nuevo_firmando_ambos_sin_alguna_firma_da_error(db, client):
    from app.models import DocumentoCambio

    crear_usuario, manyana, tarde = _setup(db, "p2")
    claudia = crear_usuario("Claudia Pérez", "claudiap2@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanp2@h.es")
    _login(client, claudia.email)

    resp = client.post("/documentos-cambio/nuevo", data={
        "companero_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
        "firmar_ambos": "on",
        "imagen_firma_propia": _FIRMA_PNG,
        "imagen_firma_companero": "",
    })
    assert resp.status_code == 200
    assert DocumentoCambio.query.count() == 0


def test_post_nuevo_firmando_ambos_guarda_firma_propia_si_se_pide(db, client):
    crear_usuario, manyana, tarde = _setup(db, "q2")
    claudia = crear_usuario("Claudia Pérez", "claudiaq2@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanq2@h.es")
    _login(client, claudia.email)

    client.post("/documentos-cambio/nuevo", data={
        "companero_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
        "firmar_ambos": "on",
        "imagen_firma_propia": _FIRMA_PNG,
        "imagen_firma_companero": _FIRMA_PNG,
        "guardar_firma": "on",
    })

    db.session.refresh(claudia)
    assert claudia.firma_guardada == _FIRMA_PNG
    # No se ha guardado por error la firma del compañero en su cuenta.
    db.session.refresh(juan)
    assert juan.firma_guardada is None
