"""Tests de los choke points centrales de multi-unidad con el feature flag
`multi_unidad` (Paso 3 de docs/FEAT_FLAG_MULTI.md)."""

from flask import session as flask_session

from app.extensions import db
from app.models import (
    Categoria,
    GrupoIntercambio,
    Unidad,
    UsuarioUnidad,
    insertar_categorias_semilla,
)
from app.services.feature_flags import activar_global, desactivar_global
from app.services.registro import registrar_usuario
from app.services.unidad_usuario import (
    pertenece_a,
    unidad_activa_o_403,
    unidades_de,
)


def _crear_usuario_con_dos_unidades():
    insertar_categorias_semilla()
    cat_enfermeria = Categoria.query.filter_by(nombre="Enfermería").first()
    cat_auxiliar = Categoria.query.filter_by(
        nombre="Auxiliar de enfermería (TCAE)"
    ).first()

    usuario = registrar_usuario(
        "Ana", "ana@test.es", "password123", "H-Principal", "UCI", cat_enfermeria.id
    )

    grupo_b = GrupoIntercambio()
    db.session.add(grupo_b)
    db.session.commit()

    hospital_principal = usuario.unidad.hospital
    unidad_b = Unidad(
        nombre="Urgencias",
        hospital=hospital_principal,
        grupo_intercambio=grupo_b,
    )
    db.session.add(unidad_b)
    db.session.commit()

    db.session.add(
        UsuarioUnidad(
            usuario_id=usuario.id,
            unidad_id=unidad_b.id,
            categoria_id=cat_auxiliar.id,
        )
    )
    db.session.commit()

    return usuario, usuario.unidad, unidad_b


class TestUnidadesDe:
    def test_con_flag_activo_devuelve_todas(self, app, db):
        usuario, unidad_principal, unidad_secundaria = (
            _crear_usuario_con_dos_unidades()
        )
        activar_global("multi_unidad")

        resultado = unidades_de(usuario)

        assert len(resultado) == 2
        assert unidad_principal in resultado
        assert unidad_secundaria in resultado

    def test_con_flag_desactivado_devuelve_solo_principal(self, app, db):
        usuario, unidad_principal, unidad_secundaria = (
            _crear_usuario_con_dos_unidades()
        )
        desactivar_global("multi_unidad")

        resultado = unidades_de(usuario)

        assert resultado == [unidad_principal]


class TestUnidadActivaO403:
    def test_con_flag_activo_usa_unidad_id_explicito(self, app, db):
        usuario, unidad_principal, unidad_secundaria = (
            _crear_usuario_con_dos_unidades()
        )
        activar_global("multi_unidad")

        resultado = unidad_activa_o_403(usuario, unidad_secundaria.id)

        assert resultado == unidad_secundaria

    def test_con_flag_desactivado_ignora_unidad_id_y_devuelve_principal(
        self, app, db
    ):
        usuario, unidad_principal, unidad_secundaria = (
            _crear_usuario_con_dos_unidades()
        )
        desactivar_global("multi_unidad")

        resultado = unidad_activa_o_403(usuario, unidad_secundaria.id)

        assert resultado == unidad_principal

    def test_con_flag_desactivado_ignora_sesion_y_devuelve_principal(
        self, app, db
    ):
        usuario, unidad_principal, unidad_secundaria = (
            _crear_usuario_con_dos_unidades()
        )
        desactivar_global("multi_unidad")
        with app.test_request_context():
            flask_session["unidad_activa_id"] = unidad_secundaria.id
            resultado = unidad_activa_o_403(usuario, None)

        assert resultado == unidad_principal


class TestPerteneceANoRegresion:
    def test_con_flag_desactivado_sigue_devolviendo_true_para_membresia(
        self, app, db
    ):
        """`pertenece_a` NO debe cambiar con el flag — solo
        `unidad_activa_o_403` y `unidades_de` sí lo hacen."""
        usuario, unidad_principal, unidad_secundaria = (
            _crear_usuario_con_dos_unidades()
        )
        desactivar_global("multi_unidad")

        assert pertenece_a(usuario, unidad_secundaria) is True
        assert pertenece_a(usuario, unidad_principal) is True

    def test_con_flag_desactivado_devuelve_false_para_unidad_ajena(
        self, app, db
    ):
        usuario, unidad_principal, _ = _crear_usuario_con_dos_unidades()
        desactivar_global("multi_unidad")

        hospital = usuario.unidad.hospital
        grupo = GrupoIntercambio()
        db.session.add_all([hospital, grupo])
        db.session.commit()
        unidad_ajena = Unidad(
            nombre="Cardiología", hospital=hospital, grupo_intercambio=grupo
        )
        db.session.add(unidad_ajena)
        db.session.commit()

        assert pertenece_a(usuario, unidad_ajena) is False
