import json
import re
from datetime import date, time

from app.models import (
    Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria, Usuario,
    DocumentoCambio, ParticipanteDocumentoCambio, AjustePlanillaSupervisora,
    UnidadSupervisada,
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
        if supervisora:
            db.session.add(UnidadSupervisada(usuario_id=usuario.id, unidad_id=u.id))
            db.session.commit()
        return usuario

    return crear_usuario, unidad, otra_unidad, franja_m


def _login(client, email, password="password123"):
    return client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=True)


def _contar_chips(tbody, nombre):
    """Cuenta chips de turno en la matriz (no confundir con las <option> del
    select del modal, que listan el nombre de la franja sin espacios alrededor)."""
    return len(re.findall(r">\s+" + re.escape(nombre) + r"\s+<", tbody))


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


# ── turno/eliminar ────────────────────────────────────────────────────────────

def test_turno_eliminar_requiere_login(client):
    resp = client.post("/planilla/supervision/turno/eliminar", data={})
    assert resp.status_code == 302


def test_turno_eliminar_prohibido_si_no_es_supervisora(db, client):
    crear_usuario, unidad, _, franja_m = _setup(db, "o")
    normal = crear_usuario("Normal", "normal_o@h.es")
    ana = crear_usuario("Ana", "ana_o@h.es")
    _login(client, normal.email)

    resp = client.post("/planilla/supervision/turno/eliminar", data={
        "usuario_id": ana.id, "fecha": "2026-07-01", "anyo": 2026, "mes": 7,
        "franja_id": franja_m.id,
    })
    assert resp.status_code == 403


def test_turno_eliminar_prohibido_si_trabajador_de_otra_unidad(db, client):
    crear_usuario, unidad, otra_unidad, franja_m = _setup(db, "p")
    supervisora = crear_usuario("Super", "super_p@h.es", supervisora=True)
    cris = crear_usuario("Cris", "cris_p@h.es", u=otra_unidad)
    _login(client, supervisora.email)

    resp = client.post("/planilla/supervision/turno/eliminar", data={
        "usuario_id": cris.id, "fecha": "2026-07-01", "anyo": 2026, "mes": 7,
        "franja_id": franja_m.id,
    })
    assert resp.status_code == 403
    assert AjustePlanillaSupervisora.query.count() == 0


def test_turno_eliminar_franja_de_otro_grupo_rechazada(db, client):
    crear_usuario, unidad, _, _ = _setup(db, "q")
    _, _, _, franja_otro_grupo = _setup(db, "r")
    supervisora = crear_usuario("Super", "super_q@h.es", supervisora=True)
    ana = crear_usuario("Ana", "ana_q@h.es")
    _login(client, supervisora.email)

    resp = client.post("/planilla/supervision/turno/eliminar", data={
        "usuario_id": ana.id, "fecha": "2026-07-01", "anyo": 2026, "mes": 7,
        "franja_id": franja_otro_grupo.id,
    })
    assert resp.status_code == 400
    assert AjustePlanillaSupervisora.query.count() == 0


def test_turno_eliminar_quita_solo_esa_franja_de_un_doblaje(db, client):
    crear_usuario, unidad, _, franja_m = _setup(db, "s")
    franja_t = FranjaHoraria(
        nombre="Tarde", hora_inicio=time(15, 0), hora_fin=time(22, 0),
        grupo_intercambio=unidad.grupo_intercambio,
    )
    db.session.add(franja_t)
    db.session.commit()

    supervisora = crear_usuario("Super", "super_s@h.es", supervisora=True)
    ana = crear_usuario("Ana", "ana_s@h.es")
    añadir_turno(ana, date(2026, 7, 1), franja_m.id)
    añadir_turno(ana, date(2026, 7, 1), franja_t.id)
    _login(client, supervisora.email)

    resp = client.post("/planilla/supervision/turno/eliminar", data={
        "usuario_id": ana.id, "fecha": "2026-07-01", "anyo": 2026, "mes": 7,
        "franja_id": franja_m.id, "motivo": "Cambio de turno",
    }, follow_redirects=True)
    assert resp.status_code == 200

    html = resp.data.decode("utf-8")
    tbody = html[html.index("<tbody>"):]
    assert _contar_chips(tbody, franja_m.nombre) == 0
    assert _contar_chips(tbody, franja_t.nombre) == 1

    ajuste = AjustePlanillaSupervisora.query.filter_by(usuario_id=ana.id).first()
    assert ajuste.motivo == "Cambio de turno"


# ── turno/editar ─────────────────────────────────────────────────────────────

def test_turno_editar_requiere_login(client):
    resp = client.post("/planilla/supervision/turno/editar", data={})
    assert resp.status_code == 302


def test_turno_editar_prohibido_si_no_es_supervisora(db, client):
    crear_usuario, unidad, _, franja_m = _setup(db, "t")
    normal = crear_usuario("Normal", "normal_t@h.es")
    ana = crear_usuario("Ana", "ana_t@h.es")
    _login(client, normal.email)

    resp = client.post("/planilla/supervision/turno/editar", data={
        "usuario_id": ana.id, "fecha": "2026-07-01", "anyo": 2026, "mes": 7,
        "franja_actual_id": franja_m.id, "franja_nueva_id": franja_m.id,
    })
    assert resp.status_code == 403


def test_turno_editar_prohibido_si_trabajador_de_otra_unidad(db, client):
    crear_usuario, unidad, otra_unidad, franja_m = _setup(db, "u")
    supervisora = crear_usuario("Super", "super_u@h.es", supervisora=True)
    cris = crear_usuario("Cris", "cris_u@h.es", u=otra_unidad)
    _login(client, supervisora.email)

    resp = client.post("/planilla/supervision/turno/editar", data={
        "usuario_id": cris.id, "fecha": "2026-07-01", "anyo": 2026, "mes": 7,
        "franja_actual_id": franja_m.id, "franja_nueva_id": franja_m.id,
    })
    assert resp.status_code == 403
    assert AjustePlanillaSupervisora.query.count() == 0


def test_turno_editar_franja_de_otro_grupo_rechazada(db, client):
    crear_usuario, unidad, _, franja_m = _setup(db, "v")
    _, _, _, franja_otro_grupo = _setup(db, "w")
    supervisora = crear_usuario("Super", "super_v@h.es", supervisora=True)
    ana = crear_usuario("Ana", "ana_v@h.es")
    _login(client, supervisora.email)

    resp = client.post("/planilla/supervision/turno/editar", data={
        "usuario_id": ana.id, "fecha": "2026-07-01", "anyo": 2026, "mes": 7,
        "franja_actual_id": franja_m.id, "franja_nueva_id": franja_otro_grupo.id,
    })
    assert resp.status_code == 400
    assert AjustePlanillaSupervisora.query.count() == 0


def test_turno_editar_sustituye_solo_esa_franja(db, client):
    crear_usuario, unidad, _, franja_m = _setup(db, "y")
    franja_t = FranjaHoraria(
        nombre="Tarde", hora_inicio=time(15, 0), hora_fin=time(22, 0),
        grupo_intercambio=unidad.grupo_intercambio,
    )
    franja_n = FranjaHoraria(
        nombre="Noche", hora_inicio=time(22, 0), hora_fin=time(8, 0),
        grupo_intercambio=unidad.grupo_intercambio,
    )
    db.session.add_all([franja_t, franja_n])
    db.session.commit()

    supervisora = crear_usuario("Super", "super_y@h.es", supervisora=True)
    ana = crear_usuario("Ana", "ana_y@h.es")
    añadir_turno(ana, date(2026, 7, 1), franja_m.id)
    añadir_turno(ana, date(2026, 7, 1), franja_t.id)
    _login(client, supervisora.email)

    resp = client.post("/planilla/supervision/turno/editar", data={
        "usuario_id": ana.id, "fecha": "2026-07-01", "anyo": 2026, "mes": 7,
        "franja_actual_id": franja_m.id, "franja_nueva_id": franja_n.id,
        "motivo": "Cambio de hora",
    }, follow_redirects=True)
    assert resp.status_code == 200

    html = resp.data.decode("utf-8")
    tbody = html[html.index("<tbody>"):]
    assert _contar_chips(tbody, franja_m.nombre) == 0
    assert _contar_chips(tbody, franja_n.nombre) == 1
    assert _contar_chips(tbody, franja_t.nombre) == 1

    ajuste = AjustePlanillaSupervisora.query.filter_by(usuario_id=ana.id).first()
    assert ajuste.motivo == "Cambio de hora"


def test_index_celda_lleva_datos_json_de_turnos_y_estado(db, client):
    crear_usuario, unidad, _, franja_m = _setup(db, "z2")
    franja_t = FranjaHoraria(
        nombre="Tarde", hora_inicio=time(15, 0), hora_fin=time(22, 0),
        grupo_intercambio=unidad.grupo_intercambio,
    )
    db.session.add(franja_t)
    db.session.commit()

    supervisora = crear_usuario("Super", "super_z2@h.es", supervisora=True)
    ana = crear_usuario("Ana", "ana_z2@h.es")
    bea = crear_usuario("Bea", "bea_z2@h.es")
    añadir_turno(ana, date(2026, 7, 1), franja_m.id)
    añadir_turno(ana, date(2026, 7, 1), franja_t.id)
    establecer_estado_dia(bea, date(2026, 7, 1), "libre")
    _login(client, supervisora.email)

    resp = client.get("/planilla/supervision/?anyo=2026&mes=7")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")

    celda_ana = re.search(
        rf'data-usuario-id="{ana.id}"[^>]*data-fecha="2026-07-01"[^>]*data-turnos=\'([^\']*)\'',
        html,
    )
    assert celda_ana is not None
    turnos = json.loads(celda_ana.group(1))
    assert {"franja_id": franja_m.id, "nombre": franja_m.nombre} in turnos
    assert {"franja_id": franja_t.id, "nombre": franja_t.nombre} in turnos

    celda_bea = re.search(
        rf'data-usuario-id="{bea.id}"[^>]*data-fecha="2026-07-01"[^>]*data-turnos=\'[^\']*\'\s*data-estado=\'([^\']*)\'',
        html,
    )
    assert celda_bea is not None
    estado = json.loads(celda_bea.group(1))
    assert estado == {"tipo": "libre", "etiqueta": "Libre"}


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
    assert tbody.count("supervision-celda--doblaje") == 1


def test_index_no_marca_doblaje_si_solo_hay_un_turno_ese_dia(db, client):
    crear_usuario, unidad, _, franja_m = _setup(db, "f2")
    supervisora = crear_usuario("Super", "super_f2@h.es", supervisora=True)
    ana = crear_usuario("Ana", "ana_f2@h.es")
    añadir_turno(ana, date(2026, 7, 1), franja_m.id)
    _login(client, supervisora.email)

    resp = client.get("/planilla/supervision/?anyo=2026&mes=7")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    tbody = html[html.index("<tbody>"):]
    assert "supervision-celda--doblaje" not in tbody


def test_index_fila_de_numeros_de_dia_tiene_clase_propia(db, client):
    crear_usuario, unidad, _, franja_m = _setup(db, "f3")
    supervisora = crear_usuario("Super", "super_f3@h.es", supervisora=True)
    _login(client, supervisora.email)

    resp = client.get("/planilla/supervision/?anyo=2026&mes=7")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    thead = html[html.index("<thead>"):html.index("</thead>")]
    assert "supervision-dianum-fila" in thead


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


# ── multiunidad ──────────────────────────────────────────────────────────────

def test_index_no_muestra_selector_de_unidad_si_solo_supervisa_una(db, client):
    crear_usuario, unidad, _, _ = _setup(db, "gg")
    supervisora = crear_usuario("Super", "super_gg@h.es", supervisora=True)
    _login(client, supervisora.email)

    resp = client.get("/planilla/supervision/?anyo=2026&mes=7")
    assert resp.status_code == 200
    assert 'aria-label="Unidad"' not in resp.data.decode("utf-8")


def test_index_muestra_selector_de_unidad_si_supervisa_varias(db, client):
    crear_usuario, unidad, otra_unidad, _ = _setup(db, "hh")
    supervisora = crear_usuario("Super", "super_hh@h.es", supervisora=True)
    db.session.add(UnidadSupervisada(usuario_id=supervisora.id, unidad_id=otra_unidad.id))
    db.session.commit()
    _login(client, supervisora.email)

    resp = client.get("/planilla/supervision/?anyo=2026&mes=7")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert 'aria-label="Unidad"' in html
    assert unidad.nombre in html
    assert otra_unidad.nombre in html


def test_index_supervisora_de_dos_unidades_ve_cada_una_por_separado(db, client):
    crear_usuario, unidad, otra_unidad, franja_m = _setup(db, "aa")
    supervisora = crear_usuario("Super", "super_aa@h.es", supervisora=True)
    db.session.add(UnidadSupervisada(usuario_id=supervisora.id, unidad_id=otra_unidad.id))
    db.session.commit()
    ana = crear_usuario("Ana", "ana_aa@h.es", u=unidad)
    cris = crear_usuario("Cris", "cris_aa@h.es", u=otra_unidad)
    _login(client, supervisora.email)

    resp_unidad = client.get(f"/planilla/supervision/?anyo=2026&mes=7&unidad_id={unidad.id}")
    assert resp_unidad.status_code == 200
    html_unidad = resp_unidad.data.decode("utf-8")
    assert "Ana" in html_unidad
    assert "Cris" not in html_unidad

    resp_otra = client.get(f"/planilla/supervision/?anyo=2026&mes=7&unidad_id={otra_unidad.id}")
    assert resp_otra.status_code == 200
    html_otra = resp_otra.data.decode("utf-8")
    assert "Cris" in html_otra
    assert "Ana" not in html_otra


def test_index_unidad_no_supervisada_devuelve_403(db, client):
    crear_usuario, unidad, _, _ = _setup(db, "bb")
    _, unidad_ajena, _, _ = _setup(db, "cc")
    supervisora = crear_usuario("Super", "super_bb@h.es", supervisora=True)
    _login(client, supervisora.email)

    resp = client.get(f"/planilla/supervision/?unidad_id={unidad_ajena.id}")
    assert resp.status_code == 403


def test_ajustar_en_segunda_unidad_supervisada_funciona(db, client):
    crear_usuario, unidad, otra_unidad, franja_m = _setup(db, "dd")
    supervisora = crear_usuario("Super", "super_dd@h.es", supervisora=True)
    db.session.add(UnidadSupervisada(usuario_id=supervisora.id, unidad_id=otra_unidad.id))
    db.session.commit()
    cris = crear_usuario("Cris", "cris_dd@h.es", u=otra_unidad)
    _login(client, supervisora.email)

    resp = client.post("/planilla/supervision/ajustar", data={
        "usuario_id": cris.id, "fecha": "2026-07-01", "anyo": 2026, "mes": 7,
        "seleccion": "libre", "unidad_id": otra_unidad.id,
    }, follow_redirects=True)
    assert resp.status_code == 200

    ajuste = AjustePlanillaSupervisora.query.filter_by(usuario_id=cris.id).first()
    assert ajuste is not None


def test_ajustar_unidad_no_supervisada_devuelve_403(db, client):
    crear_usuario, unidad, _, franja_m = _setup(db, "ee")
    _, unidad_ajena, _, _ = _setup(db, "ff")
    supervisora = crear_usuario("Super", "super_ee@h.es", supervisora=True)
    ana = crear_usuario("Ana", "ana_ee@h.es")
    _login(client, supervisora.email)

    resp = client.post("/planilla/supervision/ajustar", data={
        "usuario_id": ana.id, "fecha": "2026-07-01", "anyo": 2026, "mes": 7,
        "seleccion": "libre", "unidad_id": unidad_ajena.id,
    })
    assert resp.status_code == 403
    assert AjustePlanillaSupervisora.query.count() == 0
