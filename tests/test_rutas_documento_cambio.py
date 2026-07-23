from datetime import date, time, timedelta
from app.extensions import db
from app.models import Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria, Usuario


def _setup(db, sufijo="a"):
    hospital = Hospital(nombre=f"Hospital {sufijo}")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    categoria = Categoria(nombre=f"Enfermería {sufijo}")
    unidad = Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo)
    manyana = FranjaHoraria(nombre="Mañana", hora_inicio=time(7, 0), hora_fin=time(15, 0), grupo_intercambio=grupo)
    tarde = FranjaHoraria(nombre="Tarde", hora_inicio=time(15, 0), hora_fin=time(22, 0), grupo_intercambio=grupo)
    db.session.add_all([categoria, unidad, manyana, tarde])
    db.session.commit()

    def crear_usuario(nombre, email, password="password123"):
        u = Usuario(nombre=nombre, email=email, unidad=unidad, categoria=categoria)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        return u

    return crear_usuario, manyana, tarde


def _login(client, email, password="password123"):
    return client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=True)


def test_nuevo_requiere_login(client):
    resp = client.get("/documentos-cambio/nuevo")
    assert resp.status_code == 302


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


_FIRMA_PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAADklE"
    "QVR4nGNgGAWDEwAAAZoAAR2CVqgAAAAASUVORK5CYII="
)


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


# --- Registro manual de cambios en papel ---

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


# --- Supervisión de cambios: filtros ---

def _mes_actual_y_siguiente():
    hoy = date.today()
    fecha_este_mes = date(hoy.year, hoy.month, 1)
    anyo_sig, mes_sig = (hoy.year + 1, 1) if hoy.month == 12 else (hoy.year, hoy.month + 1)
    fecha_mes_siguiente = date(anyo_sig, mes_sig, 1)
    return fecha_este_mes, fecha_mes_siguiente


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


def _crear_documento_completo(db, creado_por, companero, franja_cede, franja_recibe, fecha_cede, fecha_recibe):
    """Crea y firma (con las dos partes) un documento directamente vía
    servicio, sin pasar por el cliente HTTP -- útil cuando se necesitan
    fechas/franjas concretas para probar filtros."""
    from app.services.documento_cambio import crear_documento_cambio, firmar_documento

    documento = crear_documento_cambio(
        creado_por, companero, fecha_cede, franja_cede.id, fecha_recibe, franja_recibe.id,
    )
    firmar_documento(documento, creado_por, _FIRMA_PNG)
    firmar_documento(documento, companero, _FIRMA_PNG)
    return documento


def _crear_documento_completo_via_client(client, claudia, juan, manyana):
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
    return documento_id


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


# --- Anular un cambio ya autorizado ---

def _fecha_futura(dias=10):
    return date.today() + timedelta(days=dias)


def _crear_y_autorizar(db, client, claudia, juan, supervisora, manyana):
    from app.services.documento_cambio import autorizar_documento

    doc = _crear_documento_completo(
        db, claudia, juan, manyana, manyana,
        _fecha_futura(10), _fecha_futura(20),
    )
    autorizar_documento(doc, supervisora)
    return doc


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


# --- Selección en bloque en la tabla de supervisión ---

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
