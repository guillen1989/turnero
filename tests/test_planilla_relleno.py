"""
Tests para las rutas de relleno masivo de planilla:
- POST /planilla/rango/aplicar
- POST /planilla/multiples/aplicar
"""
from datetime import date, time
from app.models import Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria, Usuario, TurnoPlanilla
from app.services.planilla import establecer_estado_dia, get_estados_mes


def _setup(client, db, email="relleno@test.es"):
    hospital = Hospital(nombre=f"H-{email}")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    unidad = Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo)
    categoria = Categoria(nombre=f"Cat-{email}")
    franja_m = FranjaHoraria(
        nombre="Mañana", hora_inicio=time(8), hora_fin=time(15),
        grupo_intercambio=grupo,
    )
    franja_t = FranjaHoraria(
        nombre="Tarde", hora_inicio=time(15), hora_fin=time(22),
        grupo_intercambio=grupo,
    )
    db.session.add_all([unidad, categoria, franja_m, franja_t])
    db.session.commit()

    usuario = Usuario(nombre="Test", email=email, unidad=unidad, categoria=categoria)
    usuario.set_password("pass")
    db.session.add(usuario)
    db.session.commit()

    client.post("/auth/login", data={"email": email, "password": "pass"})
    return usuario, franja_m, franja_t


# ── /rango/aplicar ────────────────────────────────────────────────────────────

def test_rango_aplica_estado_a_varios_dias(client, db):
    usuario, franja_m, _ = _setup(client, db, "rango_estado@t.es")
    resp = client.post("/planilla/rango/aplicar", data={
        "dia_inicio": 1,
        "dia_fin": 5,
        "seleccion": "libre",
        "anyo": 2026,
        "mes": 7,
    }, follow_redirects=False)
    assert resp.status_code == 302
    estados = get_estados_mes(usuario, 2026, 7)
    assert len(estados) == 5
    for d in range(1, 6):
        assert estados[date(2026, 7, d)].tipo == "libre"
    # Día 6 sin tocar
    assert date(2026, 7, 6) not in estados


def test_rango_aplica_turno_a_varios_dias(client, db):
    usuario, franja_m, _ = _setup(client, db, "rango_turno@t.es")
    client.post("/planilla/rango/aplicar", data={
        "dia_inicio": 10,
        "dia_fin": 12,
        "seleccion": str(franja_m.id),
        "anyo": 2026,
        "mes": 7,
    })
    turnos = TurnoPlanilla.query.filter_by(usuario_id=usuario.id).all()
    fechas = {t.fecha for t in turnos}
    assert date(2026, 7, 10) in fechas
    assert date(2026, 7, 11) in fechas
    assert date(2026, 7, 12) in fechas
    assert date(2026, 7, 9) not in fechas


def test_rango_invierte_si_fin_antes_inicio(client, db):
    """Si dia_fin < dia_inicio los intercambia silenciosamente."""
    usuario, franja_m, _ = _setup(client, db, "rango_inv@t.es")
    client.post("/planilla/rango/aplicar", data={
        "dia_inicio": 5,
        "dia_fin": 3,
        "seleccion": "libre",
        "anyo": 2026,
        "mes": 7,
    })
    estados = get_estados_mes(usuario, 2026, 7)
    # Debe haber rellenado días 3, 4 y 5
    assert len(estados) == 3
    assert date(2026, 7, 3) in estados


def test_rango_rechaza_sin_seleccion(client, db):
    usuario, _, _ = _setup(client, db, "rango_vacio@t.es")
    resp = client.post("/planilla/rango/aplicar", data={
        "dia_inicio": 1,
        "dia_fin": 3,
        "seleccion": "",
        "anyo": 2026,
        "mes": 7,
    }, follow_redirects=True)
    assert resp.status_code == 200
    estados = get_estados_mes(usuario, 2026, 7)
    assert len(estados) == 0


def test_rango_un_solo_dia(client, db):
    """Rango donde inicio == fin: aplica exactamente 1 día."""
    usuario, _, _ = _setup(client, db, "rango_uno@t.es")
    client.post("/planilla/rango/aplicar", data={
        "dia_inicio": 15,
        "dia_fin": 15,
        "seleccion": "vacaciones",
        "anyo": 2026,
        "mes": 7,
    })
    estados = get_estados_mes(usuario, 2026, 7)
    assert len(estados) == 1
    assert estados[date(2026, 7, 15)].tipo == "vacaciones"


# ── /multiples/aplicar ────────────────────────────────────────────────────────

def test_multiples_aplica_a_fechas_seleccionadas(client, db):
    usuario, franja_m, _ = _setup(client, db, "multi_estado@t.es")
    fechas = [date(2026, 7, 1), date(2026, 7, 7), date(2026, 7, 15)]
    resp = client.post("/planilla/multiples/aplicar", data={
        "fecha[]": [f.isoformat() for f in fechas],
        "seleccion": "libre",
        "anyo": 2026,
        "mes": 7,
    }, follow_redirects=False)
    assert resp.status_code == 302
    estados = get_estados_mes(usuario, 2026, 7)
    assert len(estados) == 3
    for fecha in fechas:
        assert estados[fecha].tipo == "libre"


def test_multiples_aplica_turno_a_fechas_seleccionadas(client, db):
    usuario, franja_m, _ = _setup(client, db, "multi_turno@t.es")
    fechas = [date(2026, 7, 2), date(2026, 7, 9)]
    client.post("/planilla/multiples/aplicar", data={
        "fecha[]": [f.isoformat() for f in fechas],
        "seleccion": str(franja_m.id),
        "anyo": 2026,
        "mes": 7,
    })
    turnos = TurnoPlanilla.query.filter_by(usuario_id=usuario.id).all()
    fechas_turno = {t.fecha for t in turnos}
    assert date(2026, 7, 2) in fechas_turno
    assert date(2026, 7, 9) in fechas_turno


def test_multiples_ignora_fechas_de_otro_mes(client, db):
    """Fechas de otro mes son descartadas por seguridad."""
    usuario, _, _ = _setup(client, db, "multi_otro@t.es")
    client.post("/planilla/multiples/aplicar", data={
        "fecha[]": ["2026-08-01", "2026-07-05"],  # agosto se ignora
        "seleccion": "libre",
        "anyo": 2026,
        "mes": 7,
    })
    estados = get_estados_mes(usuario, 2026, 7)
    assert len(estados) == 1
    assert date(2026, 7, 5) in estados
    # Agosto no debe verse afectado
    estados_agosto = get_estados_mes(usuario, 2026, 8)
    assert len(estados_agosto) == 0


def test_multiples_sin_fechas_no_hace_nada(client, db):
    usuario, _, _ = _setup(client, db, "multi_vacio@t.es")
    resp = client.post("/planilla/multiples/aplicar", data={
        "seleccion": "libre",
        "anyo": 2026,
        "mes": 7,
    }, follow_redirects=False)
    assert resp.status_code == 302
    assert get_estados_mes(usuario, 2026, 7) == {}
