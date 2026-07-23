from datetime import date, time

from app.models import (
    Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria, Usuario,
    DocumentoCambio, ParticipanteDocumentoCambio, AjustePlanillaSupervisora,
)
from app.services.planilla import añadir_turno, establecer_estado_dia


def _setup(db, sufijo="a"):
    hospital = Hospital(nombre=f"H-{sufijo}")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    unidad = Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo)
    otra_unidad = Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo)
    categoria = Categoria(nombre=f"Cat-{sufijo}")
    franja_m = FranjaHoraria(
        nombre="Mañana", hora_inicio=time(8, 0), hora_fin=time(15, 0), grupo_intercambio=grupo
    )
    db.session.add_all([unidad, otra_unidad, categoria, franja_m])
    db.session.commit()

    def crear_usuario(nombre, email, password="password123", supervisora=False, u=unidad):
        usuario = Usuario(
            nombre=nombre, email=email, unidad=u, categoria=categoria, es_supervisora=supervisora
        )
        usuario.set_password(password)
        db.session.add(usuario)
        db.session.commit()
        return usuario

    return crear_usuario, unidad, otra_unidad, franja_m


def _login(client, email, password="password123"):
    return client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=True)


def test_index_requiere_login(client):
    resp = client.get("/planilla/supervision/")
    assert resp.status_code == 302


def test_index_prohibido_si_no_es_supervisora(db, client):
    crear_usuario, unidad, _, _ = _setup(db, "a")
    normal = crear_usuario("Normal", "normal_a@h.es")
    _login(client, normal.email)

    resp = client.get("/planilla/supervision/")
    assert resp.status_code == 403


def test_index_muestra_trabajadores_de_la_unidad_y_no_de_otras(db, client):
    crear_usuario, unidad, otra_unidad, franja_m = _setup(db, "b")
    supervisora = crear_usuario("Super", "super_b@h.es", supervisora=True)
    ana = crear_usuario("Ana", "ana_b@h.es")
    crear_usuario("Cris", "cris_b@h.es", u=otra_unidad)
    _login(client, supervisora.email)

    resp = client.get("/planilla/supervision/?anyo=2026&mes=7")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Ana" in html
    assert "Cris" not in html


def test_index_no_muestra_usuarios_eliminados(db, client):
    crear_usuario, unidad, _, _ = _setup(db, "z")
    supervisora = crear_usuario("Super", "super_z@h.es", supervisora=True)
    ana = crear_usuario("Ana", "ana_z@h.es")
    ana.password_hash = "CUENTA_ELIMINADA"
    db.session.commit()
    _login(client, supervisora.email)

    resp = client.get("/planilla/supervision/?anyo=2026&mes=7")
    assert resp.status_code == 200
    assert "Ana" not in resp.data.decode("utf-8")


def test_index_muestra_turno_del_dia(db, client):
    crear_usuario, unidad, _, franja_m = _setup(db, "c")
    supervisora = crear_usuario("Super", "super_c@h.es", supervisora=True)
    ana = crear_usuario("Ana", "ana_c@h.es")
    añadir_turno(ana, date(2026, 7, 1), franja_m.id)
    _login(client, supervisora.email)

    resp = client.get("/planilla/supervision/?anyo=2026&mes=7")
    assert resp.status_code == 200
    assert franja_m.nombre[:1] in resp.data.decode("utf-8")


def test_index_muestra_estado_dia(db, client):
    crear_usuario, unidad, _, _ = _setup(db, "d")
    supervisora = crear_usuario("Super", "super_d@h.es", supervisora=True)
    ana = crear_usuario("Ana", "ana_d@h.es")
    establecer_estado_dia(ana, date(2026, 7, 1), "libre")
    _login(client, supervisora.email)

    resp = client.get("/planilla/supervision/?anyo=2026&mes=7")
    assert resp.status_code == 200
    assert "L" in resp.data.decode("utf-8")


def test_index_enlaza_a_documento_de_cambio_autorizado(db, client):
    crear_usuario, unidad, _, franja_m = _setup(db, "e")
    franja_t = FranjaHoraria(
        nombre="Tarde", hora_inicio=time(15, 0), hora_fin=time(22, 0),
        grupo_intercambio=unidad.grupo_intercambio,
    )
    db.session.add(franja_t)
    db.session.commit()

    supervisora = crear_usuario("Super", "super_e@h.es", supervisora=True)
    ana = crear_usuario("Ana", "ana_e@h.es")
    pedro = crear_usuario("Pedro", "pedro_e@h.es")

    documento = DocumentoCambio(
        creado_por=ana, unidad=unidad, numero_unidad=1,
        decision_supervisora="autorizado", anulado=False,
    )
    db.session.add(documento)
    db.session.flush()
    documento.participantes.append(ParticipanteDocumentoCambio(
        usuario=ana,
        turno_cede_fecha=date(2026, 7, 10), turno_cede_franja=franja_m,
        turno_recibe_fecha=date(2026, 7, 11), turno_recibe_franja=franja_t,
    ))
    db.session.commit()

    _login(client, supervisora.email)
    resp = client.get("/planilla/supervision/?anyo=2026&mes=7")
    assert resp.status_code == 200
    assert f"/documentos-cambio/{documento.id}" in resp.data.decode("utf-8")


# ── ajustar ────────────────────────────────────────────────────────────────────

def test_ajustar_requiere_login(client):
    resp = client.post("/planilla/supervision/ajustar", data={})
    assert resp.status_code == 302


def test_ajustar_prohibido_si_no_es_supervisora(db, client):
    crear_usuario, unidad, _, franja_m = _setup(db, "f")
    normal = crear_usuario("Normal", "normal_f@h.es")
    ana = crear_usuario("Ana", "ana_f@h.es")
    _login(client, normal.email)

    resp = client.post("/planilla/supervision/ajustar", data={
        "usuario_id": ana.id, "fecha": "2026-07-01", "anyo": 2026, "mes": 7,
        "seleccion": "libre",
    })
    assert resp.status_code == 403


def test_ajustar_prohibido_si_trabajador_de_otra_unidad(db, client):
    crear_usuario, unidad, otra_unidad, franja_m = _setup(db, "g")
    supervisora = crear_usuario("Super", "super_g@h.es", supervisora=True)
    cris = crear_usuario("Cris", "cris_g@h.es", u=otra_unidad)
    _login(client, supervisora.email)

    resp = client.post("/planilla/supervision/ajustar", data={
        "usuario_id": cris.id, "fecha": "2026-07-01", "anyo": 2026, "mes": 7,
        "seleccion": "libre",
    })
    assert resp.status_code == 403
    assert AjustePlanillaSupervisora.query.count() == 0


def test_ajustar_asigna_estado(db, client):
    crear_usuario, unidad, _, franja_m = _setup(db, "h")
    supervisora = crear_usuario("Super", "super_h@h.es", supervisora=True)
    ana = crear_usuario("Ana", "ana_h@h.es")
    _login(client, supervisora.email)

    resp = client.post("/planilla/supervision/ajustar", data={
        "usuario_id": ana.id, "fecha": "2026-07-01", "anyo": 2026, "mes": 7,
        "seleccion": "libre", "motivo": "Día libre concedido",
    }, follow_redirects=True)
    assert resp.status_code == 200

    ajuste = AjustePlanillaSupervisora.query.filter_by(usuario_id=ana.id).first()
    assert ajuste is not None
    assert ajuste.descripcion_nueva == "libre"
    assert ajuste.realizado_por_id == supervisora.id
    assert ajuste.motivo == "Día libre concedido"


def test_ajustar_asigna_turno(db, client):
    crear_usuario, unidad, _, franja_m = _setup(db, "i")
    supervisora = crear_usuario("Super", "super_i@h.es", supervisora=True)
    ana = crear_usuario("Ana", "ana_i@h.es")
    _login(client, supervisora.email)

    resp = client.post("/planilla/supervision/ajustar", data={
        "usuario_id": ana.id, "fecha": "2026-07-01", "anyo": 2026, "mes": 7,
        "seleccion": str(franja_m.id),
    }, follow_redirects=True)
    assert resp.status_code == 200

    ajuste = AjustePlanillaSupervisora.query.filter_by(usuario_id=ana.id).first()
    assert ajuste.descripcion_nueva == "Mañana"


def test_ajustar_anadir_turno_extra_no_sustituye_el_existente(db, client):
    crear_usuario, unidad, _, franja_m = _setup(db, "n")
    franja_t = FranjaHoraria(
        nombre="Tarde", hora_inicio=time(15, 0), hora_fin=time(22, 0),
        grupo_intercambio=unidad.grupo_intercambio,
    )
    db.session.add(franja_t)
    db.session.commit()

    supervisora = crear_usuario("Super", "super_n@h.es", supervisora=True)
    ana = crear_usuario("Ana", "ana_n@h.es")
    añadir_turno(ana, date(2026, 7, 1), franja_m.id)
    _login(client, supervisora.email)

    resp = client.post("/planilla/supervision/ajustar", data={
        "usuario_id": ana.id, "fecha": "2026-07-01", "anyo": 2026, "mes": 7,
        "seleccion": str(franja_t.id), "anadir_extra": "1",
    }, follow_redirects=True)
    assert resp.status_code == 200

    html = resp.data.decode("utf-8")
    tbody = html[html.index("<tbody>"):]
    assert tbody.count(f">{franja_m.nombre}<") == 1
    assert tbody.count(f">{franja_t.nombre}<") == 1


def test_ajustar_vacia_dia(db, client):
    crear_usuario, unidad, _, franja_m = _setup(db, "j")
    supervisora = crear_usuario("Super", "super_j@h.es", supervisora=True)
    ana = crear_usuario("Ana", "ana_j@h.es")
    añadir_turno(ana, date(2026, 7, 1), franja_m.id)
    _login(client, supervisora.email)

    resp = client.post("/planilla/supervision/ajustar", data={
        "usuario_id": ana.id, "fecha": "2026-07-01", "anyo": 2026, "mes": 7,
        "seleccion": "vaciar",
    }, follow_redirects=True)
    assert resp.status_code == 200

    ajuste = AjustePlanillaSupervisora.query.filter_by(usuario_id=ana.id).first()
    assert ajuste.descripcion_nueva == "(vacío)"


def test_ajustar_seleccion_invalida_no_crea_ajuste(db, client):
    crear_usuario, unidad, _, franja_m = _setup(db, "k")
    supervisora = crear_usuario("Super", "super_k@h.es", supervisora=True)
    ana = crear_usuario("Ana", "ana_k@h.es")
    _login(client, supervisora.email)

    resp = client.post("/planilla/supervision/ajustar", data={
        "usuario_id": ana.id, "fecha": "2026-07-01", "anyo": 2026, "mes": 7,
        "seleccion": "cosa-rara",
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert AjustePlanillaSupervisora.query.count() == 0


def test_ajustar_franja_de_otro_grupo_rechazada(db, client):
    crear_usuario, unidad, _, _ = _setup(db, "l")
    _, otra_unidad2, _, franja_otro_grupo = _setup(db, "m")
    supervisora = crear_usuario("Super", "super_l@h.es", supervisora=True)
    ana = crear_usuario("Ana", "ana_l@h.es")
    _login(client, supervisora.email)

    resp = client.post("/planilla/supervision/ajustar", data={
        "usuario_id": ana.id, "fecha": "2026-07-01", "anyo": 2026, "mes": 7,
        "seleccion": str(franja_otro_grupo.id),
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert AjustePlanillaSupervisora.query.count() == 0


def test_index_muestra_doblaje_con_dos_turnos_el_mismo_dia(db, client):
    crear_usuario, unidad, _, franja_m = _setup(db, "f")
    franja_t = FranjaHoraria(
        nombre="Tarde", hora_inicio=time(15, 0), hora_fin=time(22, 0),
        grupo_intercambio=unidad.grupo_intercambio,
    )
    db.session.add(franja_t)
    db.session.commit()

    supervisora = crear_usuario("Super", "super_f@h.es", supervisora=True)
    ana = crear_usuario("Ana", "ana_f@h.es")
    añadir_turno(ana, date(2026, 7, 1), franja_m.id)
    añadir_turno(ana, date(2026, 7, 1), franja_t.id)
    _login(client, supervisora.email)

    resp = client.get("/planilla/supervision/?anyo=2026&mes=7")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    tbody = html[html.index("<tbody>"):]
    assert tbody.count(f">{franja_m.nombre}<") == 1
    assert tbody.count(f">{franja_t.nombre}<") == 1


def test_index_tooltip_del_cambio_describe_companero_turno_y_fecha(db, client):
    crear_usuario, unidad, _, franja_m = _setup(db, "g")
    franja_t = FranjaHoraria(
        nombre="Tarde", hora_inicio=time(15, 0), hora_fin=time(22, 0),
        grupo_intercambio=unidad.grupo_intercambio,
    )
    db.session.add(franja_t)
    db.session.commit()

    supervisora = crear_usuario("Super", "super_g@h.es", supervisora=True)
    ana = crear_usuario("Ana", "ana_g@h.es")
    claudia = crear_usuario("Claudia Pérez", "claudia_g@h.es")

    documento = DocumentoCambio(
        creado_por=ana, unidad=unidad, numero_unidad=1,
        decision_supervisora="autorizado", anulado=False,
    )
    db.session.add(documento)
    db.session.flush()
    documento.participantes.append(ParticipanteDocumentoCambio(
        usuario=ana,
        turno_cede_fecha=date(2026, 7, 10), turno_cede_franja=franja_m,
        turno_recibe_fecha=date(2026, 7, 11), turno_recibe_franja=franja_t,
    ))
    documento.participantes.append(ParticipanteDocumentoCambio(
        usuario=claudia,
        turno_cede_fecha=date(2026, 7, 11), turno_cede_franja=franja_t,
        turno_recibe_fecha=date(2026, 7, 10), turno_recibe_franja=franja_m,
    ))
    db.session.commit()

    _login(client, supervisora.email)
    resp = client.get("/planilla/supervision/?anyo=2026&mes=7")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Claudia Pérez" in html
    assert "10/07/2026" in html
    assert franja_m.nombre in html
    assert "Día afectado por un cambio autorizado" not in html


def test_index_modal_dia_enlaza_a_registrar_cambio_desde_papel(db, client):
    crear_usuario, unidad, _, _ = _setup(db, "x")
    supervisora = crear_usuario("Super", "super_x@h.es", supervisora=True)
    _login(client, supervisora.email)

    resp = client.get("/planilla/supervision/?anyo=2026&mes=7")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert 'id="sup-ajuste-registrar-papel"' in html
    assert "/documentos-cambio/registrar-papel" in html


def test_index_muestra_contador_de_presencia_por_franja_y_dia(db, client):
    crear_usuario, unidad, _, franja_m = _setup(db, "h")
    supervisora = crear_usuario("Super", "super_h@h.es", supervisora=True)
    ana = crear_usuario("Ana", "ana_h@h.es")
    bea = crear_usuario("Bea", "bea_h@h.es")
    añadir_turno(ana, date(2026, 7, 1), franja_m.id)
    añadir_turno(bea, date(2026, 7, 1), franja_m.id)
    _login(client, supervisora.email)

    resp = client.get("/planilla/supervision/?anyo=2026&mes=7")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    inicio = html.index('class="supervision-presencia-fila"')
    fin = html.index("</tr>", inicio)
    fila = html[inicio:fin]
    assert franja_m.nombre in fila
    assert ">2<" in fila


def test_index_contador_de_presencia_vacio_si_nadie_trabaja_esa_franja_ese_dia(db, client):
    crear_usuario, unidad, _, franja_m = _setup(db, "i")
    supervisora = crear_usuario("Super", "super_i@h.es", supervisora=True)
    _login(client, supervisora.email)

    resp = client.get("/planilla/supervision/?anyo=2026&mes=7")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    inicio = html.index('class="supervision-presencia-fila"')
    fin = html.index("</tr>", inicio)
    fila = html[inicio:fin]
    assert ">0<" not in fila
