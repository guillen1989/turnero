"""Tests de integración para publicar un cambio de turno (Fase 3, paso 2)."""
from datetime import date, time

from app.models import (
    Categoria,
    FranjaHoraria,
    PublicacionCambio,
    TurnoCedido,
    TurnoAceptado,
    insertar_categorias_semilla,
)
from app.services.registro import registrar_usuario


def _usuario_y_login(client, email="test@test.es"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    usuario = registrar_usuario(
        "Test User", email, "password123", "Hospital T", "Urgencias", cat.id
    )
    client.post("/auth/login", data={"email": email, "password": "password123"})
    return usuario


def _franja(db, grupo_id, nombre="Mañana"):
    return FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id, nombre=nombre).first()


# --- Acceso a la ruta ---

def test_publicar_requiere_login(client, db):
    resp = client.get("/publicar", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_get_publicar_devuelve_formulario(client, db):
    usuario = _usuario_y_login(client)
    _franja(db, usuario.unidad.grupo_intercambio_id)
    resp = client.get("/publicar")
    assert resp.status_code == 200
    assert b"Publicar cambio" in resp.data


def test_get_publicar_incluye_franjas_de_serie_en_datos_del_calendario(client, db):
    usuario = _usuario_y_login(client)
    _franja(db, usuario.unidad.grupo_intercambio_id)
    resp = client.get("/publicar")
    assert resp.status_code == 200
    assert b'id="franjas-data"' in resp.data
    assert b'"nombre": "Ma\\u00f1ana"' in resp.data
    assert b'"nombre": "Tarde"' in resp.data


def test_get_publicar_incluye_franja_personalizada_en_datos_del_calendario(client, db):
    """El calendario tap-to-select no puede limitarse a Mañana/Tarde/Noche:
    una unidad puede tener más franjas, incluidas las creadas por sus propios
    usuarios (B4), así que deben llegar al JS igual que las de serie."""
    usuario = _usuario_y_login(client)
    grupo_id = usuario.unidad.grupo_intercambio_id
    _franja(db, grupo_id)
    franja_custom = FranjaHoraria(
        nombre="Guardia 24h",
        hora_inicio=time(8, 0),
        hora_fin=time(8, 0),
        grupo_intercambio_id=grupo_id,
        color="#8B5CF6",
    )
    db.session.add(franja_custom)
    db.session.commit()

    resp = client.get("/publicar")
    assert resp.status_code == 200
    assert b'"nombre": "Guardia 24h"' in resp.data
    assert b'"color": "#8B5CF6"' in resp.data


# --- Creación de la publicación ---

def test_publicar_crea_publicacion_en_bd(client, db):
    usuario = _usuario_y_login(client)
    franja = _franja(db, usuario.unidad.grupo_intercambio_id)
    resp = client.post("/publicar", data={
        "fecha_cedida_0": "2026-09-01",
        "franja_cedida_0": franja.id,
        "fecha_aceptada_0": "2026-09-02",
        "franja_aceptada_0": franja.id,
    }, follow_redirects=False)
    assert resp.status_code == 302
    assert PublicacionCambio.query.filter_by(usuario_id=usuario.id).count() == 1


def test_publicar_crea_turnos_cedidos_y_aceptados(client, db):
    usuario = _usuario_y_login(client)
    franja = _franja(db, usuario.unidad.grupo_intercambio_id)
    client.post("/publicar", data={
        "fecha_cedida_0": "2026-09-01",
        "franja_cedida_0": franja.id,
        "fecha_aceptada_0": "2026-09-02",
        "franja_aceptada_0": franja.id,
    })
    pub = PublicacionCambio.query.filter_by(usuario_id=usuario.id).first()
    assert pub is not None
    assert len(pub.turnos_cedidos) == 1
    assert len(pub.turnos_aceptados) == 1
    assert pub.turnos_cedidos[0].fecha == date(2026, 9, 1)
    assert pub.turnos_aceptados[0].fecha == date(2026, 9, 2)


def test_publicar_multiples_turnos_cedidos(client, db):
    usuario = _usuario_y_login(client)
    franja = _franja(db, usuario.unidad.grupo_intercambio_id)
    client.post("/publicar", data={
        "fecha_cedida_0": "2026-09-01",
        "franja_cedida_0": franja.id,
        "fecha_cedida_1": "2026-09-03",
        "franja_cedida_1": franja.id,
        "fecha_aceptada_0": "2026-09-02",
        "franja_aceptada_0": franja.id,
    })
    pub = PublicacionCambio.query.filter_by(usuario_id=usuario.id).first()
    assert pub is not None
    assert len(pub.turnos_cedidos) == 2


def test_publicar_redirige_al_dashboard(client, db):
    usuario = _usuario_y_login(client)
    franja = _franja(db, usuario.unidad.grupo_intercambio_id)
    resp = client.post("/publicar", data={
        "fecha_cedida_0": "2026-09-01",
        "franja_cedida_0": franja.id,
        "fecha_aceptada_0": "2026-09-02",
        "franja_aceptada_0": franja.id,
    }, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")


def test_publicar_sin_turno_cedido_muestra_error(client, db):
    usuario = _usuario_y_login(client)
    _franja(db, usuario.unidad.grupo_intercambio_id)
    resp = client.post("/publicar", data={
        "fecha_aceptada_0": "2026-09-02",
        "franja_aceptada_0": 1,
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert PublicacionCambio.query.count() == 0


def test_publicar_rechaza_turno_cedido_con_fecha_pasada(client, db):
    from datetime import date, timedelta
    usuario = _usuario_y_login(client)
    franja = _franja(db, usuario.unidad.grupo_intercambio_id)
    ayer = (date.today() - timedelta(days=1)).isoformat()
    resp = client.post("/publicar", data={
        "fecha_cedida_0": ayer,
        "franja_cedida_0": franja.id,
        "fecha_aceptada_0": "2026-09-02",
        "franja_aceptada_0": franja.id,
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert PublicacionCambio.query.count() == 0


def test_publicar_regalo_crea_publicacion_sin_cedidos(client, db):
    """Un regalo publica solo turnos aceptados (nada que ceder)."""
    usuario = _usuario_y_login(client)
    franja = _franja(db, usuario.unidad.grupo_intercambio_id)
    resp = client.post("/publicar", data={
        "tipo": "regalo",
        "fecha_aceptada_0": "2026-09-01",
        "franja_aceptada_0": franja.id,
    }, follow_redirects=False)
    assert resp.status_code == 302
    pub = PublicacionCambio.query.filter_by(usuario_id=usuario.id).first()
    assert pub is not None
    assert pub.tipo == "regalo"
    assert len(pub.turnos_cedidos) == 0
    assert len(pub.turnos_aceptados) == 1


def test_publicar_peticion_crea_publicacion_sin_aceptados(client, db):
    """Una petición publica solo turnos cedidos (nada que ofrecer)."""
    usuario = _usuario_y_login(client)
    franja = _franja(db, usuario.unidad.grupo_intercambio_id)
    resp = client.post("/publicar", data={
        "tipo": "peticion",
        "fecha_cedida_0": "2026-09-01",
        "franja_cedida_0": franja.id,
    }, follow_redirects=False)
    assert resp.status_code == 302
    pub = PublicacionCambio.query.filter_by(usuario_id=usuario.id).first()
    assert pub is not None
    assert pub.tipo == "peticion"
    assert len(pub.turnos_cedidos) == 1
    assert len(pub.turnos_aceptados) == 0


def test_publicar_acepta_cualquier_franja_en_turno_aceptado(client, db):
    """Al ofrecer 'cualquier franja', el turno aceptado se guarda con franja_horaria_id=None."""
    usuario = _usuario_y_login(client)
    franja = _franja(db, usuario.unidad.grupo_intercambio_id)
    resp = client.post("/publicar", data={
        "tipo": "cambio",
        "fecha_cedida_0": "2026-09-01",
        "franja_cedida_0": franja.id,
        "fecha_aceptada_0": "2026-09-02",
        "franja_aceptada_0": "0",  # 0 = cualquier franja
    }, follow_redirects=False)
    assert resp.status_code == 302
    pub = PublicacionCambio.query.filter_by(usuario_id=usuario.id).first()
    assert pub is not None
    assert pub.turnos_aceptados[0].franja_horaria_id is None
    assert pub.turnos_aceptados[0].cualquier_franja is True


def test_publicar_rechaza_turno_aceptado_con_fecha_pasada(client, db):
    from datetime import date, timedelta
    usuario = _usuario_y_login(client)
    franja = _franja(db, usuario.unidad.grupo_intercambio_id)
    ayer = (date.today() - timedelta(days=1)).isoformat()
    resp = client.post("/publicar", data={
        "fecha_cedida_0": "2026-09-01",
        "franja_cedida_0": franja.id,
        "fecha_aceptada_0": ayer,
        "franja_aceptada_0": franja.id,
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert PublicacionCambio.query.count() == 0


# --- Prefill de fecha/modo vía query params (Ronda 2, Paso 2) ---
#
# El formulario ya no tiene inputs de fecha estáticos (el calendario
# tap-to-select los genera por JS al tocar un día), así que el prefill se
# entrega al JS como constantes en el <script> inline en vez de un
# value="" en un <input>. El widget usa esas constantes para abrir el mes
# correcto y resaltar el día sugerido (comportamiento verificado en e2e).

def test_publicar_prefill_modo_ofertas_precarga_fecha_aceptada(client, db):
    usuario = _usuario_y_login(client)
    _franja(db, usuario.unidad.grupo_intercambio_id)
    resp = client.get("/publicar?fecha=2026-07-15&modo=ofertas")
    assert resp.status_code == 200
    assert b'var PREFILL_FECHA = "2026-07-15";' in resp.data
    assert b'var PREFILL_MODO = "ofertas";' in resp.data


def test_publicar_prefill_modo_peticiones_precarga_fecha_cedida(client, db):
    usuario = _usuario_y_login(client)
    _franja(db, usuario.unidad.grupo_intercambio_id)
    resp = client.get("/publicar?fecha=2026-08-02&modo=peticiones")
    assert resp.status_code == 200
    assert b'var PREFILL_FECHA = "2026-08-02";' in resp.data
    assert b'var PREFILL_MODO = "peticiones";' in resp.data


def test_publicar_sin_prefill_no_precarga_nada(client, db):
    usuario = _usuario_y_login(client)
    _franja(db, usuario.unidad.grupo_intercambio_id)
    resp = client.get("/publicar")
    assert resp.status_code == 200
    assert b'var PREFILL_FECHA = "";' in resp.data
    assert b'var PREFILL_MODO = "";' in resp.data


def test_publicar_prefill_fecha_invalida_se_ignora(client, db):
    usuario = _usuario_y_login(client)
    _franja(db, usuario.unidad.grupo_intercambio_id)
    resp = client.get("/publicar?fecha=no-es-una-fecha&modo=ofertas")
    assert resp.status_code == 200
    assert b'var PREFILL_FECHA = "";' in resp.data
    assert b'var PREFILL_MODO = "";' in resp.data
