"""
Verifica que, al publicar un cambio, el sistema muestra en el flash
información de compatibilidad derivada de las planillas publicadas.
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


def test_flash_compatibilidad_sin_planillas(client, db):
    """Sin planillas publicadas no debe haber flash de compatibilidad."""
    _, _, franja_m, franja_t, crear = _setup(db)
    solicitante = crear("sol@t.es")
    _login(client, "sol@t.es")

    fecha = _fecha_futura()
    resp = client.post("/publicar", data={
        "tipo": "cambio",
        "fecha_cedida_0": fecha.isoformat(),
        "franja_cedida_0": franja_m.id,
        "fecha_aceptada_0": fecha.isoformat(),
        "franja_aceptada_0": franja_t.id,
    }, follow_redirects=True)
    assert resp.status_code == 200
    # Sin planillas de compañeros no debe aparecer info de compatibilidad
    assert b"libran ese" not in resp.data
    assert b"turno compatible" not in resp.data


def test_flash_compatibilidad_con_companero_libre(client, db):
    """Con un compañero libre ese día debe aparecer el flash."""
    _, _, franja_m, franja_t, crear = _setup(db)
    solicitante = crear("sol2@t.es")
    companero  = crear("comp2@t.es")

    # compañero publica su planilla de ese mes (sin turno ese día → libre)
    fecha = _fecha_futura()
    publicar_mes(companero, fecha.year, fecha.month)
    # solicitante también publica para ver nombres
    publicar_mes(solicitante, fecha.year, fecha.month)

    _login(client, "sol2@t.es")
    resp = client.post("/publicar", data={
        "tipo": "cambio",
        "fecha_cedida_0": fecha.isoformat(),
        "franja_cedida_0": franja_m.id,
        "fecha_aceptada_0": fecha.isoformat(),
        "franja_aceptada_0": franja_t.id,
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"libran ese" in resp.data


def test_flash_nudge_si_solicitante_no_tiene_planilla(client, db):
    """Si hay compañeros con planilla pero el solicitante no la publicó, aparece el nudge."""
    _, _, franja_m, franja_t, crear = _setup(db)
    solicitante = crear("sol3@t.es")
    companero   = crear("comp3@t.es")

    fecha = _fecha_futura()
    publicar_mes(companero, fecha.year, fecha.month)
    # solicitante NO publica

    _login(client, "sol3@t.es")
    resp = client.post("/publicar", data={
        "tipo": "cambio",
        "fecha_cedida_0": fecha.isoformat(),
        "franja_cedida_0": franja_m.id,
        "fecha_aceptada_0": fecha.isoformat(),
        "franja_aceptada_0": franja_t.id,
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Publica tu planilla" in resp.data


def test_flash_compatible_excluye_turno_solapante(client, db):
    """Un compañero con turno solapante no aparece como compatible."""
    _, _, franja_m, franja_t, crear = _setup(db)
    solicitante = crear("sol4@t.es")
    companero   = crear("comp4@t.es")

    fecha = _fecha_futura()
    publicar_mes(companero, fecha.year, fecha.month)
    publicar_mes(solicitante, fecha.year, fecha.month)
    añadir_turno(companero, fecha, franja_m.id)  # mismo turno → solapa

    _login(client, "sol4@t.es")
    resp = client.post("/publicar", data={
        "tipo": "cambio",
        "fecha_cedida_0": fecha.isoformat(),
        "franja_cedida_0": franja_m.id,
        "fecha_aceptada_0": fecha.isoformat(),
        "franja_aceptada_0": franja_t.id,
    }, follow_redirects=True)
    assert resp.status_code == 200
    # El compañero está trabajando el mismo turno → ni libre ni compatible
    assert b"libran ese" not in resp.data
    assert b"turno compatible" not in resp.data
