import pytest
from app.models import FeatureFlag


def test_crear_feature_flag(db):
    flag = FeatureFlag(clave="hoja_cambio_papel", descripcion="Registro en papel")
    db.session.add(flag)
    db.session.commit()

    recuperado = db.session.get(FeatureFlag, flag.id)
    assert recuperado.clave == "hoja_cambio_papel"
    assert recuperado.descripcion == "Registro en papel"


def test_activo_global_por_defecto_es_false(db):
    flag = FeatureFlag(clave="hoja_cambio_papel")
    db.session.add(flag)
    db.session.commit()

    recuperado = db.session.get(FeatureFlag, flag.id)
    assert recuperado.activo_global is False


def test_clave_es_unica(db):
    db.session.add(FeatureFlag(clave="hoja_cambio_papel"))
    db.session.commit()

    db.session.add(FeatureFlag(clave="hoja_cambio_papel"))
    with pytest.raises(Exception):
        db.session.commit()
