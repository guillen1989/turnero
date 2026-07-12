"""Tests E2E de editar un cambio ya publicado.

/editar reutiliza el mismo calendario tap-to-select que /publicar (ver
test_publicar.py), precargado con los turnos ya guardados de la publicación.
"""
from datetime import date, timedelta

from app.extensions import db as _db
from app.models import FranjaHoraria, PublicacionCambio, TurnoAceptado, TurnoCedido
from app.services.registro import crear_franjas_default


def _fecha(dias):
    return date.today() + timedelta(days=dias)


def _crear_publicacion(e2e_app, dias_cedido, dias_aceptado):
    with e2e_app.app_context():
        from app.models import Usuario
        u = Usuario.query.filter_by(email="ana@test.es").first()
        crear_franjas_default(u.unidad.grupo_intercambio)
        _db.session.commit()
        franja = FranjaHoraria.query.filter_by(
            grupo_intercambio_id=u.unidad.grupo_intercambio_id, nombre="Mañana"
        ).first()

        pub = PublicacionCambio(usuario_id=u.id)
        _db.session.add(pub)
        _db.session.flush()
        _db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=_fecha(dias_cedido), franja_horaria_id=franja.id))
        _db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=_fecha(dias_aceptado), franja_horaria_id=franja.id))
        _db.session.commit()
        return pub.id


def test_editar_muestra_turnos_existentes_precargados(e2e_app, pagina_autenticada, live_server):
    pub_id = _crear_publicacion(e2e_app, 7, 14)
    page = pagina_autenticada
    page.goto(f"{live_server}/publicaciones/{pub_id}/editar")

    assert page.locator('#cal-cedidos input[type="hidden"][name^="fecha_cedida_"]').count() == 1
    assert page.locator('#cal-aceptados input[type="hidden"][name^="fecha_aceptada_"]').count() == 1


def test_editar_permite_anadir_varios_dias_de_un_tap(e2e_app, pagina_autenticada, live_server):
    """Mismo motivo que en /publicar: añadir varios días del mismo turno sin
    filas manuales, también al editar una publicación ya existente."""
    pub_id = _crear_publicacion(e2e_app, 7, 14)
    page = pagina_autenticada
    page.goto(f"{live_server}/publicaciones/{pub_id}/editar")

    widget = page.locator("#cal-cedidos")
    widget.locator('.cal-turnos-chip[data-franja-nombre="Mañana"]').click()

    vista_inicial = _fecha(7)  # mes en el que arranca el widget: el del turno cedido ya existente
    for dias in (20, 21):
        fecha = _fecha(dias)
        meses_a_avanzar = (fecha.year - vista_inicial.year) * 12 + (fecha.month - vista_inicial.month)
        for _ in range(meses_a_avanzar):
            widget.locator('[data-role="next"]').click()
        widget.locator(f'button.cal-turnos-celda[data-fecha="{fecha.isoformat()}"]').click()
        vista_inicial = fecha

    assert widget.locator('input[type="hidden"][name^="fecha_cedida_"]').count() == 3

    page.locator('#editar-form button[type="submit"]').click()
    page.wait_for_url(f"{live_server}/")

    with e2e_app.app_context():
        pub = _db.session.get(PublicacionCambio, pub_id)
        assert len(pub.turnos_cedidos) == 3
