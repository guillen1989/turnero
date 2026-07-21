import io
from datetime import time

from app.extensions import db
from app.models import Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria, Usuario, TurnoPlanilla
from app.models.planilla_import import MapeoTrabajadorPlanilla, MapeoCodigoTurno
from app.services.planilla_matching import resolver_o_crear_trabajador, vincular_usuario

CONTENIDO = (
    "Informe\n"
    "\tFecha inicial:\t01/01/2024\t\n"
    "\tFecha final:\t31/01/2024\t\n"
    "\tUnidad:\tPRUEBA\n"
    "\tDias\t\t1\t2\n"
    "\t\n"
    "\tPEREZ, ANA\t11111\tM\tT\n"
)


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

    def crear_usuario(nombre, email, password="password123", supervisora=False):
        u = Usuario(nombre=nombre, email=email, unidad=unidad, categoria=categoria, es_supervisora=supervisora)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        return u

    return crear_usuario, grupo, unidad, manyana, tarde


def _login(client, email, password="password123"):
    return client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=True)


def test_index_requiere_login(client):
    resp = client.get("/planilla/importar/")
    assert resp.status_code == 302


def test_index_prohibido_si_no_es_supervisora(db, client):
    crear_usuario, grupo, unidad, manyana, tarde = _setup(db, "a")
    normal = crear_usuario("Normal", "normal_a@h.es")
    _login(client, normal.email)

    resp = client.get("/planilla/importar/")
    assert resp.status_code == 403


def test_index_muestra_pendientes(db, client):
    crear_usuario, grupo, unidad, manyana, tarde = _setup(db, "b")
    supervisora = crear_usuario("Super", "super_b@h.es", supervisora=True)
    resolver_o_crear_trabajador(unidad, "99999", "GÓMEZ, LUIS")
    _login(client, supervisora.email)

    resp = client.get("/planilla/importar/")
    assert resp.status_code == 200
    assert "GÓMEZ, LUIS" in resp.data.decode("utf-8")


def test_subir_sin_codigos_mapeados_redirige_a_configurar_codigos(db, client):
    crear_usuario, grupo, unidad, manyana, tarde = _setup(db, "c")
    supervisora = crear_usuario("Super", "super_c@h.es", supervisora=True)
    _login(client, supervisora.email)

    resp = client.post(
        "/planilla/importar/",
        data={"archivo": (io.BytesIO(CONTENIDO.encode("latin-1")), "planilla.xls")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "código" in resp.data.decode("utf-8").lower()
    assert TurnoPlanilla.query.count() == 0


def test_configurar_codigos_guarda_el_mapeo(db, client):
    crear_usuario, grupo, unidad, manyana, tarde = _setup(db, "d")
    supervisora = crear_usuario("Super", "super_d@h.es", supervisora=True)
    _login(client, supervisora.email)

    resp = client.post(
        "/planilla/importar/codigos",
        data={f"codigos_{manyana.id}": "M, MC", f"codigos_{tarde.id}": "T"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert MapeoCodigoTurno.query.filter_by(codigo="M").first().franja_horaria_id == manyana.id
    assert MapeoCodigoTurno.query.filter_by(codigo="MC").first().franja_horaria_id == manyana.id
    assert MapeoCodigoTurno.query.filter_by(codigo="T").first().franja_horaria_id == tarde.id


def test_subir_con_codigos_mapeados_escribe_turnos_y_muestra_resumen(db, client):
    crear_usuario, grupo, unidad, manyana, tarde = _setup(db, "e")
    supervisora = crear_usuario("Super", "super_e@h.es", supervisora=True)
    ana = crear_usuario("Ana Pérez", "ana_e@h.es")
    trabajador = resolver_o_crear_trabajador(unidad, "11111", "PEREZ, ANA")
    vincular_usuario(trabajador, ana)
    _login(client, supervisora.email)

    from app.services.planilla_matching import establecer_mapeo_codigo
    establecer_mapeo_codigo(grupo, "M", manyana)
    establecer_mapeo_codigo(grupo, "T", tarde)

    resp = client.post(
        "/planilla/importar/",
        data={"archivo": (io.BytesIO(CONTENIDO.encode("latin-1")), "planilla.xls")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert TurnoPlanilla.query.filter_by(usuario_id=ana.id).count() == 2


def test_vincular_trabajador_pendiente(db, client):
    crear_usuario, grupo, unidad, manyana, tarde = _setup(db, "f")
    supervisora = crear_usuario("Super", "super_f@h.es", supervisora=True)
    luis = crear_usuario("Luis Gómez", "luis_f@h.es")
    trabajador = resolver_o_crear_trabajador(unidad, "99999", "GÓMEZ, LUIS")
    _login(client, supervisora.email)

    resp = client.post(
        f"/planilla/importar/{trabajador.id}/vincular",
        data={"usuario_id": luis.id},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    recuperado = db.session.get(MapeoTrabajadorPlanilla, trabajador.id)
    assert recuperado.usuario_id == luis.id


def test_vincular_prohibido_si_el_mapeo_es_de_otra_unidad(db, client):
    crear_usuario, grupo, unidad, manyana, tarde = _setup(db, "g")
    supervisora = crear_usuario("Super", "super_g@h.es", supervisora=True)

    crear_usuario2, grupo2, unidad2, manyana2, tarde2 = _setup(db, "h")
    trabajador_otra_unidad = resolver_o_crear_trabajador(unidad2, "55555", "OTRO, NOMBRE")

    _login(client, supervisora.email)
    resp = client.post(
        f"/planilla/importar/{trabajador_otra_unidad.id}/vincular",
        data={"usuario_id": 1},
    )
    assert resp.status_code == 403
