from datetime import date, time
from app.models import (
    Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria,
    Usuario, TurnoPlanilla, PlanillaMes,
)
from app.models.event import Event
from app.services.planilla import añadir_turno, publicar_mes, establecer_estado_dia


def _rellenar_mes(usuario, anyo, mes):
    """Marca todos los días del mes como 'libre' para pasar la validación de planilla completa."""
    import calendar
    _, num_dias = calendar.monthrange(anyo, mes)
    for d in range(1, num_dias + 1):
        establecer_estado_dia(usuario, date(anyo, mes, d), "libre")


def _crear_usuario_y_login(client, db, email="u@test.es"):
    hospital = Hospital(nombre=f"H-{email}")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    unidad = Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo)
    categoria = Categoria(nombre=f"Cat-{email}")
    franja = FranjaHoraria(
        nombre="Mañana", hora_inicio=time(8, 0), hora_fin=time(15, 0),
        grupo_intercambio=grupo,
    )
    db.session.add_all([unidad, categoria, franja])
    db.session.commit()

    usuario = Usuario(nombre="Ana", email=email, unidad=unidad, categoria=categoria)
    usuario.set_password("pass")
    db.session.add(usuario)
    db.session.commit()

    client.post("/auth/login", data={"email": email, "password": "pass"})
    return usuario, franja


def test_planilla_requiere_login(client):
    resp = client.get("/planilla/")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_planilla_carga_mes_actual(client, db):
    _crear_usuario_y_login(client, db)
    resp = client.get("/planilla/")
    assert resp.status_code == 200
    assert b"planilla" in resp.data.lower()


def test_planilla_muestra_dias_del_mes(client, db):
    _crear_usuario_y_login(client, db, "dias@test.es")
    resp = client.get("/planilla/?anyo=2026&mes=7")
    assert resp.status_code == 200
    assert b"Julio" in resp.data


def test_añadir_turno_via_ruta(client, db):
    usuario, franja = _crear_usuario_y_login(client, db, "add@test.es")
    resp = client.post("/planilla/turno/a%C3%B1adir", data={
        "fecha": "2026-07-01",
        "franja_id": franja.id,
        "anyo": 2026,
        "mes": 7,
    }, follow_redirects=False)
    assert resp.status_code in (302, 200)
    assert TurnoPlanilla.query.filter_by(usuario_id=usuario.id, fecha=date(2026, 7, 1)).count() == 1


def test_eliminar_turno_via_ruta(client, db):
    usuario, franja = _crear_usuario_y_login(client, db, "del@test.es")
    añadir_turno(usuario, date(2026, 7, 1), franja.id)

    client.post("/planilla/turno/eliminar", data={
        "fecha": "2026-07-01",
        "franja_id": franja.id,
        "anyo": 2026,
        "mes": 7,
    })
    assert TurnoPlanilla.query.filter_by(usuario_id=usuario.id, fecha=date(2026, 7, 1)).count() == 0


def test_publicar_mes_via_ruta(client, db):
    usuario, _ = _crear_usuario_y_login(client, db, "pub@test.es")
    _rellenar_mes(usuario, 2026, 7)
    client.post("/planilla/2026/7/publicar")
    planilla = PlanillaMes.query.filter_by(usuario_id=usuario.id, anyo=2026, mes=7).first()
    assert planilla is not None
    assert planilla.publicada


def test_publicar_mes_rechaza_mes_incompleto(client, db):
    """La ruta rechaza la publicación si quedan días sin cumplimentar."""
    usuario, franja = _crear_usuario_y_login(client, db, "incompleto@test.es")
    # Solo rellenamos los primeros 14 días de julio (faltan 31 - 14 = 17)
    for d in range(1, 15):
        establecer_estado_dia(usuario, date(2026, 7, d), "libre")
    resp = client.post("/planilla/2026/7/publicar", follow_redirects=True)
    assert resp.status_code == 200
    assert b"incompleta" in resp.data or b"sin cumplimentar" in resp.data
    planilla = PlanillaMes.query.filter_by(usuario_id=usuario.id, anyo=2026, mes=7).first()
    assert planilla is None or not planilla.publicada


def test_publicar_mes_aceptado_con_mes_completo(client, db):
    """La ruta acepta la publicación cuando todos los días están cubiertos."""
    usuario, _ = _crear_usuario_y_login(client, db, "completo@test.es")
    _rellenar_mes(usuario, 2026, 7)
    resp = client.post("/planilla/2026/7/publicar", follow_redirects=True)
    assert resp.status_code == 200
    planilla = PlanillaMes.query.filter_by(usuario_id=usuario.id, anyo=2026, mes=7).first()
    assert planilla is not None and planilla.publicada


def test_publicar_mes_registra_evento_para_analytics(client, db):
    """Cada publicación registra un Event 'planilla_publicada' para la serie temporal de analytics."""
    usuario, _ = _crear_usuario_y_login(client, db, "evento@test.es")
    _rellenar_mes(usuario, 2026, 7)
    client.post("/planilla/2026/7/publicar")
    planilla = PlanillaMes.query.filter_by(usuario_id=usuario.id, anyo=2026, mes=7).first()
    evento = Event.query.filter_by(event_type="planilla_publicada", user_id=usuario.id).first()
    assert evento is not None
    assert evento.entity_id == planilla.id


def test_despublicar_mes_via_ruta(client, db):
    usuario, _ = _crear_usuario_y_login(client, db, "despub@test.es")
    publicar_mes(usuario, 2026, 7)
    client.post("/planilla/2026/7/despublicar")
    planilla = PlanillaMes.query.filter_by(usuario_id=usuario.id, anyo=2026, mes=7).first()
    assert not planilla.publicada
