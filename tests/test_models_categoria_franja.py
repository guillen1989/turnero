import pytest
from datetime import time
from app.models import Categoria, FranjaHoraria, GrupoIntercambio, insertar_categorias_semilla
from app.models.categoria import CATEGORIAS_SEMILLA


def test_crear_categoria(db):
    cat = Categoria(nombre="Enfermería")
    db.session.add(cat)
    db.session.commit()

    assert db.session.get(Categoria, cat.id).nombre == "Enfermería"


def test_categoria_nombre_unico(db):
    db.session.add(Categoria(nombre="Médico/a"))
    db.session.commit()

    db.session.add(Categoria(nombre="Médico/a"))
    with pytest.raises(Exception):
        db.session.commit()


def test_seed_inserta_todas_las_categorias(db):
    insertar_categorias_semilla()
    total = Categoria.query.count()
    assert total == len(CATEGORIAS_SEMILLA)


def test_seed_es_idempotente(db):
    insertar_categorias_semilla()
    insertar_categorias_semilla()
    assert Categoria.query.count() == len(CATEGORIAS_SEMILLA)


def test_crear_franja_horaria(db):
    grupo = GrupoIntercambio()
    db.session.add(grupo)
    db.session.commit()

    franja = FranjaHoraria(
        nombre="Mañana",
        hora_inicio=time(7, 0),
        hora_fin=time(15, 0),
        grupo_intercambio=grupo,
    )
    db.session.add(franja)
    db.session.commit()

    recuperada = db.session.get(FranjaHoraria, franja.id)
    assert recuperada.nombre == "Mañana"
    assert recuperada.hora_inicio == time(7, 0)
    assert recuperada.grupo_intercambio.id == grupo.id


def test_franjas_horarias_unicas_por_grupo(db):
    grupo = GrupoIntercambio()
    db.session.add(grupo)
    db.session.commit()

    db.session.add(FranjaHoraria(nombre="Tarde", hora_inicio=time(15, 0), hora_fin=time(22, 0), grupo_intercambio=grupo))
    db.session.commit()

    db.session.add(FranjaHoraria(nombre="Tarde", hora_inicio=time(15, 0), hora_fin=time(22, 0), grupo_intercambio=grupo))
    with pytest.raises(Exception):
        db.session.commit()


def test_mismo_nombre_franja_en_grupos_distintos(db):
    """Dos grupos distintos pueden tener franjas con el mismo nombre."""
    grupo1 = GrupoIntercambio()
    grupo2 = GrupoIntercambio()
    db.session.add_all([grupo1, grupo2])
    db.session.commit()

    db.session.add(FranjaHoraria(nombre="Noche", hora_inicio=time(22, 0), hora_fin=time(7, 0), grupo_intercambio=grupo1))
    db.session.add(FranjaHoraria(nombre="Noche", hora_inicio=time(22, 0), hora_fin=time(7, 0), grupo_intercambio=grupo2))
    db.session.commit()

    assert FranjaHoraria.query.filter_by(nombre="Noche").count() == 2
