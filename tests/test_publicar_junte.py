"""Tests del tipo de publicación 'junte de noches'."""
from datetime import date, timedelta

from app.models import (
    Categoria, PublicacionCambio,
    TurnoCedido, TurnoAceptado, insertar_categorias_semilla,
)
from app.services.registro import registrar_usuario


def _proximo_lunes():
    hoy = date.today()
    dias = (7 - hoy.weekday()) % 7 or 7
    return hoy + timedelta(days=dias)


def _setup(client):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    u = registrar_usuario("Ana", "ana@test.es", "pass1234", "H", "U", cat.id)
    client.post("/auth/login", data={"email": "ana@test.es", "password": "pass1234"})
    return u


def _post_junte(client, semana, cadencia="LMVD", noches=None):
    data = {
        "tipo": "junte",
        "junte_semana": semana.isoformat(),
        "junte_cadencia": cadencia,
    }
    if noches:
        data["junte_noches"] = noches
    return client.post("/publicar", data=data, follow_redirects=False)


# --- Happy path ---

def test_junte_crea_publicacion(client, db):
    u = _setup(client)
    lunes = _proximo_lunes()
    # LMVD=[0,2,4,6], noches_post=[0,1,2,3] → cedidos=[4,6], aceptados=[1,3]
    resp = _post_junte(client, lunes, "LMVD", ["0", "1", "2", "3"])
    assert resp.status_code == 302
    pub = PublicacionCambio.query.filter_by(usuario_id=u.id).first()
    assert pub is not None
    assert pub.tipo == "junte"


def test_junte_tipo_lmvd_deriva_cedidos_y_aceptados_correctos(client, db):
    u = _setup(client)
    lunes = _proximo_lunes()
    # LMVD=[0,2,4,6], noches_post=[0,1,2,3]
    # cedidos = [4(Vie), 6(Dom)], aceptados = [1(Mar), 3(Jue)]
    _post_junte(client, lunes, "LMVD", ["0", "1", "2", "3"])
    pub = PublicacionCambio.query.filter_by(usuario_id=u.id).first()

    fechas_cedidas = {tc.fecha for tc in pub.turnos_cedidos}
    fechas_aceptadas = {ta.fecha for ta in pub.turnos_aceptados}

    assert lunes + timedelta(days=4) in fechas_cedidas    # Viernes
    assert lunes + timedelta(days=6) in fechas_cedidas    # Domingo
    assert lunes + timedelta(days=1) in fechas_aceptadas  # Martes
    assert lunes + timedelta(days=3) in fechas_aceptadas  # Jueves


def test_junte_tipo_mjs_deriva_cedidos_y_aceptados_correctos(client, db):
    u = _setup(client)
    lunes = _proximo_lunes()
    # MJS=[1,3,5], noches_post=[4,5,6]
    # cedidos = [1(Mar), 3(Jue)], aceptados = [4(Vie), 6(Dom)]
    _post_junte(client, lunes, "MJS", ["4", "5", "6"])
    pub = PublicacionCambio.query.filter_by(usuario_id=u.id).first()

    fechas_cedidas = {tc.fecha for tc in pub.turnos_cedidos}
    fechas_aceptadas = {ta.fecha for ta in pub.turnos_aceptados}

    assert lunes + timedelta(days=1) in fechas_cedidas    # Martes
    assert lunes + timedelta(days=3) in fechas_cedidas    # Jueves
    assert lunes + timedelta(days=4) in fechas_aceptadas  # Viernes
    assert lunes + timedelta(days=6) in fechas_aceptadas  # Domingo


def test_junte_acepta_fecha_en_medio_de_semana(client, db):
    """La semana se snappa al lunes aunque el usuario envíe un miércoles."""
    u = _setup(client)
    lunes = _proximo_lunes()
    miercoles = lunes + timedelta(days=2)
    resp = _post_junte(client, miercoles, "LMVD", ["0", "1", "2", "3"])
    assert resp.status_code == 302
    pub = PublicacionCambio.query.filter_by(usuario_id=u.id).first()
    # Los cedidos deben referirse a la semana del lunes, no del miércoles
    fechas_cedidas = {tc.fecha for tc in pub.turnos_cedidos}
    assert lunes + timedelta(days=4) in fechas_cedidas


# --- Validaciones ---

def test_junte_sin_cadencia_muestra_error(client, db):
    _setup(client)
    lunes = _proximo_lunes()
    resp = client.post("/publicar", data={
        "tipo": "junte",
        "junte_semana": lunes.isoformat(),
        "junte_noches": ["0", "1"],
    })
    assert resp.status_code == 200
    assert "cadencia" in resp.data.decode().lower()


def test_junte_sin_semana_muestra_error(client, db):
    _setup(client)
    resp = client.post("/publicar", data={
        "tipo": "junte",
        "junte_cadencia": "LMVD",
        "junte_noches": ["0", "1"],
    })
    assert resp.status_code == 200
    assert "semana" in resp.data.decode().lower()


def test_junte_sin_noches_post_muestra_error(client, db):
    """Sin noches seleccionadas no se cumplen los requisitos."""
    _setup(client)
    lunes = _proximo_lunes()
    resp = _post_junte(client, lunes, "LMVD", noches=None)
    assert resp.status_code == 200


def test_junte_cediendo_todas_las_noches_muestra_error(client, db):
    """Si el usuario selecciona exactamente sus noches propias, no cede nada."""
    _setup(client)
    lunes = _proximo_lunes()
    # LMVD=[0,2,4,6], si noches_post incluye [0,2,4,6] → cedidos vacíos
    resp = _post_junte(client, lunes, "LMVD", ["0", "2", "4", "6"])
    assert resp.status_code == 200
