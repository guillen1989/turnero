from app.models import FeatureFlag, Hospital, GrupoIntercambio, Unidad
from app.services.feature_flags import (
    feature_activa,
    crear_flag,
    activar_global,
    desactivar_global,
    habilitar_para_unidad,
    deshabilitar_para_unidad,
)


def _crear_unidad(db):
    hospital = Hospital(nombre="Hospital Test")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    unidad = Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo)
    db.session.add(unidad)
    db.session.commit()
    return unidad


def test_feature_activa_false_si_el_flag_no_existe(db):
    assert feature_activa("no_registrado") is False


def test_crear_flag(db):
    flag = crear_flag("hoja_cambio_papel", "Registro en papel")

    recuperado = db.session.get(FeatureFlag, flag.id)
    assert recuperado.clave == "hoja_cambio_papel"
    assert recuperado.descripcion == "Registro en papel"
    assert recuperado.activo_global is False


def test_activar_global_hace_feature_activa_true(db):
    crear_flag("hoja_cambio_papel")

    activar_global("hoja_cambio_papel")

    assert feature_activa("hoja_cambio_papel") is True


def test_desactivar_global(db):
    crear_flag("hoja_cambio_papel")
    activar_global("hoja_cambio_papel")

    desactivar_global("hoja_cambio_papel")

    assert feature_activa("hoja_cambio_papel") is False


def test_activo_global_gana_aunque_la_unidad_no_este_en_la_lista(db):
    unidad = _crear_unidad(db)
    crear_flag("hoja_cambio_papel")
    activar_global("hoja_cambio_papel")

    assert feature_activa("hoja_cambio_papel", unidad) is True


def test_unidad_en_la_lista_gana_aunque_activo_global_sea_false(db):
    unidad = _crear_unidad(db)
    crear_flag("hoja_cambio_papel")

    habilitar_para_unidad("hoja_cambio_papel", unidad)

    assert feature_activa("hoja_cambio_papel", unidad) is True
    assert feature_activa("hoja_cambio_papel") is False


def test_deshabilitar_para_unidad(db):
    unidad = _crear_unidad(db)
    crear_flag("hoja_cambio_papel")
    habilitar_para_unidad("hoja_cambio_papel", unidad)

    deshabilitar_para_unidad("hoja_cambio_papel", unidad)

    assert feature_activa("hoja_cambio_papel", unidad) is False
