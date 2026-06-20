import pytest
from app.models import Hospital, GrupoIntercambio, Unidad
from app.extensions import db


def test_crear_hospital(db):
    hospital = Hospital(nombre="Hospital La Paz")
    db.session.add(hospital)
    db.session.commit()

    recuperado = db.session.get(Hospital, hospital.id)
    assert recuperado.nombre == "Hospital La Paz"


def test_hospital_nombre_unico(db):
    db.session.add(Hospital(nombre="Hospital Valle Verde"))
    db.session.commit()

    db.session.add(Hospital(nombre="Hospital Valle Verde"))
    with pytest.raises(Exception):
        db.session.commit()


def test_crear_grupo_intercambio(db):
    grupo = GrupoIntercambio()
    db.session.add(grupo)
    db.session.commit()

    assert grupo.id is not None


def test_crear_unidad_con_grupo_propio(db):
    """Una unidad sin compañeras de intercambio forma un grupo de uno."""
    hospital = Hospital(nombre="Hospital del Mar")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    unidad = Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo)
    db.session.add(unidad)
    db.session.commit()

    assert unidad.id is not None
    assert unidad.hospital.nombre == "Hospital del Mar"
    assert unidad.grupo_intercambio.id == grupo.id


def test_unidades_en_mismo_grupo_de_intercambio(db):
    """Varias unidades pueden compartir el mismo grupo de intercambio."""
    hospital = Hospital(nombre="Hospital General")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    trauma1 = Unidad(nombre="Traumatología 1", hospital=hospital, grupo_intercambio=grupo)
    trauma2 = Unidad(nombre="Traumatología 2", hospital=hospital, grupo_intercambio=grupo)
    db.session.add_all([trauma1, trauma2])
    db.session.commit()

    unidades_del_grupo = list(grupo.unidades)
    assert len(unidades_del_grupo) == 2
    nombres = {u.nombre for u in unidades_del_grupo}
    assert nombres == {"Traumatología 1", "Traumatología 2"}


def test_unidad_nombre_unico_por_hospital(db):
    """No puede haber dos unidades con el mismo nombre en el mismo hospital."""
    hospital = Hospital(nombre="Hospital Norte")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    db.session.add(Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo))
    db.session.commit()

    db.session.add(Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo))
    with pytest.raises(Exception):
        db.session.commit()
