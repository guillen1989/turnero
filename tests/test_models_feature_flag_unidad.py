import pytest
from app.models import FeatureFlag, FeatureFlagUnidad, Hospital, GrupoIntercambio, Unidad


def _crear_contexto(db):
    hospital = Hospital(nombre="Hospital Test")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    unidad1 = Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo)
    unidad2 = Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo)
    flag = FeatureFlag(clave="hoja_cambio_papel")
    db.session.add_all([unidad1, unidad2, flag])
    db.session.commit()

    return flag, unidad1, unidad2


def test_feature_flag_unidades_habilitadas(db):
    flag, unidad1, unidad2 = _crear_contexto(db)

    flag.unidades_habilitadas.append(unidad1)
    flag.unidades_habilitadas.append(unidad2)
    db.session.commit()

    recuperado = db.session.get(FeatureFlag, flag.id)
    nombres = {u.nombre for u in recuperado.unidades_habilitadas}
    assert nombres == {"Urgencias", "UCI"}


def test_unidad_feature_flags_habilitados_backref(db):
    flag, unidad1, unidad2 = _crear_contexto(db)

    flag.unidades_habilitadas.append(unidad1)
    db.session.commit()

    recuperada = db.session.get(Unidad, unidad1.id)
    assert [f.id for f in recuperada.feature_flags_habilitados] == [flag.id]

    recuperada2 = db.session.get(Unidad, unidad2.id)
    assert recuperada2.feature_flags_habilitados == []


def test_no_permite_asociacion_duplicada(db):
    flag, unidad1, _ = _crear_contexto(db)

    db.session.add(FeatureFlagUnidad(feature_flag_id=flag.id, unidad_id=unidad1.id))
    db.session.commit()

    db.session.add(FeatureFlagUnidad(feature_flag_id=flag.id, unidad_id=unidad1.id))
    with pytest.raises(Exception):
        db.session.commit()
