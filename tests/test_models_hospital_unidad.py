import pytest
from app.models import Pais, Provincia, Ciudad, Hospital, GrupoIntercambio, Unidad
from app.extensions import db


def test_crear_hospital(db):
    hospital = Hospital(nombre="Hospital La Paz")
    db.session.add(hospital)
    db.session.commit()

    recuperado = db.session.get(Hospital, hospital.id)
    assert recuperado.nombre == "Hospital La Paz"


def test_hospital_nombre_unico_por_ciudad(db):
    """Mismo nombre de hospital en la misma ciudad no puede existir dos veces."""
    pais = Pais(nombre="España Test")
    prov = Provincia(nombre="Madrid Test", pais=pais)
    ciudad = Ciudad(nombre="Madrid Capital", provincia=prov)
    db.session.add_all([pais, prov, ciudad])
    db.session.commit()

    db.session.add(Hospital(nombre="Hospital Valle Verde", ciudad=ciudad))
    db.session.commit()

    db.session.add(Hospital(nombre="Hospital Valle Verde", ciudad=ciudad))
    with pytest.raises(Exception):
        db.session.commit()


def test_hospital_mismo_nombre_diferente_ciudad_es_valido(db):
    """El mismo nombre de hospital puede existir en ciudades distintas."""
    pais = Pais(nombre="España B")
    prov = Provincia(nombre="Castilla B", pais=pais)
    ciudad1 = Ciudad(nombre="Toledo", provincia=prov)
    ciudad2 = Ciudad(nombre="Cuenca", provincia=prov)
    db.session.add_all([pais, prov, ciudad1, ciudad2])
    db.session.commit()

    db.session.add(Hospital(nombre="Hospital General", ciudad=ciudad1))
    db.session.add(Hospital(nombre="Hospital General", ciudad=ciudad2))
    db.session.commit()
    assert Hospital.query.filter_by(nombre="Hospital General").count() == 2


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


def test_unidad_nombre_unico_por_hospital_y_categoria(db):
    """Misma unidad (nombre + hospital + categoría) no puede existir dos veces."""
    from app.models import Categoria
    hospital = Hospital(nombre="Hospital Norte")
    grupo1 = GrupoIntercambio()
    grupo2 = GrupoIntercambio()
    cat = Categoria(nombre="Enfermería Test Uniq")
    db.session.add_all([hospital, grupo1, grupo2, cat])
    db.session.commit()

    db.session.add(Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo1, categoria=cat))
    db.session.commit()

    db.session.add(Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo2, categoria=cat))
    with pytest.raises(Exception):
        db.session.commit()


def test_unidad_mismo_nombre_diferente_categoria_es_valido(db):
    """La misma unidad puede existir para distintas categorías en el mismo hospital."""
    from app.models import Categoria
    hospital = Hospital(nombre="Hospital Sur")
    grupo1 = GrupoIntercambio()
    grupo2 = GrupoIntercambio()
    cat1 = Categoria(nombre="Médico Test")
    cat2 = Categoria(nombre="Enfermería Test")
    db.session.add_all([hospital, grupo1, grupo2, cat1, cat2])
    db.session.commit()

    db.session.add(Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo1, categoria=cat1))
    db.session.add(Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo2, categoria=cat2))
    db.session.commit()
    assert Unidad.query.filter_by(nombre="UCI").count() == 2
