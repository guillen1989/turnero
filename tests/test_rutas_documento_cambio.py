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
    assert b"N\xc2\xba 1" in resp.data


def test_numero_de_documento_es_por_unidad_no_el_id_global(db, client):
    """
    Si otra unidad ya ha creado hojas de cambio antes (id global más alto),
    la primera hoja de una unidad nueva tiene que seguir mostrando "Nº 1",
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
    assert b"N\xc2\xba 1" in resp.data


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
    assert f"<td>{doc.numero_unidad}</td>".encode() in resp.data
    assert b"Claudia P\xc3\xa9rez" in resp.data
    assert b"Juan Rodr\xc3\xadguez" in resp.data
    assert "<table".encode() in resp.data


def test_no_supervisora_no_puede_ver_la_pagina_de_supervisora(db, client):
    crear_usuario, manyana, tarde = _setup(db, "jj")
    claudia = crear_usuario("Claudia Pérez", "claudiajj@h.es")
    _login(client, claudia.email)

    resp = client.get("/documentos-cambio/supervisora")
    assert resp.status_code == 403


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
    assert f"<td>{doc.numero_unidad}</td>".encode() not in resp.data
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
    assert f"<td>{doc_este_mes.numero_unidad}</td>".encode() in resp.data
    assert f"<td>{doc_mes_siguiente.numero_unidad}</td>".encode() not in resp.data


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
    assert f"<td>{doc.numero_unidad}</td>".encode() in resp.data


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
    assert f"<td>{doc.numero_unidad}</td>".encode() in resp.data


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
    assert f"<td>{doc_claudia.numero_unidad}</td>".encode() in resp.data
    assert f"<td>{doc_ana.numero_unidad}</td>".encode() not in resp.data


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
    assert f"<td>{doc_claudia_juan.numero_unidad}</td>".encode() in resp.data
    assert f"<td>{doc_claudia_ana.numero_unidad}</td>".encode() not in resp.data


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
    assert f"<td>{doc_manyana.numero_unidad}</td>".encode() in resp.data
    assert f"<td>{doc_tarde.numero_unidad}</td>".encode() not in resp.data


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
    assert f"<td>{doc_a.numero_unidad}</td>".encode() in resp.data
    assert f"<td>{doc_b.numero_unidad}</td>".encode() not in resp.data


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
    assert f"<td>{doc.numero_unidad}</td>".encode() in resp.data
    resp_factible = client.get("/documentos-cambio/supervisora", query_string={"factibilidad": "factible"})
    assert f"<td>{doc.numero_unidad}</td>".encode() not in resp_factible.data


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
    assert f"<td>{doc_a.numero_unidad}</td>".encode() in resp.data
    assert f"<td>{doc_b.numero_unidad}</td>".encode() not in resp.data


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
    resp = client.post(f"/documentos-cambio/{documento_id}/autorizar")
    assert resp.status_code == 302

    documento = db.session.get(DocumentoCambio, documento_id)
    assert documento.decision_supervisora == "autorizado"
    assert documento.supervisora_id == supervisora.id
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
        data={"motivo": "No coincide con la planilla real de ese mes."},
    )
    assert resp.status_code == 302

    documento = db.session.get(DocumentoCambio, documento_id)
    assert documento.decision_supervisora == "denegado"
    assert documento.motivo_denegacion == "No coincide con la planilla real de ese mes."
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
        data={"motivo": "Pedro ya tenía otro cambio ese día."},
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
    client.post(f"/documentos-cambio/{documento_id}/autorizar")
    resp = client.post(f"/documentos-cambio/{documento_id}/autorizar")
    assert resp.status_code == 409
