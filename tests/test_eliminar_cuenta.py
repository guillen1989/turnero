"""Tests para la funcionalidad de eliminar cuenta (anonimización)."""
from datetime import date

from app.extensions import db as _db
from app.models import (
    Categoria,
    FranjaHoraria,
    MatchCambio,
    MatchParticipacion,
    PublicacionCambio,
    SuscripcionPublicaciones,
    TurnoCedido,
    TurnoAceptado,
    insertar_categorias_semilla,
)
from app.models.busqueda_guardada import BusquedaGuardada
from app.services.registro import eliminar_cuenta, registrar_usuario


def _crear_usuario(nombre, email, db):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario(nombre, email, "password123", "H1", "Urgencias", cat.id)


def _franja(usuario):
    return FranjaHoraria.query.filter_by(
        grupo_intercambio_id=usuario.unidad.grupo_intercambio_id, nombre="Mañana"
    ).first()


def _crear_match_entre(ana, pedro, estado="propuesto"):
    franja = _franja(ana)

    pub_ana = PublicacionCambio(usuario_id=ana.id)
    _db.session.add(pub_ana)
    _db.session.flush()
    tc_ana = TurnoCedido(publicacion_id=pub_ana.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id)
    _db.session.add(tc_ana)
    _db.session.add(TurnoAceptado(publicacion_id=pub_ana.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id))

    pub_pedro = PublicacionCambio(usuario_id=pedro.id)
    _db.session.add(pub_pedro)
    _db.session.flush()
    tc_pedro = TurnoCedido(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id)
    _db.session.add(tc_pedro)
    _db.session.add(TurnoAceptado(publicacion_id=pub_pedro.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id))

    match = MatchCambio(tipo="directo_2", estado=estado)
    _db.session.add(match)
    _db.session.flush()
    _db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_ana.id, turno_cedido_id=tc_ana.id))
    _db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_pedro.id, turno_cedido_id=tc_pedro.id))
    _db.session.commit()
    return match


# --- Servicio puro ---

def test_eliminar_cuenta_anonimiza_nombre_y_email(db):
    ana = _crear_usuario("Ana García", "ana@test.es", db)
    eliminar_cuenta(ana)
    assert ana.nombre == "Usuario eliminado"
    assert ana.email.startswith("eliminado_")
    assert ana.email.endswith("@eliminado.invalid")


def test_eliminar_cuenta_bloquea_login(db):
    ana = _crear_usuario("Ana García", "ana@test.es", db)
    eliminar_cuenta(ana)
    assert not ana.check_password("password123")


def test_eliminar_cuenta_cancela_publicaciones_activas(db):
    ana = _crear_usuario("Ana García", "ana@test.es", db)
    franja = _franja(ana)
    pub = PublicacionCambio(usuario_id=ana.id)
    _db.session.add(pub)
    _db.session.flush()
    _db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id))
    _db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id))
    _db.session.commit()

    eliminar_cuenta(ana)

    _db.session.refresh(pub)
    assert pub.estado == "cancelada"


def test_eliminar_cuenta_rechaza_matches_propuestos(db):
    ana = _crear_usuario("Ana García", "ana@test.es", db)
    pedro = _crear_usuario("Pedro", "pedro@test.es", db)
    match = _crear_match_entre(ana, pedro, estado="propuesto")

    eliminar_cuenta(ana)

    _db.session.refresh(match)
    assert match.estado == "rechazado"


def test_eliminar_cuenta_rechaza_matches_confirmados_parcialmente(db):
    ana = _crear_usuario("Ana García", "ana@test.es", db)
    pedro = _crear_usuario("Pedro", "pedro@test.es", db)
    match = _crear_match_entre(ana, pedro, estado="confirmado_parcial")

    eliminar_cuenta(ana)

    _db.session.refresh(match)
    assert match.estado == "rechazado"


def test_eliminar_cuenta_no_toca_matches_ya_cerrados(db):
    ana = _crear_usuario("Ana García", "ana@test.es", db)
    pedro = _crear_usuario("Pedro", "pedro@test.es", db)
    match = _crear_match_entre(ana, pedro, estado="confirmado_total")

    eliminar_cuenta(ana)

    _db.session.refresh(match)
    assert match.estado == "confirmado_total"


def test_eliminar_cuenta_borra_busquedas_guardadas(db):
    ana = _crear_usuario("Ana García", "ana@test.es", db)
    _db.session.add(BusquedaGuardada(usuario_id=ana.id, filtros={}))
    _db.session.commit()

    eliminar_cuenta(ana)

    assert BusquedaGuardada.query.filter_by(usuario_id=ana.id).count() == 0


def test_eliminar_cuenta_borra_suscripciones_como_suscriptor(db):
    ana = _crear_usuario("Ana García", "ana@test.es", db)
    pedro = _crear_usuario("Pedro", "pedro@test.es", db)
    _db.session.add(SuscripcionPublicaciones(suscriptor_id=ana.id, publicador_id=pedro.id))
    _db.session.commit()

    eliminar_cuenta(ana)

    assert SuscripcionPublicaciones.query.filter_by(suscriptor_id=ana.id).count() == 0


def test_eliminar_cuenta_borra_suscripciones_como_publicador(db):
    ana = _crear_usuario("Ana García", "ana@test.es", db)
    pedro = _crear_usuario("Pedro", "pedro@test.es", db)
    _db.session.add(SuscripcionPublicaciones(suscriptor_id=pedro.id, publicador_id=ana.id))
    _db.session.commit()

    eliminar_cuenta(ana)

    assert SuscripcionPublicaciones.query.filter_by(publicador_id=ana.id).count() == 0


# --- Ruta HTTP ---

def _login(client, email, password="password123"):
    return client.post("/auth/login", data={"email": email, "password": password})


def test_ruta_eliminar_requiere_autenticacion(client, db):
    resp = client.post(
        "/auth/perfil/cuenta/eliminar",
        data={"password": "password123"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_ruta_eliminar_password_incorrecta_muestra_error(client, db):
    _crear_usuario("Ana García", "ana@test.es", db)
    _login(client, "ana@test.es")

    resp = client.post(
        "/auth/perfil/cuenta/eliminar",
        data={"password": "wrongpassword"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "incorrecta" in resp.data.decode("utf-8").lower()


def test_ruta_eliminar_exitoso_cierra_sesion_y_redirige(client, db):
    _crear_usuario("Ana García", "ana@test.es", db)
    _login(client, "ana@test.es")

    resp = client.post(
        "/auth/perfil/cuenta/eliminar",
        data={"password": "password123"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_cuenta_eliminada_no_puede_hacer_login(client, db):
    ana = _crear_usuario("Ana García", "ana@test.es", db)
    eliminar_cuenta(ana)

    _login(client, "ana@test.es")
    # A protected route must redirect to login if the user is not authenticated.
    resp = client.get("/auth/perfil", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
