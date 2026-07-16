from datetime import time
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


def test_flujo_completo_firmar_ambos_muestra_notas_ilog(db, client):
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

    resp = client.post(
        f"/documentos-cambio/{documento_id}/firmar/{p2.id}",
        data={"imagen_firma": "data:image/png;base64,BBB"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert db.session.get(DocumentoCambio, documento_id).estado == "completo"
    assert "Libra el turno de mañana".encode("utf-8") in resp.data


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
    client.post(f"/documentos-cambio/{documento_id}/firmar/{p2.id}", data={"imagen_firma": _FIRMA_PNG})

    resp = client.get(f"/documentos-cambio/{documento_id}/pdf")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data[:5] == b"%PDF-"
