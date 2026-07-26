import pytest
from app.models import Usuario, Hospital, GrupoIntercambio, Unidad, Categoria, UnidadSupervisada


def _crear_contexto(db):
    hospital = Hospital(nombre="Hospital Test")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    unidad1 = Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo)
    unidad2 = Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo)
    categoria = Categoria(nombre="Enfermería")
    db.session.add_all([unidad1, unidad2, categoria])
    db.session.commit()

    usuario = Usuario(
        nombre="Ana García", email="ana@hospital.es", unidad=unidad1, categoria=categoria, es_supervisora=True
    )
    usuario.set_password("pass")
    db.session.add(usuario)
    db.session.commit()

    return usuario, unidad1, unidad2


def test_usuario_unidades_supervisadas(db):
    usuario, unidad1, unidad2 = _crear_contexto(db)

    usuario.unidades_supervisadas.append(unidad1)
    usuario.unidades_supervisadas.append(unidad2)
    db.session.commit()

    recuperado = db.session.get(Usuario, usuario.id)
    nombres = {u.nombre for u in recuperado.unidades_supervisadas}
    assert nombres == {"Urgencias", "UCI"}


def test_unidad_supervisoras_backref(db):
    usuario, unidad1, unidad2 = _crear_contexto(db)

    usuario.unidades_supervisadas.append(unidad1)
    db.session.commit()

    recuperada = db.session.get(Unidad, unidad1.id)
    assert [s.id for s in recuperada.supervisoras] == [usuario.id]

    recuperada2 = db.session.get(Unidad, unidad2.id)
    assert recuperada2.supervisoras == []


def test_no_permite_asociacion_duplicada(db):
    usuario, unidad1, _ = _crear_contexto(db)

    db.session.add(UnidadSupervisada(usuario_id=usuario.id, unidad_id=unidad1.id))
    db.session.commit()

    db.session.add(UnidadSupervisada(usuario_id=usuario.id, unidad_id=unidad1.id))
    with pytest.raises(Exception):
        db.session.commit()
