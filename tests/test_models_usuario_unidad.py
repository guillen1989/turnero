import pytest
from app.models import Usuario, Hospital, GrupoIntercambio, Unidad, Categoria, UsuarioUnidad


def _crear_contexto(db):
    hospital = Hospital(nombre="Hospital Test")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    unidad1 = Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo)
    unidad2 = Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo)
    cat_enfermeria = Categoria(nombre="Enfermería")
    cat_auxiliar = Categoria(nombre="Auxiliar de enfermería (TCAE)")
    db.session.add_all([unidad1, unidad2, cat_enfermeria, cat_auxiliar])
    db.session.commit()

    usuario = Usuario(
        nombre="Ana García", email="ana@hospital.es", unidad=unidad1, categoria=cat_enfermeria
    )
    usuario.set_password("pass")
    db.session.add(usuario)
    db.session.commit()

    db.session.add_all([
        UsuarioUnidad(usuario_id=usuario.id, unidad_id=unidad1.id, categoria_id=cat_enfermeria.id),
        UsuarioUnidad(usuario_id=usuario.id, unidad_id=unidad2.id, categoria_id=cat_auxiliar.id),
    ])
    db.session.commit()

    return usuario, unidad1, unidad2, cat_enfermeria, cat_auxiliar


def test_usuario_unidades_devuelve_ambas_unidades(db):
    usuario, unidad1, unidad2, _, _ = _crear_contexto(db)

    recuperado = db.session.get(Usuario, usuario.id)
    nombres = {u.nombre for u in recuperado.unidades}
    assert nombres == {"Urgencias", "UCI"}


def test_unidad_miembros_devuelve_los_usuarios_de_cada_unidad(db):
    usuario, unidad1, unidad2, _, _ = _crear_contexto(db)

    recuperada1 = db.session.get(Unidad, unidad1.id)
    recuperada2 = db.session.get(Unidad, unidad2.id)
    assert {u.id for u in recuperada1.miembros} == {usuario.id}
    assert {u.id for u in recuperada2.miembros} == {usuario.id}


def test_membresias_unidad_expone_la_categoria_especifica_por_unidad(db):
    usuario, unidad1, unidad2, cat_enfermeria, cat_auxiliar = _crear_contexto(db)

    recuperado = db.session.get(Usuario, usuario.id)
    categorias = {m.unidad_id: m.categoria_id for m in recuperado.membresias_unidad}
    assert categorias == {
        unidad1.id: cat_enfermeria.id,
        unidad2.id: cat_auxiliar.id,
    }


def test_no_permite_asociacion_duplicada(db):
    usuario, unidad1, _, cat_enfermeria, _ = _crear_contexto(db)

    db.session.add(UsuarioUnidad(usuario_id=usuario.id, unidad_id=unidad1.id, categoria_id=cat_enfermeria.id))
    with pytest.raises(Exception):
        db.session.commit()
