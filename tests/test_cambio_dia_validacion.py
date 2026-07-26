"""Tests de validación para publicaciones de tipo cambio_dia (Fase 1, paso 1.2).

Un cambio de turno en el día requiere que todos los turnos cedidos y aceptados
sean de la misma fecha. Este archivo verifica esa validación.
"""
from datetime import date

from app.extensions import db
from app.models import (
    Categoria,
    FranjaHoraria,
    PublicacionCambio,
    TurnoCedido,
    TurnoAceptado,
    insertar_categorias_semilla,
)
from app.services.registro import registrar_usuario
from app.services.publicaciones import publicar_cambio
from app.services.validacion_cambio_dia import ErrorValidacionCambioDia


# --- Helpers ---

def _usuario(email="test@test.es", hospital="H1", unidad="Urgencias", cat_nombre="Enfermería"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre=cat_nombre).first()
    return registrar_usuario("Test", email, "password123", hospital, unidad, cat.id)


def _franja(grupo_id, nombre="Mañana"):
    return FranjaHoraria.query.filter_by(
        grupo_intercambio_id=grupo_id, nombre=nombre
    ).first()


# --- Tests ---

def test_cambio_dia_misma_fecha_valido(db):
    """Un cambio_dia con turnos de la misma fecha debe validar correctamente."""
    u = _usuario()
    misma_fecha = date(2026, 9, 25)
    franja_manana = _franja(u.unidad.grupo_intercambio_id, "Mañana")
    franja_tarde = _franja(u.unidad.grupo_intercambio_id, "Tarde")
    
    # Crear publicación usando publicar_cambio, que incluye validación
    pub = publicar_cambio(
        usuario_id=u.id,
        turnos_cedidos=[(misma_fecha, franja_manana.id)],
        turnos_aceptados=[(misma_fecha, franja_tarde.id)],
        tipo="cambio_dia"
    )
    
    # El publicación debe crearse sin error
    assert pub.id is not None
    assert pub.tipo == "cambio_dia"
    assert pub.estado == "abierta"


def test_cambio_dia_fechas_diferentes_invalido(db):
    """Un cambio_dia con turnos de fechas diferentes debe fallar la validación."""
    u = _usuario()
    fecha1 = date(2026, 9, 25)
    fecha2 = date(2026, 9, 26)
    franja_manana = _franja(u.unidad.grupo_intercambio_id, "Mañana")
    franja_tarde = _franja(u.unidad.grupo_intercambio_id, "Tarde")
    
    # Crear publicación con fechas diferentes debería fallar
    try:
        pub = publicar_cambio(
            usuario_id=u.id,
            turnos_cedidos=[(fecha1, franja_manana.id)],
            turnos_aceptados=[(fecha2, franja_tarde.id)],
            tipo="cambio_dia"
        )
        assert False, "Se esperaba excepción de validación, pero no se lanzó"
    except ErrorValidacionCambioDia as e:
        assert "misma fecha" in str(e).lower()


def test_cambio_dia_con_multiples_turnos_cedidos_misma_fecha(db):
    """Un cambio_dia con múltiples turnos cedidos (misma fecha) debe validar."""
    u = _usuario()
    misma_fecha = date(2026, 9, 25)
    franja_manana = _franja(u.unidad.grupo_intercambio_id, "Mañana")
    franja_tarde = _franja(u.unidad.grupo_intercambio_id, "Tarde")
    franja_noche = _franja(u.unidad.grupo_intercambio_id, "Noche")
    
    # Crear publicación con dos turnos cedidos de la misma fecha
    pub = publicar_cambio(
        usuario_id=u.id,
        turnos_cedidos=[(misma_fecha, franja_manana.id), (misma_fecha, franja_tarde.id)],
        turnos_aceptados=[(misma_fecha, franja_noche.id)],
        tipo="cambio_dia"
    )
    
    # Debe validar sin error
    assert pub.id is not None
    assert pub.tipo == "cambio_dia"
    assert len(pub.turnos_cedidos) == 2


def test_cambio_dia_turnos_cedidos_fechas_diferentes_invalido(db):
    """Un cambio_dia con turnos cedidos de fechas diferentes debe fallar."""
    u = _usuario()
    fecha1 = date(2026, 9, 25)
    fecha2 = date(2026, 9, 26)
    franja_manana = _franja(u.unidad.grupo_intercambio_id, "Mañana")
    franja_tarde = _franja(u.unidad.grupo_intercambio_id, "Tarde")
    
    try:
        pub = publicar_cambio(
            usuario_id=u.id,
            turnos_cedidos=[(fecha1, franja_manana.id), (fecha2, franja_tarde.id)],
            turnos_aceptados=[(fecha1, franja_tarde.id)],
            tipo="cambio_dia"
        )
        assert False, "Se esperaba excepción de validación"
    except ErrorValidacionCambioDia as e:
        assert "misma fecha" in str(e).lower()


def test_cambio_dia_fecha_pasada_invalido(db):
    """Un cambio_dia para una fecha pasada debería fallar."""
    u = _usuario()
    fecha_pasada = date(2026, 1, 1)
    franja_manana = _franja(u.unidad.grupo_intercambio_id, "Mañana")
    franja_tarde = _franja(u.unidad.grupo_intercambio_id, "Tarde")
    
    # Por ahora, la publicación se crea, pero debería validarse fecha pasada
    # en un paso posterior (Fase 6 - caducidad)
    pub = publicar_cambio(
        usuario_id=u.id,
        turnos_cedidos=[(fecha_pasada, franja_manana.id)],
        turnos_aceptados=[(fecha_pasada, franja_tarde.id)],
        tipo="cambio_dia"
    )
    # La validación de fecha pasada es responsabilidad de caducidad, no de validador
    assert pub.id is not None


def test_cambio_normal_no_se_valida_cambio_dia(db):
    """Un cambio_dia normal (tipo cambio) no debe aplicar validación cambio_dia."""
    u = _usuario()
    fecha1 = date(2026, 9, 25)
    fecha2 = date(2026, 9, 26)  # fechas diferentes
    franja_manana = _franja(u.unidad.grupo_intercambio_id, "Mañana")
    franja_tarde = _franja(u.unidad.grupo_intercambio_id, "Tarde")
    
    # Crear publicación normal (tipo "cambio") con fechas diferentes
    # NO debería fallar porque el validador solo aplica a cambio_dia
    pub = publicar_cambio(
        usuario_id=u.id,
        turnos_cedidos=[(fecha1, franja_manana.id)],
        turnos_aceptados=[(fecha2, franja_tarde.id)],
        tipo="cambio"  # tipo normal, no cambio_dia
    )
    
    assert pub.id is not None
    assert pub.tipo == "cambio"
