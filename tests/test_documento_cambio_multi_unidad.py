"""Paso 2 de FIX_MULTI: selector de unidad en la creacion de hoja de cambio."""
from datetime import date, time

from app.extensions import db
from app.models import (
    Categoria, DocumentoCambio, FranjaHoraria, GrupoIntercambio,
    Hospital, Unidad, Usuario, UsuarioUnidad,
)
from app.services.unidad_usuario import unidad_activa_o_403
from tests.helpers_documento_cambio import _login, _FIRMA_PNG


def _crear_usuario_dos_grupos(db):
    """Crea un usuario con 2 unidades en 2 grupos distintos, cada uno con
    sus propias franjas y companeros."""
    hospital = Hospital(nombre="Hospital General")
    db.session.add(hospital)
    db.session.commit()

    grupo_a = GrupoIntercambio()
    grupo_b = GrupoIntercambio()
    db.session.add_all([grupo_a, grupo_b])
    db.session.commit()

    unidad_a = Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo_a)
    unidad_b = Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo_b)
    cat = Categoria(nombre="Enfermeria")
    db.session.add_all([unidad_a, unidad_b, cat])
    db.session.commit()

    manyana_a = FranjaHoraria(
        nombre="Manana UCI", hora_inicio=time(8, 0), hora_fin=time(15, 0),
        grupo_intercambio=grupo_a,
    )
    tarde_a = FranjaHoraria(
        nombre="Tarde UCI", hora_inicio=time(15, 0), hora_fin=time(22, 0),
        grupo_intercambio=grupo_a,
    )
    manyana_b = FranjaHoraria(
        nombre="Manana URG", hora_inicio=time(8, 0), hora_fin=time(15, 0),
        grupo_intercambio=grupo_b,
    )
    tarde_b = FranjaHoraria(
        nombre="Tarde URG", hora_inicio=time(15, 0), hora_fin=time(22, 0),
        grupo_intercambio=grupo_b,
    )
    db.session.add_all([manyana_a, tarde_a, manyana_b, tarde_b])
    db.session.commit()

    usuario = Usuario(
        nombre="Ana Multi", email="multi@test.es",
        unidad=unidad_a, categoria=cat,
    )
    usuario.set_password("password123")
    db.session.add(usuario)
    db.session.commit()

    db.session.add(UsuarioUnidad(
        usuario_id=usuario.id, unidad_id=unidad_a.id, categoria_id=cat.id,
    ))
    db.session.add(UsuarioUnidad(
        usuario_id=usuario.id, unidad_id=unidad_b.id, categoria_id=cat.id,
    ))
    db.session.commit()

    companero_a = Usuario(
        nombre="Pedro UCI", email="pedroa@test.es",
        unidad=unidad_a, categoria=cat,
    )
    companero_a.set_password("password123")
    companero_b = Usuario(
        nombre="Pedro URG", email="pedrob@test.es",
        unidad=unidad_b, categoria=cat,
    )
    companero_b.set_password("password123")
    db.session.add_all([companero_a, companero_b])
    db.session.commit()

    return {
        "usuario": usuario,
        "unidad_a": unidad_a, "unidad_b": unidad_b,
        "grupo_a": grupo_a, "grupo_b": grupo_b,
        "manyana_a": manyana_a, "tarde_a": tarde_a,
        "manyana_b": manyana_b, "tarde_b": tarde_b,
        "companero_a": companero_a, "companero_b": companero_b,
    }


def test_nuevo_con_unidad_id_muestra_companeros_correctos(db, client):
    """GET /documentos-cambio/nuevo?unidad_id=X filtra companeros por grupo."""
    datos = _crear_usuario_dos_grupos(db)
    _login(client, datos["usuario"].email)

    resp_a = client.get(
        f"/documentos-cambio/nuevo?unidad_id={datos['unidad_a'].id}"
    )
    assert resp_a.status_code == 200
    html_a = resp_a.data.decode("utf-8")
    assert "Pedro UCI" in html_a
    assert "Pedro URG" not in html_a

    resp_b = client.get(
        f"/documentos-cambio/nuevo?unidad_id={datos['unidad_b'].id}"
    )
    assert resp_b.status_code == 200
    html_b = resp_b.data.decode("utf-8")
    assert "Pedro URG" in html_b
    assert "Pedro UCI" not in html_b


def test_nuevo_con_unidad_id_muestra_franjas_correctas(db, client):
    """GET /documentos-cambio/nuevo?unidad_id=X muestra franjas de ese grupo."""
    datos = _crear_usuario_dos_grupos(db)
    _login(client, datos["usuario"].email)

    resp_a = client.get(
        f"/documentos-cambio/nuevo?unidad_id={datos['unidad_a'].id}"
    )
    html_a = resp_a.data.decode("utf-8")
    assert "Manana UCI" in html_a
    assert "Tarde UCI" in html_a
    assert "Manana URG" not in html_a
    assert "Tarde URG" not in html_a

    resp_b = client.get(
        f"/documentos-cambio/nuevo?unidad_id={datos['unidad_b'].id}"
    )
    html_b = resp_b.data.decode("utf-8")
    assert "Manana URG" in html_b
    assert "Tarde URG" in html_b
    assert "Manana UCI" not in html_b
    assert "Tarde UCI" not in html_b


def test_nuevo_con_unidad_id_invalida_da_403(db, client):
    """GET /documentos-cambio/nuevo?unidad_id=999 devuelve 403."""
    datos = _crear_usuario_dos_grupos(db)
    _login(client, datos["usuario"].email)

    resp = client.get("/documentos-cambio/nuevo?unidad_id=99999")
    assert resp.status_code == 403


def test_nuevo_sin_unidad_id_usa_unidad_principal(db, client):
    """GET /documentos-cambio/nuevo sin unidad_id usa la unidad principal."""
    datos = _crear_usuario_dos_grupos(db)
    _login(client, datos["usuario"].email)

    resp = client.get("/documentos-cambio/nuevo")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Pedro UCI" in html
    assert "Pedro URG" not in html


def test_post_nuevo_crea_documento_en_unidad_correcta(db, client):
    """POST /documentos-cambio/nuevo asocia el DocumentoCambio a la unidad elegida."""
    datos = _crear_usuario_dos_grupos(db)
    usuario = datos["usuario"]
    _login(client, usuario.email)

    resp = client.post("/documentos-cambio/nuevo", data={
        "unidad_id": datos["unidad_b"].id,
        "companero_id": datos["companero_b"].id,
        "turno_cede_fecha": "2026-08-03",
        "turno_cede_franja_id": datos["manyana_b"].id,
        "turno_recibe_fecha": "2026-08-10",
        "turno_recibe_franja_id": datos["tarde_b"].id,
    })

    assert resp.status_code == 302
    documento_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])
    documento = db.session.get(DocumentoCambio, documento_id)
    assert documento.unidad_id == datos["unidad_b"].id


def test_post_nuevo_otra_unidad_sin_pertenencia_da_403(db, client):
    """POST con unidad_id a la que no pertenece el usuario da 403."""
    datos = _crear_usuario_dos_grupos(db)
    _login(client, datos["usuario"].email)

    otra_unidad = Unidad(
        nombre="UCI otro hospital",
        hospital=datos["unidad_a"].hospital,
        grupo_intercambio=datos["grupo_a"],
    )
    db.session.add(otra_unidad)
    db.session.commit()

    resp = client.post("/documentos-cambio/nuevo", data={
        "unidad_id": otra_unidad.id,
        "companero_id": datos["companero_a"].id,
        "turno_cede_fecha": "2026-08-03",
        "turno_cede_franja_id": datos["manyana_a"].id,
        "turno_recibe_fecha": "2026-08-10",
        "turno_recibe_franja_id": datos["tarde_a"].id,
    })
    assert resp.status_code == 403


def test_nuevo_selector_unidad_visible_solo_si_tiene_varias(db, client):
    """El selector de unidad aparece en la plantilla solo si unidades|length > 1."""
    datos = _crear_usuario_dos_grupos(db)
    _login(client, datos["usuario"].email)

    resp = client.get("/documentos-cambio/nuevo")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "id=\"hoja-select-unidad\"" in html
    assert datos["unidad_a"].nombre in html
    assert datos["unidad_b"].nombre in html

    # Usuario con una sola unidad: selector no deberia aparecer
    client.get("/auth/logout")
    usuario_simple = Usuario(
        nombre="Solo Uno", email="solo@test.es",
        unidad=datos["unidad_a"], categoria=datos["usuario"].categoria,
    )
    usuario_simple.set_password("password123")
    db.session.add(usuario_simple)
    db.session.commit()
    _login(client, "solo@test.es")

    resp = client.get("/documentos-cambio/nuevo")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "id=\"hoja-select-unidad\"" not in html


def test_turnos_disponibles_filtra_por_unidad(db, client):
    """El endpoint turnos-disponibles filtra por la unidad activa."""
    from app.services.planilla import añadir_turno

    datos = _crear_usuario_dos_grupos(db)
    usuario = datos["usuario"]
    _login(client, usuario.email)

    añadir_turno(datos["companero_a"], date(2026, 8, 3), datos["manyana_a"].id)
    añadir_turno(datos["companero_b"], date(2026, 8, 3), datos["manyana_b"].id)

    # Con unidad_a activa, solo ve turnos del companero_a
    resp_a = client.get(
        "/documentos-cambio/api/turnos-disponibles"
        f"?usuario_id={datos['companero_a'].id}&fecha=2026-08-03"
        f"&unidad_id={datos['unidad_a'].id}"
    )
    assert resp_a.status_code == 200
    assert resp_a.json == [{"id": datos["manyana_a"].id, "nombre": "Manana UCI"}]

    # El companero_b no deberia aparecer porque pertenece a otro grupo
    resp_b = client.get(
        "/documentos-cambio/api/turnos-disponibles"
        f"?usuario_id={datos['companero_b'].id}&fecha=2026-08-03"
        f"&unidad_id={datos['unidad_a'].id}"
    )
    assert resp_b.status_code == 200
    assert resp_b.json == []

    # Pero con unidad_b activa, si deberia aparecer
    resp_b2 = client.get(
        "/documentos-cambio/api/turnos-disponibles"
        f"?usuario_id={datos['companero_b'].id}&fecha=2026-08-03"
        f"&unidad_id={datos['unidad_b'].id}"
    )
    assert resp_b2.status_code == 200
    assert resp_b2.json == [{"id": datos["manyana_b"].id, "nombre": "Manana URG"}]