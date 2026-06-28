"""
Verifica que, al publicar un cambio, el sistema persiste la compatibilidad de planilla
y la muestra como tarjeta en el dashboard (pestaña Activos).
"""
from datetime import date, time, timedelta
from app.models import (
    Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria, Usuario,
)
from app.services.planilla import añadir_turno, publicar_mes


def _setup(db):
    hospital = Hospital(nombre="H-Compat")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    unidad = Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo)
    categoria = Categoria(nombre="Enfermería")
    franja_m = FranjaHoraria(nombre="Mañana", hora_inicio=time(8), hora_fin=time(15), grupo_intercambio=grupo)
    franja_t = FranjaHoraria(nombre="Tarde",  hora_inicio=time(15), hora_fin=time(22), grupo_intercambio=grupo)
    db.session.add_all([unidad, categoria, franja_m, franja_t])
    db.session.commit()

    def crear(email):
        u = Usuario(nombre=email.split("@")[0], email=email, unidad=unidad, categoria=categoria)
        u.set_password("pass")
        db.session.add(u)
        db.session.commit()
        return u

    return unidad, categoria, franja_m, franja_t, crear


def _login(client, email):
    client.post("/auth/login", data={"email": email, "password": "pass"})


def _fecha_futura():
    return date.today() + timedelta(days=30)


def _publicar_cambio(client, franja_m, franja_t, fecha):
    return client.post("/publicar", data={
        "tipo": "cambio",
        "fecha_cedida_0": fecha.isoformat(),
        "franja_cedida_0": franja_m.id,
        "fecha_aceptada_0": fecha.isoformat(),
        "franja_aceptada_0": franja_t.id,
    }, follow_redirects=True)


def test_sin_planillas_no_aparece_compat(client, db):
    """Sin planillas publicadas la tarjeta de compatibilidad no aparece."""
    _, _, franja_m, franja_t, crear = _setup(db)
    crear("sol@t.es")
    _login(client, "sol@t.es")

    resp = _publicar_cambio(client, franja_m, franja_t, _fecha_futura())
    assert resp.status_code == 200
    assert b"libran ese" not in resp.data
    assert b"turno compatible" not in resp.data


def test_companero_libre_aparece_en_tarjeta(client, db):
    """Con un compañero libre ese día la tarjeta muestra que libra."""
    _, _, franja_m, franja_t, crear = _setup(db)
    solicitante = crear("sol2@t.es")
    companero  = crear("comp2@t.es")

    fecha = _fecha_futura()
    publicar_mes(companero, fecha.year, fecha.month)
    publicar_mes(solicitante, fecha.year, fecha.month)

    _login(client, "sol2@t.es")
    resp = _publicar_cambio(client, franja_m, franja_t, fecha)
    assert resp.status_code == 200
    # La tarjeta en Activos debe mostrar que el compañero libra ese día
    assert b"libran ese" in resp.data


def test_nudge_si_solicitante_sin_planilla(client, db):
    """Si el solicitante no ha publicado su planilla aparece el nudge de publicar."""
    _, _, franja_m, franja_t, crear = _setup(db)
    solicitante = crear("sol3@t.es")
    companero   = crear("comp3@t.es")

    fecha = _fecha_futura()
    publicar_mes(companero, fecha.year, fecha.month)
    # solicitante NO publica

    _login(client, "sol3@t.es")
    resp = _publicar_cambio(client, franja_m, franja_t, fecha)
    assert resp.status_code == 200
    assert b"Publica tu planilla" in resp.data


def test_turno_solapante_no_aparece_en_tarjeta(client, db):
    """Un compañero con turno solapante no aparece en la tarjeta."""
    _, _, franja_m, franja_t, crear = _setup(db)
    solicitante = crear("sol4@t.es")
    companero   = crear("comp4@t.es")

    fecha = _fecha_futura()
    publicar_mes(companero, fecha.year, fecha.month)
    publicar_mes(solicitante, fecha.year, fecha.month)
    añadir_turno(companero, fecha, franja_m.id)  # mismo turno → solapa

    _login(client, "sol4@t.es")
    resp = _publicar_cambio(client, franja_m, franja_t, fecha)
    assert resp.status_code == 200
    assert b"libran ese" not in resp.data
    assert b"turno compatible" not in resp.data
