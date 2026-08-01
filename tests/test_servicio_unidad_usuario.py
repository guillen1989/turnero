import pytest
from flask import session
from werkzeug.exceptions import Forbidden

from app.models import Usuario, Hospital, GrupoIntercambio, Unidad, Categoria, UsuarioUnidad
from app.services.unidad_usuario import (
    categoria_en_unidad,
    pertenece_a,
    sincronizar_unidades,
    unidad_activa_o_403,
    unidades_de,
)


def _crear_contexto(db):
    hospital = Hospital(nombre="Hospital Test")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    unidad_uci = Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo)
    unidad_urgencias = Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo)
    unidad_ajena = Unidad(nombre="Traumatología", hospital=hospital, grupo_intercambio=grupo)
    cat_enfermeria = Categoria(nombre="Enfermería")
    cat_auxiliar = Categoria(nombre="Auxiliar de enfermería (TCAE)")
    db.session.add_all([unidad_uci, unidad_urgencias, unidad_ajena, cat_enfermeria, cat_auxiliar])
    db.session.commit()

    usuario = Usuario(
        nombre="Ana García", email="ana@hospital.es", unidad=unidad_uci, categoria=cat_enfermeria
    )
    usuario.set_password("pass")
    db.session.add(usuario)
    db.session.commit()

    db.session.add_all([
        UsuarioUnidad(usuario_id=usuario.id, unidad_id=unidad_uci.id, categoria_id=cat_enfermeria.id),
        UsuarioUnidad(usuario_id=usuario.id, unidad_id=unidad_urgencias.id, categoria_id=cat_auxiliar.id),
    ])
    db.session.commit()

    return usuario, unidad_uci, unidad_urgencias, unidad_ajena, cat_enfermeria, cat_auxiliar


# --- unidades_de ---

def test_unidades_de_devuelve_principal_y_membresias_ordenadas_por_nombre(db):
    usuario, unidad_uci, unidad_urgencias, _, _, _ = _crear_contexto(db)

    resultado = unidades_de(usuario)

    assert [u.nombre for u in resultado] == ["UCI", "Urgencias"]


def test_unidades_de_incluye_siempre_la_unidad_principal(db):
    hospital = Hospital(nombre="Hospital Otro")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()
    unidad_propia = Unidad(nombre="Propia", hospital=hospital, grupo_intercambio=grupo)
    unidad_extra = Unidad(nombre="Extra", hospital=hospital, grupo_intercambio=grupo)
    categoria = Categoria(nombre="Enfermería")
    db.session.add_all([unidad_propia, unidad_extra, categoria])
    db.session.commit()
    usuario = Usuario(
        nombre="Sin fila principal", email="sinfila@hospital.es",
        unidad=unidad_propia, categoria=categoria,
    )
    usuario.set_password("pass")
    db.session.add(usuario)
    db.session.commit()
    db.session.add(UsuarioUnidad(
        usuario_id=usuario.id, unidad_id=unidad_extra.id, categoria_id=categoria.id,
    ))
    db.session.commit()

    resultado = unidades_de(usuario)

    assert {u.id for u in resultado} == {unidad_propia.id, unidad_extra.id}


# --- pertenece_a ---

def test_pertenece_a_true_para_la_principal_y_las_membresias(db):
    usuario, unidad_uci, unidad_urgencias, _, _, _ = _crear_contexto(db)

    assert pertenece_a(usuario, unidad_uci) is True
    assert pertenece_a(usuario, unidad_urgencias) is True


def test_pertenece_a_false_para_unidad_ajena(db):
    usuario, _, _, unidad_ajena, _, _ = _crear_contexto(db)

    assert pertenece_a(usuario, unidad_ajena) is False


# --- categoria_en_unidad ---

def test_categoria_en_unidad_principal_devuelve_la_categoria_global(db):
    usuario, unidad_uci, _, _, cat_enfermeria, _ = _crear_contexto(db)

    assert categoria_en_unidad(usuario, unidad_uci) == cat_enfermeria


def test_categoria_en_unidad_extra_devuelve_la_de_esa_membresia(db):
    usuario, _, unidad_urgencias, _, _, cat_auxiliar = _crear_contexto(db)

    assert categoria_en_unidad(usuario, unidad_urgencias) == cat_auxiliar


# --- unidad_activa_o_403 ---

def test_unidad_activa_o_403_sin_parametro_y_sin_sesion_devuelve_la_principal(app, db):
    usuario, unidad_uci, _, _, _, _ = _crear_contexto(db)

    with app.test_request_context():
        assert unidad_activa_o_403(usuario, None) == unidad_uci


def test_unidad_activa_o_403_usa_la_sesion_si_no_viene_query_param(app, db):
    usuario, _, unidad_urgencias, _, _, _ = _crear_contexto(db)

    with app.test_request_context():
        session["unidad_activa_id"] = unidad_urgencias.id
        assert unidad_activa_o_403(usuario, None) == unidad_urgencias


def test_unidad_activa_o_403_prioriza_el_query_param_sobre_la_sesion(app, db):
    usuario, unidad_uci, unidad_urgencias, _, _, _ = _crear_contexto(db)

    with app.test_request_context():
        session["unidad_activa_id"] = unidad_urgencias.id
        assert unidad_activa_o_403(usuario, unidad_uci.id) == unidad_uci


def test_unidad_activa_o_403_con_sesion_obsoleta_cae_a_la_principal_y_la_limpia(app, db):
    usuario, unidad_uci, _, unidad_ajena, _, _ = _crear_contexto(db)

    with app.test_request_context():
        session["unidad_activa_id"] = unidad_ajena.id
        assert unidad_activa_o_403(usuario, None) == unidad_uci
        assert "unidad_activa_id" not in session


def test_unidad_activa_o_403_con_unidad_id_valido_devuelve_la_unidad(db):
    usuario, _, unidad_urgencias, _, _, _ = _crear_contexto(db)

    assert unidad_activa_o_403(usuario, unidad_urgencias.id) == unidad_urgencias


def test_unidad_activa_o_403_con_unidad_ajena_aborta(db):
    usuario, _, _, unidad_ajena, _, _ = _crear_contexto(db)

    with pytest.raises(Forbidden):
        unidad_activa_o_403(usuario, unidad_ajena.id)


def test_unidad_activa_o_403_con_unidad_inexistente_aborta(db):
    usuario, _, _, _, _, _ = _crear_contexto(db)

    with pytest.raises(Forbidden):
        unidad_activa_o_403(usuario, 999999)


# --- sincronizar_unidades ---

def test_sincronizar_unidades_añade_membresias_nuevas_con_su_categoria(db):
    usuario, unidad_uci, unidad_urgencias, unidad_ajena, cat_enfermeria, cat_auxiliar = _crear_contexto(db)

    sincronizar_unidades(usuario, {
        unidad_uci.id: cat_enfermeria.id,
        unidad_urgencias.id: cat_auxiliar.id,
        unidad_ajena.id: cat_enfermeria.id,
    })
    db.session.commit()

    recuperado = db.session.get(Usuario, usuario.id)
    assert {u.id for u in unidades_de(recuperado)} == {
        unidad_uci.id, unidad_urgencias.id, unidad_ajena.id,
    }
    categorias = {m.unidad_id: m.categoria_id for m in recuperado.membresias_unidad}
    assert categorias == {
        unidad_uci.id: cat_enfermeria.id,
        unidad_urgencias.id: cat_auxiliar.id,
        unidad_ajena.id: cat_enfermeria.id,
    }


def test_sincronizar_unidades_actualiza_la_categoria_de_una_membresia_existente(db):
    usuario, unidad_uci, unidad_urgencias, _, _, cat_auxiliar = _crear_contexto(db)

    sincronizar_unidades(usuario, {
        unidad_uci.id: cat_auxiliar.id,
        unidad_urgencias.id: cat_auxiliar.id,
    })
    db.session.commit()

    recuperado = db.session.get(Usuario, usuario.id)
    assert recuperado.categoria_id == cat_auxiliar.id
    categorias = {m.unidad_id: m.categoria_id for m in recuperado.membresias_unidad}
    assert categorias[unidad_urgencias.id] == cat_auxiliar.id


def test_sincronizar_unidades_quita_las_que_no_estan_pero_mantiene_la_principal(db):
    usuario, unidad_uci, unidad_urgencias, _, cat_enfermeria, _ = _crear_contexto(db)

    sincronizar_unidades(usuario, {unidad_uci.id: cat_enfermeria.id})
    db.session.commit()

    recuperado = db.session.get(Usuario, usuario.id)
    assert {u.id for u in unidades_de(recuperado)} == {unidad_uci.id}


def test_sincronizar_unidades_sin_la_principal_falla(db):
    usuario, unidad_uci, unidad_urgencias, _, cat_enfermeria, cat_auxiliar = _crear_contexto(db)

    with pytest.raises(AssertionError):
        sincronizar_unidades(usuario, {
            unidad_urgencias.id: cat_auxiliar.id,
        })
    db.session.rollback()
    assert {u.id for u in unidades_de(usuario)} == {unidad_uci.id, unidad_urgencias.id}
