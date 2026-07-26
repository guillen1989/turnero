from app.models import Usuario, Hospital, GrupoIntercambio, Unidad, Categoria, UnidadSupervisada
from app.services.supervision import (
    puede_supervisar,
    sincronizar_unidades_supervisadas,
    unidades_supervisadas_de,
)


def _crear_contexto(db):
    hospital = Hospital(nombre="Hospital Test")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    unidad_uci = Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo)
    unidad_urgencias = Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo)
    unidad_ajena = Unidad(nombre="Traumatología", hospital=hospital, grupo_intercambio=grupo)
    categoria = Categoria(nombre="Enfermería")
    db.session.add_all([unidad_uci, unidad_urgencias, unidad_ajena, categoria])
    db.session.commit()

    usuario = Usuario(
        nombre="Ana García", email="ana@hospital.es", unidad=unidad_uci, categoria=categoria, es_supervisora=True
    )
    usuario.set_password("pass")
    db.session.add(usuario)
    db.session.commit()

    db.session.add_all([
        UnidadSupervisada(usuario_id=usuario.id, unidad_id=unidad_urgencias.id),
        UnidadSupervisada(usuario_id=usuario.id, unidad_id=unidad_uci.id),
    ])
    db.session.commit()

    return usuario, unidad_uci, unidad_urgencias, unidad_ajena


def test_unidades_supervisadas_de_devuelve_las_unidades_ordenadas_por_nombre(db):
    usuario, unidad_uci, unidad_urgencias, _ = _crear_contexto(db)

    resultado = unidades_supervisadas_de(usuario)

    assert [u.nombre for u in resultado] == ["UCI", "Urgencias"]


def test_unidades_supervisadas_de_vacio_si_no_supervisa_ninguna(db):
    hospital = Hospital(nombre="Hospital Sin Unidades")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()
    unidad = Unidad(nombre="Sola", hospital=hospital, grupo_intercambio=grupo)
    categoria = Categoria(nombre="Cat")
    db.session.add_all([unidad, categoria])
    db.session.commit()
    usuario = Usuario(nombre="Sin unidades", email="sin@hospital.es", unidad=unidad, categoria=categoria)
    usuario.set_password("pass")
    db.session.add(usuario)
    db.session.commit()

    assert unidades_supervisadas_de(usuario) == []


def test_puede_supervisar_devuelve_true_para_unidad_asociada(db):
    usuario, unidad_uci, unidad_urgencias, _ = _crear_contexto(db)

    assert puede_supervisar(usuario, unidad_uci) is True
    assert puede_supervisar(usuario, unidad_urgencias) is True


def test_puede_supervisar_devuelve_false_para_unidad_no_asociada(db):
    usuario, _, _, unidad_ajena = _crear_contexto(db)

    assert puede_supervisar(usuario, unidad_ajena) is False


def test_sincronizar_unidades_supervisadas_añade_las_nuevas(db):
    usuario, unidad_uci, unidad_urgencias, unidad_ajena = _crear_contexto(db)

    sincronizar_unidades_supervisadas(
        usuario, {unidad_uci.id, unidad_urgencias.id, unidad_ajena.id}
    )
    db.session.commit()

    assert {u.id for u in unidades_supervisadas_de(usuario)} == {
        unidad_uci.id, unidad_urgencias.id, unidad_ajena.id,
    }


def test_sincronizar_unidades_supervisadas_quita_las_que_sobran(db):
    usuario, unidad_uci, unidad_urgencias, _ = _crear_contexto(db)

    sincronizar_unidades_supervisadas(usuario, {unidad_uci.id})
    db.session.commit()

    assert {u.id for u in unidades_supervisadas_de(usuario)} == {unidad_uci.id}


def test_sincronizar_unidades_supervisadas_vacio_quita_todas(db):
    usuario, _, _, _ = _crear_contexto(db)

    sincronizar_unidades_supervisadas(usuario, set())
    db.session.commit()

    assert unidades_supervisadas_de(usuario) == []
