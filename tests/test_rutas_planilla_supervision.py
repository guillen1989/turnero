from datetime import date, time

from app.models import (
    Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria, Usuario,
    DocumentoCambio, ParticipanteDocumentoCambio,
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
