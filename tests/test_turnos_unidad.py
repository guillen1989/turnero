"""Tests para la gestión de turnos de unidad (configuración de franjas horarias)."""
from datetime import date, time

import pytest

from app.extensions import db
from app.models import (
    Categoria, FranjaHoraria, PublicacionCambio, TurnoCedido, TurnoAceptado,
    insertar_categorias_semilla,
)
from app.services.registro import registrar_usuario


def _usuario_y_login(client, email="test@test.es", unidad="Urgencias", hospital="Hospital T"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    usuario = registrar_usuario("Test User", email, "password123", hospital, unidad, cat.id)
    client.post("/auth/login", data={"email": email, "password": "password123"})
    return usuario


# ---------------------------------------------------------------------------
# Acceso a la página
# ---------------------------------------------------------------------------

def test_turnos_page_requiere_login(client, db):
    resp = client.get("/unidad/turnos", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.location


def test_turnos_page_visible_y_muestra_franjas(client, db):
    usuario = _usuario_y_login(client)
    resp = client.get("/unidad/turnos")
    assert resp.status_code == 200
    assert "Mañana".encode() in resp.data or b"Turnos" in resp.data


def test_turnos_page_muestra_nombre_unidad(client, db):
    usuario = _usuario_y_login(client)
    resp = client.get("/unidad/turnos")
    assert b"Urgencias" in resp.data


# ---------------------------------------------------------------------------
# Aplicar plantillas
# ---------------------------------------------------------------------------

def test_aplicar_plantilla_tres_turnos_crea_franjas_correctas(client, db):
    usuario = _usuario_y_login(client)
    grupo = usuario.unidad.grupo_intercambio
    resp = client.post(
        "/unidad/turnos/plantilla",
        data={"plantilla_id": "tres_turnos"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    nombres = {f.nombre for f in FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo.id).all()}
    assert {"Mañana", "Tarde", "Noche"}.issubset(nombres)


def test_aplicar_plantilla_tres_turnos_actualiza_horas(client, db):
    usuario = _usuario_y_login(client)
    grupo = usuario.unidad.grupo_intercambio
    client.post("/unidad/turnos/plantilla", data={"plantilla_id": "tres_turnos"}, follow_redirects=True)
    manana = FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo.id, nombre="Mañana").first()
    assert manana is not None
    assert manana.hora_inicio == time(8, 0)
    assert manana.hora_fin == time(15, 0)


def test_aplicar_plantilla_doce_horas_crea_franjas_correctas(client, db):
    usuario = _usuario_y_login(client)
    grupo = usuario.unidad.grupo_intercambio
    resp = client.post(
        "/unidad/turnos/plantilla",
        data={"plantilla_id": "doce_horas"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    nombres = {f.nombre for f in FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo.id).all()}
    assert {"Diurno", "Nocturno"}.issubset(nombres)


def test_aplicar_plantilla_mixto_crea_cinco_franjas(client, db):
    usuario = _usuario_y_login(client)
    grupo = usuario.unidad.grupo_intercambio
    client.post("/unidad/turnos/plantilla", data={"plantilla_id": "mixto"}, follow_redirects=True)
    nombres = {f.nombre for f in FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo.id).all()}
    assert {"Mañana", "Tarde", "Noche", "Diurno", "Nocturno"}.issubset(nombres)


def test_aplicar_plantilla_elimina_franjas_sin_uso(client, db):
    usuario = _usuario_y_login(client)
    grupo = usuario.unidad.grupo_intercambio
    # Añadir una franja que no pertenece a la plantilla y sin publicaciones
    franja_extra = FranjaHoraria(
        nombre="Turno especial", hora_inicio=time(6, 0), hora_fin=time(14, 0),
        grupo_intercambio_id=grupo.id,
    )
    db.session.add(franja_extra)
    db.session.commit()

    client.post("/unidad/turnos/plantilla", data={"plantilla_id": "tres_turnos"}, follow_redirects=True)

    assert FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo.id, nombre="Turno especial").first() is None


def test_aplicar_plantilla_mantiene_franjas_en_uso(client, db):
    usuario = _usuario_y_login(client)
    grupo = usuario.unidad.grupo_intercambio

    # Crear una franja especial referenciada por una publicación
    franja_especial = FranjaHoraria(
        nombre="Guardia médica", hora_inicio=time(15, 0), hora_fin=time(8, 0),
        grupo_intercambio_id=grupo.id,
    )
    db.session.add(franja_especial)
    db.session.flush()

    pub = PublicacionCambio(usuario_id=usuario.id)
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=date(2026, 9, 1), franja_horaria_id=franja_especial.id))
    db.session.commit()

    # Aplicar plantilla que NO incluye "Guardia médica"
    client.post("/unidad/turnos/plantilla", data={"plantilla_id": "tres_turnos"}, follow_redirects=True)

    # La franja con publicación asociada debe mantenerse
    assert FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo.id, nombre="Guardia médica").first() is not None


def test_aplicar_plantilla_invalida_muestra_error(client, db):
    _usuario_y_login(client)
    resp = client.post(
        "/unidad/turnos/plantilla",
        data={"plantilla_id": "plantilla_inventada"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"error" in resp.data.lower() or "no válida".encode() in resp.data


# ---------------------------------------------------------------------------
# Añadir turno personalizado
# ---------------------------------------------------------------------------

def test_agregar_franja_personalizada(client, db):
    usuario = _usuario_y_login(client)
    grupo = usuario.unidad.grupo_intercambio
    resp = client.post(
        "/unidad/turnos",
        data={"nombre": "Guardia", "hora_inicio": "08:00", "hora_fin": "20:00"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    franja = FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo.id, nombre="Guardia").first()
    assert franja is not None
    assert franja.hora_inicio == time(8, 0)
    assert franja.hora_fin == time(20, 0)


def test_agregar_franja_nombre_vacio_muestra_error(client, db):
    usuario = _usuario_y_login(client)
    grupo = usuario.unidad.grupo_intercambio
    count_antes = FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo.id).count()
    resp = client.post(
        "/unidad/turnos",
        data={"nombre": "", "hora_inicio": "08:00", "hora_fin": "20:00"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo.id).count() == count_antes


def test_agregar_franja_duplicada_muestra_error(client, db):
    usuario = _usuario_y_login(client)
    grupo = usuario.unidad.grupo_intercambio
    client.post("/unidad/turnos", data={"nombre": "Guardia", "hora_inicio": "08:00", "hora_fin": "20:00"})
    resp = client.post(
        "/unidad/turnos",
        data={"nombre": "Guardia", "hora_inicio": "09:00", "hora_fin": "21:00"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo.id, nombre="Guardia").count() == 1


def test_agregar_franja_hora_invalida_muestra_error(client, db):
    usuario = _usuario_y_login(client)
    grupo = usuario.unidad.grupo_intercambio
    count_antes = FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo.id).count()
    resp = client.post(
        "/unidad/turnos",
        data={"nombre": "Guardia", "hora_inicio": "no-es-hora", "hora_fin": "20:00"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo.id).count() == count_antes


# ---------------------------------------------------------------------------
# Eliminar franja
# ---------------------------------------------------------------------------

def test_eliminar_franja_sin_uso(client, db):
    usuario = _usuario_y_login(client)
    grupo = usuario.unidad.grupo_intercambio
    franja = FranjaHoraria(
        nombre="Temporal", hora_inicio=time(9, 0), hora_fin=time(13, 0),
        grupo_intercambio_id=grupo.id,
    )
    db.session.add(franja)
    db.session.commit()
    franja_id = franja.id

    resp = client.post(f"/unidad/turnos/{franja_id}/eliminar", follow_redirects=True)
    assert resp.status_code == 200
    assert db.session.get(FranjaHoraria, franja_id) is None


def test_eliminar_franja_en_uso_da_error(client, db):
    usuario = _usuario_y_login(client)
    grupo = usuario.unidad.grupo_intercambio
    franja = FranjaHoraria(
        nombre="En uso", hora_inicio=time(8, 0), hora_fin=time(20, 0),
        grupo_intercambio_id=grupo.id,
    )
    db.session.add(franja)
    db.session.flush()
    pub = PublicacionCambio(usuario_id=usuario.id)
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id))
    db.session.commit()
    franja_id = franja.id

    resp = client.post(f"/unidad/turnos/{franja_id}/eliminar", follow_redirects=True)
    assert resp.status_code == 200
    assert db.session.get(FranjaHoraria, franja_id) is not None  # debe seguir existiendo


def test_eliminar_franja_de_otra_unidad_da_404(client, db):
    """Un usuario no puede eliminar franjas de otro grupo."""
    usuario = _usuario_y_login(client)
    # Crear franja de otro grupo
    from app.models import GrupoIntercambio
    otro_grupo = GrupoIntercambio()
    db.session.add(otro_grupo)
    db.session.flush()
    franja_ajena = FranjaHoraria(
        nombre="Ajena", hora_inicio=time(8, 0), hora_fin=time(15, 0),
        grupo_intercambio_id=otro_grupo.id,
    )
    db.session.add(franja_ajena)
    db.session.commit()

    resp = client.post(f"/unidad/turnos/{franja_ajena.id}/eliminar", follow_redirects=True)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Flujo de registro con unidad nueva → redirección
# ---------------------------------------------------------------------------

def test_registro_nueva_unidad_redirige_a_configurar_turnos(client, db):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    resp = client.post(
        "/auth/registro",
        data={
            "nombre": "Test User",
            "email": "nuevo@test.es",
            "password": "password123",
            "password2": "password123",
            "hospital_id": "0",
            "hospital_nuevo": "Hospital Nuevo",
            "unidad_id": "0",
            "unidad_nuevo": "Urgencias Nueva",
            "categoria_id": str(cat.id),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/unidad/turnos" in resp.location


def test_registro_unidad_existente_no_redirige_a_turnos(client, db):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    # Primera persona crea la unidad
    registrar_usuario("Ana", "ana@test.es", "password123", "Hospital X", "Urgencias X", cat.id)

    # Segunda persona se une a la misma unidad
    resp = client.post(
        "/auth/registro",
        data={
            "nombre": "Pedro",
            "email": "pedro@test.es",
            "password": "password123",
            "password2": "password123",
            "hospital_id": "0",
            "hospital_nuevo": "Hospital X",
            "unidad_id": "0",
            "unidad_nuevo": "Urgencias X",
            "categoria_id": str(cat.id),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/unidad/turnos" not in resp.location
