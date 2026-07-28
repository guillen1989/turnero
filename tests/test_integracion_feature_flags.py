import pytest
from flask import render_template_string
from werkzeug.exceptions import NotFound

from app.services.feature_flags import requiere_feature, crear_flag, activar_global


def test_requiere_feature_da_404_si_el_flag_esta_inactivo(app, db):
    @requiere_feature("hoja_cambio_papel")
    def vista():
        return "ok"

    crear_flag("hoja_cambio_papel")

    with app.test_request_context():
        with pytest.raises(NotFound):
            vista()


def test_requiere_feature_deja_pasar_si_el_flag_esta_activo(app, db):
    @requiere_feature("hoja_cambio_papel")
    def vista():
        return "ok"

    crear_flag("hoja_cambio_papel")
    activar_global("hoja_cambio_papel")

    with app.test_request_context():
        assert vista() == "ok"


def test_requiere_feature_da_404_si_el_flag_no_existe(app, db):
    @requiere_feature("no_registrado")
    def vista():
        return "ok"

    with app.test_request_context():
        with pytest.raises(NotFound):
            vista()


def test_feature_activa_disponible_en_plantillas_flag_activo(app, db):
    crear_flag("hoja_cambio_papel")
    activar_global("hoja_cambio_papel")

    with app.test_request_context():
        resultado = render_template_string(
            "{% if feature_activa('hoja_cambio_papel') %}<a href='#'>enlace</a>{% endif %}"
        )
        assert "<a href='#'>enlace</a>" in resultado


def test_feature_activa_oculta_enlace_en_plantillas_flag_inactivo(app, db):
    crear_flag("hoja_cambio_papel")

    with app.test_request_context():
        resultado = render_template_string(
            "{% if feature_activa('hoja_cambio_papel') %}<a href='#'>enlace</a>{% endif %}"
        )
        assert "<a href='#'>enlace</a>" not in resultado
