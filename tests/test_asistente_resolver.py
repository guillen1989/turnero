from datetime import date

from app.models import Categoria, FranjaHoraria, insertar_categorias_semilla
from app.services.registro import registrar_usuario
from app.services.asistente.resolver import resolver_propuesta
from app.services.asistente.schema import PropuestaPublicacion

HOY = date(2026, 8, 25)


def _usuario(email="test@test.es", hospital="H1", unidad="Urgencias", cat_nombre="Enfermería"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre=cat_nombre).first()
    u = registrar_usuario("Test", email, "password123", hospital, unidad, cat.id)
    return u


def _propuesta(**overrides):
    base = dict(
        tipo="cambio",
        cedidos=[{"fecha": "2026-08-28", "franja": "Mañana"}],
        aceptados=[{"fecha": "2026-08-29", "franja": "Tarde"}],
        campos_faltantes=[],
    )
    base.update(overrides)
    return PropuestaPublicacion(**base)


def test_franja_exacta_resuelve_al_id_correcto(db):
    u = _usuario()
    franja_manana = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u.unidad.grupo_intercambio_id, nombre="Mañana"
    ).first()

    cedidos, aceptados, problemas = resolver_propuesta(_propuesta(), u, HOY)

    assert problemas == []
    assert cedidos == [(date(2026, 8, 28), franja_manana.id)]


def test_busqueda_de_franja_se_limita_al_grupo_del_usuario(db):
    u1 = _usuario(email="u1@test.es", unidad="Urgencias")
    u2 = _usuario(email="u2@test.es", unidad="Quirófano")

    franja_de_otro_grupo = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u2.unidad.grupo_intercambio_id, nombre="Mañana"
    ).first()
    franja_de_otro_grupo.nombre = "SoloEnQuirofano"
    db.session.commit()

    cedidos, aceptados, problemas = resolver_propuesta(
        _propuesta(cedidos=[{"fecha": "2026-08-28", "franja": "SoloEnQuirofano"}]),
        u1,
        HOY,
    )

    assert cedidos == []
    assert any("SoloEnQuirofano" in p for p in problemas)


def test_normalizacion_de_mayusculas_tildes_y_espacios_resuelve_igual(db):
    u = _usuario()
    franja_manana = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u.unidad.grupo_intercambio_id, nombre="Mañana"
    ).first()

    cedidos, aceptados, problemas = resolver_propuesta(
        _propuesta(cedidos=[{"fecha": "2026-08-28", "franja": "  MAÑANA  "}]),
        u,
        HOY,
    )

    assert problemas == []
    assert cedidos == [(date(2026, 8, 28), franja_manana.id)]


def test_sinonimo_de_franja_resuelve(db):
    u = _usuario()
    franja_manana = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u.unidad.grupo_intercambio_id, nombre="Mañana"
    ).first()

    cedidos, aceptados, problemas = resolver_propuesta(
        _propuesta(cedidos=[{"fecha": "2026-08-28", "franja": "mañanita"}]),
        u,
        HOY,
    )

    assert problemas == []
    assert cedidos == [(date(2026, 8, 28), franja_manana.id)]


def test_franja_desconocida_va_a_problemas_sin_inventar_id(db):
    u = _usuario()

    cedidos, aceptados, problemas = resolver_propuesta(
        _propuesta(cedidos=[{"fecha": "2026-08-28", "franja": "Turno Fantasma"}]),
        u,
        HOY,
    )

    assert cedidos == []
    assert any("Turno Fantasma" in p for p in problemas)


def test_franja_null_en_aceptados_hereda_la_franja_de_los_cedidos_si_es_unica(db):
    u = _usuario()
    franja_manana = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u.unidad.grupo_intercambio_id, nombre="Mañana"
    ).first()

    cedidos, aceptados, problemas = resolver_propuesta(
        _propuesta(
            cedidos=[
                {"fecha": "2026-08-28", "franja": "Mañana"},
                {"fecha": "2026-08-30", "franja": "Mañana"},
            ],
            aceptados=[{"fecha": "2026-08-29", "franja": None}],
        ),
        u,
        HOY,
    )

    assert problemas == []
    assert aceptados == [(date(2026, 8, 29), franja_manana.id)]


def test_franja_null_en_aceptados_es_cualquier_franja_si_cedidos_no_comparten_franja(db):
    u = _usuario()

    cedidos, aceptados, problemas = resolver_propuesta(
        _propuesta(
            cedidos=[
                {"fecha": "2026-08-28", "franja": "Mañana"},
                {"fecha": "2026-08-30", "franja": "Tarde"},
            ],
            aceptados=[{"fecha": "2026-08-29", "franja": None}],
        ),
        u,
        HOY,
    )

    assert problemas == []
    assert aceptados == [(date(2026, 8, 29), None)]


def test_fecha_en_el_pasado_va_a_problemas(db):
    u = _usuario()

    cedidos, aceptados, problemas = resolver_propuesta(
        _propuesta(cedidos=[{"fecha": "2020-01-01", "franja": "Mañana"}]),
        u,
        HOY,
    )

    assert cedidos == []
    assert problemas != []


def test_turnos_duplicados_van_a_problemas(db):
    u = _usuario()

    cedidos, aceptados, problemas = resolver_propuesta(
        _propuesta(cedidos=[
            {"fecha": "2026-08-28", "franja": "Mañana"},
            {"fecha": "2026-08-28", "franja": "Mañana"},
        ]),
        u,
        HOY,
    )

    assert problemas != []


def test_propuesta_con_campos_faltantes_no_se_resuelve(db):
    u = _usuario()

    cedidos, aceptados, problemas = resolver_propuesta(
        _propuesta(campos_faltantes=["fecha del turno cedido"]),
        u,
        HOY,
    )

    assert cedidos == []
    assert aceptados == []
    assert problemas == ["fecha del turno cedido"]


def test_resultado_pasa_validaciones_de_publicar_cambio(db):
    from app.routes.publicaciones import _validar_turnos
    from app.services.validacion_cambio_dia import validar_publicacion_cambio_dia
    from app.models import PublicacionCambio

    u = _usuario()

    cedidos, aceptados, problemas = resolver_propuesta(_propuesta(), u, HOY)

    assert problemas == []
    assert _validar_turnos("cambio", cedidos, aceptados, HOY) is None
    pub_falsa = PublicacionCambio(tipo="cambio")
    validar_publicacion_cambio_dia(pub_falsa)  # no lanza para tipo != cambio_dia


def test_problema_solo_en_aceptados_no_descarta_los_cedidos_ya_resueltos(db):
    u = _usuario()
    franja_manana = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u.unidad.grupo_intercambio_id, nombre="Mañana"
    ).first()

    cedidos, aceptados, problemas = resolver_propuesta(
        _propuesta(aceptados=[{"fecha": "2026-08-29", "franja": "Turno Fantasma"}]),
        u,
        HOY,
    )

    assert cedidos == [(date(2026, 8, 28), franja_manana.id)]
    assert aceptados == []
    assert any("Turno Fantasma" in p for p in problemas)


def test_problema_solo_en_cedidos_no_descarta_los_aceptados_ya_resueltos(db):
    u = _usuario()
    franja_tarde = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u.unidad.grupo_intercambio_id, nombre="Tarde"
    ).first()

    cedidos, aceptados, problemas = resolver_propuesta(
        _propuesta(cedidos=[{"fecha": "2026-08-28", "franja": "Turno Fantasma"}]),
        u,
        HOY,
    )

    assert cedidos == []
    assert aceptados == [(date(2026, 8, 29), franja_tarde.id)]
    assert any("Turno Fantasma" in p for p in problemas)


def test_campos_faltantes_solo_aceptados_resuelve_igualmente_los_cedidos(db):
    u = _usuario()
    franja_manana = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u.unidad.grupo_intercambio_id, nombre="Mañana"
    ).first()

    cedidos, aceptados, problemas = resolver_propuesta(
        _propuesta(campos_faltantes=["aceptados"]),
        u,
        HOY,
    )

    assert cedidos == [(date(2026, 8, 28), franja_manana.id)]
    assert aceptados == []
    assert problemas == ["aceptados"]


def test_campos_faltantes_solo_cedidos_resuelve_igualmente_los_aceptados(db):
    u = _usuario()
    franja_tarde = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=u.unidad.grupo_intercambio_id, nombre="Tarde"
    ).first()

    cedidos, aceptados, problemas = resolver_propuesta(
        _propuesta(campos_faltantes=["cedidos"]),
        u,
        HOY,
    )

    assert cedidos == []
    assert aceptados == [(date(2026, 8, 29), franja_tarde.id)]
    assert problemas == ["cedidos"]


def test_campos_faltantes_generico_sigue_sin_resolver_nada(db):
    u = _usuario()

    cedidos, aceptados, problemas = resolver_propuesta(
        _propuesta(campos_faltantes=["franja de los aceptados"]),
        u,
        HOY,
    )

    assert cedidos == []
    assert aceptados == []
    assert problemas == ["franja de los aceptados"]
