from datetime import date, time, timedelta

from app.extensions import db
from app.models import Categoria, FranjaHoraria, GrupoIntercambio, Hospital, Unidad, Usuario
from tests.helpers_documento_cambio import _setup, _login, _FIRMA_PNG, _crear_documento_completo_via_client


def test_ver_documento_ajeno_da_403(db, client):
    crear_usuario, manyana, tarde = _setup(db, "c")
    claudia = crear_usuario("Claudia Pérez", "claudiac@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanc@h.es")
    otro = crear_usuario("Otro Usuario", "otroc@h.es")
    _login(client, claudia.email)
    resp = client.post("/documentos-cambio/nuevo", data={
        "companero_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
    })
    documento_id = resp.headers["Location"].rstrip("/").split("/")[-1]
    client.get("/auth/logout")

    _login(client, otro.email)
    resp = client.get(f"/documentos-cambio/{documento_id}")
    assert resp.status_code == 403


def test_flujo_completo_firmar_ambos_no_muestra_notas_ilog_a_los_participantes(db, client):
    crear_usuario, manyana, tarde = _setup(db, "d")
    claudia = crear_usuario("Claudia Pérez", "claudiad@h.es")
    juan = crear_usuario("Juan Rodríguez", "juand@h.es")
    _login(client, claudia.email)

    resp = client.post("/documentos-cambio/nuevo", data={
        "companero_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
    })
    documento_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])

    resp = client.get(f"/documentos-cambio/{documento_id}")
    assert resp.status_code == 200
    assert b"Sin firmar" in resp.data

    from app.models import DocumentoCambio
    documento = db.session.get(DocumentoCambio, documento_id)
    p1, p2 = documento.participantes[0], documento.participantes[1]

    resp = client.post(
        f"/documentos-cambio/{documento_id}/firmar/{p1.id}",
        data={"imagen_firma": "data:image/png;base64,AAA"},
    )
    assert resp.status_code == 302
    assert db.session.get(DocumentoCambio, documento_id).estado == "pendiente_firmas"

    # Firma cruzada entre cuentas reales: Juan firma desde su propia cuenta.
    client.get("/auth/logout")
    _login(client, juan.email)
    resp = client.post(
        f"/documentos-cambio/{documento_id}/firmar/{p2.id}",
        data={"imagen_firma": "data:image/png;base64,BBB"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert db.session.get(DocumentoCambio, documento_id).estado == "completo"
    assert "Libra el turno de mañana".encode("utf-8") not in resp.data
    assert b"Notas para ilog" not in resp.data


def test_supervisora_ve_las_notas_ilog_de_un_documento_completo(db, client):
    crear_usuario, manyana, tarde = _setup(db, "mm")
    claudia = crear_usuario("Claudia Pérez", "claudiamm@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanmm@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martamm@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    _login(client, claudia.email)
    documento_id = _crear_documento_completo_via_client(client, claudia, juan, manyana)

    client.get("/auth/logout")
    _login(client, supervisora.email)
    resp = client.get(f"/documentos-cambio/{documento_id}")
    assert resp.status_code == 200
    assert b"Notas para ilog" in resp.data
    assert "Libra el turno de mañana".encode("utf-8") in resp.data


def test_no_se_puede_firmar_en_nombre_de_otro(db, client):
    crear_usuario, manyana, tarde = _setup(db, "dd")
    claudia = crear_usuario("Claudia Pérez", "claudiadd@h.es")
    juan = crear_usuario("Juan Rodríguez", "juandd@h.es")
    _login(client, claudia.email)

    resp = client.post("/documentos-cambio/nuevo", data={
        "companero_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
    })
    documento_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])
    from app.models import DocumentoCambio
    p1, p2 = db.session.get(DocumentoCambio, documento_id).participantes

    # Claudia (logueada) intenta firmar la fila de Juan (p2): prohibido.
    resp = client.post(
        f"/documentos-cambio/{documento_id}/firmar/{p2.id}",
        data={"imagen_firma": "data:image/png;base64,AAA"},
    )
    assert resp.status_code == 403


def test_firmar_dos_veces_el_mismo_participante_da_409(db, client):
    crear_usuario, manyana, tarde = _setup(db, "e")
    claudia = crear_usuario("Claudia Pérez", "claudiae@h.es")
    juan = crear_usuario("Juan Rodríguez", "juane@h.es")
    _login(client, claudia.email)

    resp = client.post("/documentos-cambio/nuevo", data={
        "companero_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
    })
    documento_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])
    from app.models import DocumentoCambio
    p1 = db.session.get(DocumentoCambio, documento_id).participantes[0]

    client.post(f"/documentos-cambio/{documento_id}/firmar/{p1.id}",
                data={"imagen_firma": "data:image/png;base64,AAA"})
    resp = client.post(f"/documentos-cambio/{documento_id}/firmar/{p1.id}",
                        data={"imagen_firma": "data:image/png;base64,CCC"})
    assert resp.status_code == 409


def test_pdf_da_409_si_no_esta_completo(db, client):
    crear_usuario, manyana, tarde = _setup(db, "f")
    claudia = crear_usuario("Claudia Pérez", "claudiaf@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanf@h.es")
    _login(client, claudia.email)

    resp = client.post("/documentos-cambio/nuevo", data={
        "companero_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
    })
    documento_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])

    resp = client.get(f"/documentos-cambio/{documento_id}/pdf")
    assert resp.status_code == 409


def test_pdf_descarga_cuando_esta_completo(db, client):
    crear_usuario, manyana, tarde = _setup(db, "g")
    claudia = crear_usuario("Claudia Pérez", "claudiag@h.es")
    juan = crear_usuario("Juan Rodríguez", "juang@h.es")
    _login(client, claudia.email)

    resp = client.post("/documentos-cambio/nuevo", data={
        "companero_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
    })
    documento_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])
    from app.models import DocumentoCambio
    p1, p2 = db.session.get(DocumentoCambio, documento_id).participantes

    client.post(f"/documentos-cambio/{documento_id}/firmar/{p1.id}", data={"imagen_firma": _FIRMA_PNG})
    client.get("/auth/logout")
    _login(client, juan.email)
    client.post(f"/documentos-cambio/{documento_id}/firmar/{p2.id}", data={"imagen_firma": _FIRMA_PNG})

    resp = client.get(f"/documentos-cambio/{documento_id}/pdf")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data[:5] == b"%PDF-"


def test_companero_puede_ver_el_documento_y_firmar_su_parte(db, client):
    crear_usuario, manyana, tarde = _setup(db, "ee")
    claudia = crear_usuario("Claudia Pérez", "claudiaee@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanee@h.es")
    _login(client, claudia.email)

    resp = client.post("/documentos-cambio/nuevo", data={
        "companero_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
    })
    documento_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])
    client.get("/auth/logout")

    _login(client, juan.email)
    resp = client.get(f"/documentos-cambio/{documento_id}")
    assert resp.status_code == 200  # antes daba 403: solo el creador podía verlo


def test_ver_muestra_boton_de_firma_guardada_si_el_usuario_tiene_una(db, client):
    crear_usuario, manyana, tarde = _setup(db, "hh")
    claudia = crear_usuario("Claudia Pérez", "claudiahh@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanhh@h.es")
    claudia.firma_guardada = "data:image/png;base64,AAA"
    db.session.commit()
    _login(client, claudia.email)

    resp = client.post("/documentos-cambio/nuevo", data={
        "companero_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
    })
    documento_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])

    resp = client.get(f"/documentos-cambio/{documento_id}")
    assert b"firma-usar-guardada" in resp.data
    assert b'data-firma="data:image/png;base64,AAA"' in resp.data


def test_ver_no_muestra_boton_de_firma_guardada_si_el_usuario_no_tiene(db, client):
    crear_usuario, manyana, tarde = _setup(db, "ii")
    claudia = crear_usuario("Claudia Pérez", "claudiaii@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanii@h.es")
    _login(client, claudia.email)

    resp = client.post("/documentos-cambio/nuevo", data={
        "companero_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
    })
    documento_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])

    resp = client.get(f"/documentos-cambio/{documento_id}")
    assert b"firma-usar-guardada" not in resp.data


def test_ver_ofrece_guardar_firma_si_el_usuario_no_tiene_una(db, client):
    crear_usuario, manyana, tarde = _setup(db, "jj")
    claudia = crear_usuario("Claudia Pérez", "claudiajj@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanjj@h.es")
    _login(client, claudia.email)

    resp = client.post("/documentos-cambio/nuevo", data={
        "companero_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
    })
    documento_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])

    resp = client.get(f"/documentos-cambio/{documento_id}")
    assert b'name="guardar_firma"' in resp.data


def test_ver_no_ofrece_guardar_firma_si_el_usuario_ya_tiene_una(db, client):
    crear_usuario, manyana, tarde = _setup(db, "kk")
    claudia = crear_usuario("Claudia Pérez", "claudiakk@h.es")
    juan = crear_usuario("Juan Rodríguez", "juankk@h.es")
    claudia.firma_guardada = "data:image/png;base64,AAA"
    db.session.commit()
    _login(client, claudia.email)

    resp = client.post("/documentos-cambio/nuevo", data={
        "companero_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
    })
    documento_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])

    resp = client.get(f"/documentos-cambio/{documento_id}")
    assert b'name="guardar_firma"' not in resp.data


def test_firmar_con_guardar_firma_marcado_guarda_la_firma_para_el_futuro(db, client):
    crear_usuario, manyana, tarde = _setup(db, "ll")
    claudia = crear_usuario("Claudia Pérez", "claudiall@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanll@h.es")
    _login(client, claudia.email)

    resp = client.post("/documentos-cambio/nuevo", data={
        "companero_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
    })
    documento_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])
    from app.models import DocumentoCambio
    p1 = db.session.get(DocumentoCambio, documento_id).participantes[0]

    client.post(
        f"/documentos-cambio/{documento_id}/firmar/{p1.id}",
        data={"imagen_firma": "data:image/png;base64,AAA", "guardar_firma": "1"},
    )

    from app.extensions import db as _db
    _db.session.refresh(claudia)
    assert claudia.firma_guardada == "data:image/png;base64,AAA"


def test_firmar_sin_marcar_guardar_firma_no_guarda_nada(db, client):
    crear_usuario, manyana, tarde = _setup(db, "mm2")
    claudia = crear_usuario("Claudia Pérez", "claudiamm2@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanmm2@h.es")
    _login(client, claudia.email)

    resp = client.post("/documentos-cambio/nuevo", data={
        "companero_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
    })
    documento_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])
    from app.models import DocumentoCambio
    p1 = db.session.get(DocumentoCambio, documento_id).participantes[0]

    client.post(
        f"/documentos-cambio/{documento_id}/firmar/{p1.id}",
        data={"imagen_firma": "data:image/png;base64,AAA"},
    )

    from app.extensions import db as _db
    _db.session.refresh(claudia)
    assert claudia.firma_guardada is None


def test_firmar_con_guardar_firma_marcado_no_sobrescribe_firma_ya_guardada(db, client):
    crear_usuario, manyana, tarde = _setup(db, "nn")
    claudia = crear_usuario("Claudia Pérez", "claudiann@h.es")
    juan = crear_usuario("Juan Rodríguez", "juannn@h.es")
    claudia.firma_guardada = "data:image/png;base64,ORIGINAL"
    db.session.commit()
    _login(client, claudia.email)

    resp = client.post("/documentos-cambio/nuevo", data={
        "companero_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
    })
    documento_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])
    from app.models import DocumentoCambio
    p1 = db.session.get(DocumentoCambio, documento_id).participantes[0]

    client.post(
        f"/documentos-cambio/{documento_id}/firmar/{p1.id}",
        data={"imagen_firma": "data:image/png;base64,NUEVA", "guardar_firma": "1"},
    )

    from app.extensions import db as _db
    _db.session.refresh(claudia)
    assert claudia.firma_guardada == "data:image/png;base64,ORIGINAL"


def test_companero_ve_aviso_de_documento_pendiente(db, client):
    crear_usuario, manyana, tarde = _setup(db, "ff")
    claudia = crear_usuario("Claudia Pérez", "claudiaff@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanff@h.es")
    _login(client, claudia.email)

    client.post("/documentos-cambio/nuevo", data={
        "companero_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
    })
    client.get("/auth/logout")

    _login(client, juan.email)
    resp = client.get("/avisos")
    assert resp.status_code == 200
    assert b"Hoja de cambio" in resp.data


def test_ver_muestra_numero_de_documento(db, client):
    crear_usuario, manyana, tarde = _setup(db, "gg")
    claudia = crear_usuario("Claudia Pérez", "claudiagg@h.es")
    juan = crear_usuario("Juan Rodríguez", "juangg@h.es")
    _login(client, claudia.email)

    resp = client.post("/documentos-cambio/nuevo", data={
        "companero_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
    })
    documento_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])

    resp = client.get(f"/documentos-cambio/{documento_id}")
    assert b"cambio #1 del" in resp.data


def test_ver_no_ofrece_firmar_ni_muestra_sin_firmar_en_un_cambio_de_papel(db, client):
    """Un cambio registrado desde papel ya se firmó a mano y ya quedó
    autorizado -- no debe ofrecer firmar digitalmente ni mostrar "Sin
    firmar" a los implicados."""
    from app.services.documento_cambio import registrar_documento_cambio_papel

    crear_usuario, manyana, tarde = _setup(db, "papel")
    claudia = crear_usuario("Claudia Pérez", "claudiapapel@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanpapel@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martapapel@h.es")
    supervisora.es_supervisora = True
    db.session.commit()

    documento = registrar_documento_cambio_papel(
        supervisora=supervisora, usuario1=claudia, usuario2=juan,
        turno1_cede_fecha=date(2026, 7, 7), turno1_cede_franja_id=manyana.id,
        turno1_recibe_fecha=date(2026, 7, 28), turno1_recibe_franja_id=manyana.id,
    )

    _login(client, claudia.email)
    resp = client.get(f"/documentos-cambio/{documento.id}")

    assert resp.status_code == 200
    assert "Registrado desde hoja de papel".encode("utf-8") in resp.data
    assert "Sin firmar".encode("utf-8") not in resp.data
    assert ">Tu firma<".encode("utf-8") not in resp.data


def test_numero_de_documento_es_por_unidad_no_el_id_global(db, client):
    """
    Si otra unidad ya ha creado hojas de cambio antes (id global más alto),
    la primera hoja de una unidad nueva tiene que seguir mostrando "cambio #1 del",
    no arrastrar el id autoincremental compartido por toda la app.
    """
    crear_usuario_otra, manyana_otra, _ = _setup(db, "hh-otra")
    alguien = crear_usuario_otra("Alguien de Otra Unidad", "alguienhh@h.es")
    companero_otro = crear_usuario_otra("Compañero de Otra Unidad", "companerohh@h.es")
    _login(client, alguien.email)
    client.post("/documentos-cambio/nuevo", data={
        "companero_id": companero_otro.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana_otra.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana_otra.id,
    })
    client.get("/auth/logout")

    crear_usuario, manyana, tarde = _setup(db, "hh")
    claudia = crear_usuario("Claudia Pérez", "claudiahh@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanhh@h.es")
    _login(client, claudia.email)

    resp = client.post("/documentos-cambio/nuevo", data={
        "companero_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
    })
    documento_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])
    assert documento_id > 1  # el id global ya iba por delante por la otra unidad

    resp = client.get(f"/documentos-cambio/{documento_id}")
    assert b"cambio #1 del" in resp.data
