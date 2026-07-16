"""Tests del sistema de búsquedas guardadas con alertas."""
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.extensions import db as _db
from app.models import BusquedaGuardada, Categoria, Notificacion, insertar_categorias_semilla
from app.models.publicacion import PublicacionCambio, TurnoCedido, TurnoAceptado
from app.services.busquedas_guardadas import (
    eliminar_busqueda,
    guardar_busqueda,
    publicacion_cumple_filtros,
)
from app.services.publicaciones import publicar_cambio
from app.services.registro import registrar_usuario
from werkzeug.exceptions import Forbidden


# --- Helpers ---

def _usuario(email="u1@test.es", nombre="User1", unidad="Urgencias"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario(nombre, email, "pass123", "H1", unidad, cat.id)


def _usuario2(email="u2@test.es", nombre="User2", unidad="Urgencias"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario(nombre, email, "pass456", "H1", unidad, cat.id)


def _franja_id(usuario):
    return usuario.unidad.grupo_intercambio.franjas_horarias.first().id


def _usuario_n(n, unidad="Urgencias"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario(f"User{n}", f"u{n}@test.es", "pass123", "H1", unidad, cat.id)


def _login(client, email, password="pass123"):
    client.post("/auth/login", data={"email": email, "password": password})


# --- Tests de la función pura publicacion_cumple_filtros ---

class TestPublicacionCumpleFiltros:
    def _tc(self, fecha, franja_id):
        t = MagicMock(spec=TurnoCedido)
        t.fecha = fecha
        t.franja_horaria_id = franja_id
        return t

    def _ta(self, fecha, franja_id=None, cualquier_franja=False):
        t = MagicMock(spec=TurnoAceptado)
        t.fecha = fecha
        t.franja_horaria_id = franja_id
        t.cualquier_franja = cualquier_franja
        return t

    def _pub(self, tipo="cambio", cedidos=None, aceptados=None, nombre="Ana"):
        pub = MagicMock(spec=PublicacionCambio)
        pub.tipo = tipo
        pub.usuario = MagicMock()
        pub.usuario.nombre = nombre
        pub.turnos_cedidos = cedidos or []
        pub.turnos_aceptados = aceptados or []
        return pub

    def test_filtro_vacio_acepta_cualquier_pub(self):
        assert publicacion_cumple_filtros(self._pub(), {}) is True

    def test_filtro_tipo_acepta_coincidencia(self):
        assert publicacion_cumple_filtros(self._pub("regalo"), {"tipo": "regalo"}) is True

    def test_filtro_tipo_rechaza_distinto(self):
        assert publicacion_cumple_filtros(self._pub("cambio"), {"tipo": "regalo"}) is False

    def test_filtro_mes_acepta_turno_cedido_en_ese_mes(self):
        tc = self._tc(date(2025, 7, 10), 1)
        assert publicacion_cumple_filtros(self._pub(cedidos=[tc]), {"mes": 7}) is True

    def test_filtro_mes_rechaza_turno_en_otro_mes(self):
        tc = self._tc(date(2025, 6, 10), 1)
        assert publicacion_cumple_filtros(self._pub(cedidos=[tc]), {"mes": 7}) is False

    def test_filtro_mes_acepta_turno_aceptado_en_ese_mes(self):
        ta = self._ta(date(2025, 7, 15))
        assert publicacion_cumple_filtros(self._pub(aceptados=[ta]), {"mes": 7}) is True

    def test_filtro_franja_acepta_coincidencia_en_cedido(self):
        tc = self._tc(date(2025, 7, 10), 3)
        assert publicacion_cumple_filtros(self._pub(cedidos=[tc]), {"franja_id": 3}) is True

    def test_filtro_franja_rechaza_franja_distinta(self):
        tc = self._tc(date(2025, 7, 10), 3)
        assert publicacion_cumple_filtros(self._pub(cedidos=[tc]), {"franja_id": 5}) is False

    def test_filtro_franja_acepta_coincidencia_en_aceptado(self):
        ta = self._ta(date(2025, 7, 10), franja_id=3, cualquier_franja=False)
        assert publicacion_cumple_filtros(self._pub(aceptados=[ta]), {"franja_id": 3}) is True

    def test_filtro_franja_ignora_cualquier_franja(self):
        ta = self._ta(date(2025, 7, 10), franja_id=None, cualquier_franja=True)
        assert publicacion_cumple_filtros(self._pub(aceptados=[ta]), {"franja_id": 3}) is False

    def test_filtro_nombre_parcial_case_insensitive(self):
        pub = self._pub(nombre="Ana García")
        assert publicacion_cumple_filtros(pub, {"nombre": "ana"}) is True

    def test_filtro_nombre_rechaza_no_coincide(self):
        pub = self._pub(nombre="Ana García")
        assert publicacion_cumple_filtros(pub, {"nombre": "carlos"}) is False

    def test_multiples_filtros_todos_deben_cumplirse(self):
        tc = self._tc(date(2025, 7, 10), 3)
        pub = self._pub("regalo", cedidos=[tc])
        assert publicacion_cumple_filtros(pub, {"tipo": "regalo", "mes": 7}) is True
        assert publicacion_cumple_filtros(pub, {"tipo": "cambio", "mes": 7}) is False

    def test_filtro_dia_acepta_coincidencia(self):
        tc = self._tc(date(2025, 7, 10), 1)
        assert publicacion_cumple_filtros(self._pub(cedidos=[tc]), {"dia": 10}) is True

    def test_filtro_dia_rechaza_otro_dia(self):
        tc = self._tc(date(2025, 7, 10), 1)
        assert publicacion_cumple_filtros(self._pub(cedidos=[tc]), {"dia": 15}) is False


# --- Tests de operaciones de BD ---

def test_guardar_busqueda_genera_nombre(db):
    u = _usuario()
    b = guardar_busqueda(u.id, {"tipo": "regalo", "mes": 7})
    assert b.id is not None
    assert b.nombre == "Regalos · Julio"
    assert b.filtros == {"tipo": "regalo", "mes": 7}


def test_guardar_busqueda_sin_filtros(db):
    u = _usuario()
    b = guardar_busqueda(u.id, {})
    assert b.nombre == "Todos los cambios"


def test_guardar_busqueda_con_franja_nombre(db):
    u = _usuario()
    b = guardar_busqueda(u.id, {"franja_id": 1, "franja_nombre": "Mañana"})
    assert "Mañana" in b.nombre


def test_eliminar_busqueda_propietario(db):
    u = _usuario()
    b = guardar_busqueda(u.id, {"tipo": "regalo"})
    bid = b.id
    eliminar_busqueda(bid, u.id)
    assert _db.session.get(BusquedaGuardada, bid) is None


def test_eliminar_busqueda_otro_usuario_lanza_forbidden(db):
    u1 = _usuario()
    u2 = _usuario2()
    b = guardar_busqueda(u1.id, {"tipo": "regalo"})
    with pytest.raises(Forbidden):
        eliminar_busqueda(b.id, u2.id)


# --- Tests de integración: notificación al publicar ---

def test_publicar_notifica_busqueda_guardada_coincidente(app, db):
    u1 = _usuario()
    u2 = _usuario2()
    guardar_busqueda(u1.id, {"tipo": "regalo"})
    franja = _franja_id(u2)
    with patch("app.push.sender.webpush"):
        publicar_cambio(u2.id, [], [(date(2025, 7, 10), franja)], tipo="regalo")
    notif = Notificacion.query.filter_by(
        usuario_id=u1.id, tipo="alerta_busqueda_guardada"
    ).first()
    assert notif is not None
    assert notif.publicacion_id is not None


def test_publicar_no_notifica_si_busqueda_no_coincide(app, db):
    u1 = _usuario()
    u2 = _usuario2()
    guardar_busqueda(u1.id, {"tipo": "peticion"})
    franja = _franja_id(u2)
    with patch("app.push.sender.webpush"):
        publicar_cambio(u2.id, [], [(date(2025, 7, 10), franja)], tipo="regalo")
    notif = Notificacion.query.filter_by(
        usuario_id=u1.id, tipo="alerta_busqueda_guardada"
    ).first()
    assert notif is None


def test_publicar_no_notifica_al_propio_publicador(app, db):
    u1 = _usuario()
    guardar_busqueda(u1.id, {"tipo": "regalo"})
    franja = _franja_id(u1)
    with patch("app.push.sender.webpush"):
        publicar_cambio(u1.id, [], [(date(2025, 7, 10), franja)], tipo="regalo")
    notif = Notificacion.query.filter_by(
        usuario_id=u1.id, tipo="alerta_busqueda_guardada"
    ).first()
    assert notif is None


def test_notificar_busquedas_guardadas_no_crece_con_n(app, db, query_counter):
    """No debe haber una query SELECT extra por cada búsqueda guardada coincidente
    (regresión del N+1 en notificar_busquedas_guardadas: antes hacía un
    db.session.get(Usuario, ...) por cada búsqueda dentro del bucle). Cada
    búsqueda debe pertenecer a un usuario *distinto*: con el mismo usuario
    repetido, el identity map de SQLAlchemy serviría el get() de caché y
    ocultaría el N+1."""
    publicador = _usuario_n(0)
    franja = _franja_id(publicador)

    buscador_1 = _usuario_n(1)
    guardar_busqueda(buscador_1.id, {})
    with patch("app.services.busquedas_guardadas.enviar_push_condicional"):
        query_counter.selects = 0
        publicar_cambio(publicador.id, [], [(date(2025, 7, 10), franja)], tipo="regalo")
        selects_con_1_busqueda = query_counter.selects

        for n in range(2, 6):
            buscador = _usuario_n(n)
            guardar_busqueda(buscador.id, {})

        query_counter.selects = 0
        publicar_cambio(publicador.id, [], [(date(2025, 7, 11), franja)], tipo="regalo")
        selects_con_5_busquedas = query_counter.selects

    assert selects_con_5_busquedas == selects_con_1_busqueda


def test_publicar_notifica_por_mes(app, db):
    u1 = _usuario()
    u2 = _usuario2()
    guardar_busqueda(u1.id, {"mes": 7})
    franja = _franja_id(u2)
    with patch("app.push.sender.webpush"):
        publicar_cambio(u2.id, [(date(2025, 7, 5), franja)], [(date(2025, 7, 6), franja)])
    notif = Notificacion.query.filter_by(
        usuario_id=u1.id, tipo="alerta_busqueda_guardada"
    ).first()
    assert notif is not None


# --- Tests de rutas ---

def test_ruta_guardar_busqueda_requiere_login(client, db):
    resp = client.post("/busquedas-guardadas", data={"tipo": "regalo"})
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_ruta_guardar_busqueda(client, db):
    u = _usuario()
    _login(client, "u1@test.es")
    resp = client.post("/busquedas-guardadas", data={"tipo": "regalo", "mes": "7"})
    assert resp.status_code == 302
    b = BusquedaGuardada.query.filter_by(usuario_id=u.id).first()
    assert b is not None
    assert b.filtros.get("tipo") == "regalo"
    assert b.filtros.get("mes") == 7


def test_ruta_eliminar_busqueda(client, db):
    u = _usuario()
    b = guardar_busqueda(u.id, {"tipo": "regalo"})
    _login(client, "u1@test.es")
    resp = client.post(f"/busquedas-guardadas/{b.id}/eliminar")
    assert resp.status_code == 302
    assert _db.session.get(BusquedaGuardada, b.id) is None


def test_ruta_eliminar_busqueda_ajena_da_403(client, db):
    u1 = _usuario()
    u2 = _usuario2()
    b = guardar_busqueda(u1.id, {"tipo": "regalo"})
    _login(client, "u2@test.es", "pass456")
    resp = client.post(f"/busquedas-guardadas/{b.id}/eliminar")
    assert resp.status_code == 403


def test_cambios_muestra_pestana_alertas(client, db):
    _usuario()
    _login(client, "u1@test.es")
    resp = client.get("/cambios")
    assert resp.status_code == 200
    assert "Mis alertas" in resp.data.decode()


def test_cambios_pestaña_alertas_muestra_busquedas(client, db):
    u = _usuario()
    guardar_busqueda(u.id, {"tipo": "regalo"})
    _login(client, "u1@test.es")
    resp = client.get("/cambios?tab=alertas")
    assert resp.status_code == 200
    assert "Regalos" in resp.data.decode()


def test_cambios_muestra_boton_guardar_con_filtro(client, db):
    _usuario()
    _login(client, "u1@test.es")
    resp = client.get("/cambios?tipo=regalo")
    assert resp.status_code == 200
    assert "Guardar búsqueda como alerta" in resp.data.decode()


def test_cambios_sin_filtro_no_muestra_boton_guardar(client, db):
    _usuario()
    _login(client, "u1@test.es")
    resp = client.get("/cambios")
    assert resp.status_code == 200
    assert "Guardar búsqueda como alerta" not in resp.data.decode()


def test_avisos_muestra_alerta_busqueda_guardada(client, db):
    u1 = _usuario()
    u2 = _usuario2()
    guardar_busqueda(u1.id, {"tipo": "regalo"})
    franja = _franja_id(u2)
    with patch("app.push.sender.webpush"):
        publicar_cambio(u2.id, [], [(date(2025, 7, 10), franja)], tipo="regalo")
    _login(client, "u1@test.es")
    resp = client.get("/avisos")
    assert resp.status_code == 200
    assert "Alerta" in resp.data.decode()


def test_avisos_alerta_enlaza_a_resultados_de_busqueda(client, db):
    """El aviso de alerta lleva a /cambios con los filtros de la búsqueda guardada."""
    u1 = _usuario()
    u2 = _usuario2()
    guardar_busqueda(u1.id, {"tipo": "regalo"})
    franja = _franja_id(u2)
    with patch("app.push.sender.webpush"):
        publicar_cambio(u2.id, [], [(date(2025, 7, 10), franja)], tipo="regalo")
    _login(client, "u1@test.es")
    resp = client.get("/avisos")
    body = resp.data.decode()
    assert "Ver resultados" in body
    assert "tipo=regalo" in body


def test_notif_busqueda_guardada_vincula_busqueda_al_crear(app, db):
    """La notificación creada por alerta lleva el busqueda_guardada_id correcto."""
    u1 = _usuario()
    u2 = _usuario2()
    busqueda = guardar_busqueda(u1.id, {"tipo": "regalo"})
    franja = _franja_id(u2)
    with app.app_context():
        with patch("app.push.sender.webpush"):
            publicar_cambio(u2.id, [], [(date(2025, 7, 10), franja)], tipo="regalo")
        notif = Notificacion.query.filter_by(
            usuario_id=u1.id, tipo="alerta_busqueda_guardada"
        ).first()
        assert notif is not None
        assert notif.busqueda_guardada_id == busqueda.id
