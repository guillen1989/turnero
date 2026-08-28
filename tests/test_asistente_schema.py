import pytest
from pydantic import ValidationError

from app.services.asistente.schema import PropuestaPublicacion


def _propuesta_valida(**overrides):
    base = dict(
        tipo="cambio",
        cedidos=[{"fecha": "2026-08-14", "franja": "Noche"}],
        aceptados=[{"fecha": "2026-08-17", "franja": None}],
        campos_faltantes=[],
    )
    base.update(overrides)
    return base


def test_acepta_una_propuesta_correcta():
    propuesta = PropuestaPublicacion(**_propuesta_valida())

    assert propuesta.tipo == "cambio"
    assert propuesta.cedidos[0].fecha == "2026-08-14"
    assert propuesta.cedidos[0].franja == "Noche"


def test_rechaza_tipo_fuera_de_tipos_publicacion():
    with pytest.raises(ValidationError):
        PropuestaPublicacion(**_propuesta_valida(tipo="invento"))


def test_rechaza_fecha_con_formato_invalido():
    with pytest.raises(ValidationError):
        PropuestaPublicacion(**_propuesta_valida(
            cedidos=[{"fecha": "14/08/2026", "franja": "Noche"}]
        ))


def test_acepta_franja_null_en_aceptados_como_cualquier_franja():
    propuesta = PropuestaPublicacion(**_propuesta_valida(
        aceptados=[{"fecha": "2026-08-17", "franja": None}]
    ))

    assert propuesta.aceptados[0].franja is None


def test_campos_faltantes_por_defecto_vacio():
    propuesta = PropuestaPublicacion(**_propuesta_valida(campos_faltantes=[]))

    assert propuesta.campos_faltantes == []


def test_acepta_fecha_null_cuando_el_modelo_no_la_conoce():
    propuesta = PropuestaPublicacion(**_propuesta_valida(
        cedidos=[{"fecha": None, "franja": None}]
    ))

    assert propuesta.cedidos[0].fecha is None
