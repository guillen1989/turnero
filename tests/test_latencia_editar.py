"""Diagnóstico de latencia (docs/cambio.md, Paso 1): cuenta las queries SQL
ejecutadas al editar una publicación con varias candidatas activas, algunas
con turnos aceptados `cualquier_franja=True` (el caso que dispara
`_franjas_del_grupo` sin caché en `app/matching/service.py`)."""
from datetime import date

from app.extensions import db
from app.models import (
    Categoria, FranjaHoraria, PublicacionCambio, TurnoAceptado, TurnoCedido,
    insertar_categorias_semilla,
)
from app.services.registro import registrar_usuario


def _usuario_n(n):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario(f"U{n}", f"u{n}@test.es", "pass1234", "H1", "Urgencias", cat.id)


def _franja(grupo_id):
    return FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id).first()


def _login(client, email):
    client.post("/auth/login", data={"email": email, "password": "pass1234"})


def _candidata_cualquier_franja(usuario, franja, fecha_cede, fecha_acepta_cualquier):
    """Publicación activa tipo 'cambio' con un turno aceptado cualquier_franja=True,
    el caso que dispara `_franjas_del_grupo` dentro de `_aceptados()`."""
    pub = PublicacionCambio(usuario_id=usuario.id, unidad_id=usuario.unidad_id, tipo="cambio")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=fecha_cede, franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(
        publicacion_id=pub.id, fecha=fecha_acepta_cualquier,
        franja_horaria_id=None, cualquier_franja=True,
    ))
    db.session.commit()
    return pub


def _editar_y_contar(client, query_counter, pub_id, franja_id, fecha_cedida, fecha_aceptada):
    query_counter.selects = 0
    client.post(f"/publicaciones/{pub_id}/editar", data={
        "fecha_cedida_0": fecha_cedida.isoformat(),
        "franja_cedida_0": franja_id,
        "fecha_aceptada_0": fecha_aceptada.isoformat(),
        "franja_aceptada_0": franja_id,
    })
    return query_counter.selects


def test_editar_publicacion_selects_crecen_con_candidatas_cualquier_franja(client, db, query_counter):
    """Confirma la hipótesis de N+1 de docs/cambio.md: el número de SELECT
    ejecutados al editar una publicación crece con el número de candidatas
    activas que tienen un turno aceptado `cualquier_franja=True`, en vez de
    mantenerse constante (cada candidata dispara su propia llamada, sin
    caché, a `_franjas_del_grupo` dentro de las 6 búsquedas de matching)."""
    autor = _usuario_n(0)
    franja = _franja(autor.unidad.grupo_intercambio_id)
    pub = PublicacionCambio(usuario_id=autor.id, unidad_id=autor.unidad_id, tipo="cambio")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=date(2026, 9, 1), franja_horaria_id=franja.id))
    db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=date(2026, 9, 2), franja_horaria_id=franja.id))
    db.session.commit()

    _candidata_cualquier_franja(_usuario_n(1), franja, date(2026, 9, 3), date(2026, 9, 4))

    _login(client, autor.email)
    selects_con_1_candidata = _editar_y_contar(
        client, query_counter, pub.id, franja.id, date(2026, 9, 10), date(2026, 9, 11)
    )

    for n in range(2, 7):
        _candidata_cualquier_franja(_usuario_n(n), franja, date(2026, 9, 3), date(2026, 9, 4))

    selects_con_6_candidatas = _editar_y_contar(
        client, query_counter, pub.id, franja.id, date(2026, 9, 20), date(2026, 9, 21)
    )

    print(
        f"\n[Paso 1 — diagnóstico] SELECTs con 1 candidata: {selects_con_1_candidata}; "
        f"con 6 candidatas: {selects_con_6_candidatas}"
    )

    assert selects_con_6_candidatas > selects_con_1_candidata


def test_franjas_del_grupo_se_cachea_por_request(app, db, query_counter):
    """Paso 2 de docs/cambio.md: dos llamadas a `_franjas_del_grupo` con el
    mismo grupo dentro del mismo request (flask.g) solo deben ejecutar 1
    query, no una por llamada."""
    from app.matching.service import _franjas_del_grupo

    autor = _usuario_n(0)
    franja = _franja(autor.unidad.grupo_intercambio_id)
    pub = PublicacionCambio(usuario_id=autor.id, unidad_id=autor.unidad_id, tipo="cambio")
    db.session.add(pub)
    db.session.commit()

    with app.test_request_context():
        query_counter.selects = 0
        primera = _franjas_del_grupo(pub)
        selects_tras_primera = query_counter.selects
        segunda = _franjas_del_grupo(pub)
        selects_tras_segunda = query_counter.selects

    assert selects_tras_primera > 0
    assert selects_tras_segunda == selects_tras_primera
    assert primera == segunda
    assert franja.id in primera
