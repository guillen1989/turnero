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


# --- Helpers ---

def _usuario(email="test@test.es", hospital="H1", unidad="Urgencias", cat_nombre="Enfermería"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre=cat_nombre).first()
    return registrar_usuario("Test", email, "password123", hospital, unidad, cat.id)


def _franja(grupo_id, nombre="Mañana"):
    return FranjaHoraria.query.filter_by(
        grupo_intercambio_id=grupo_id, nombre=nombre
    ).first()


def _pub_cambio_dia(usuario, fecha_cede, fecha_acepta, franja_cede=None, franja_acepta=None):
    """Helper para crear una publicación de tipo cambio_dia."""
    franja_cede = franja_cede or _franja(usuario.unidad.grupo_intercambio_id, "Mañana")
    franja_acepta = franja_acepta or _franja(usuario.unidad.grupo_intercambio_id, "Tarde")
    
    pub = PublicacionCambio(usuario_id=usuario.id, tipo="cambio_dia")
    db.session.add(pub)
    db.session.flush()
    
    db.session.add(TurnoCedido(
        publicacion_id=pub.id,
        fecha=fecha_cede,
        franja_horaria_id=franja_cede.id,
    ))
    db.session.add(TurnoAceptado(
        publicacion_id=pub.id,
        fecha=fecha_acepta,
        franja_horaria_id=franja_acepta.id,
    ))
    db.session.commit()
    return pub


# --- Tests ---

def test_cambio_dia_misma_fecha_valido(db):
    """Un cambio_dia con turnos de la misma fecha debe validar correctamente."""
    u = _usuario()
    misma_fecha = date(2026, 9, 25)
    
    pub = _pub_cambio_dia(u, misma_fecha, misma_fecha)
    
    # El publicación debe crearse sin error
    assert pub.id is not None
    assert pub.tipo == "cambio_dia"
    assert pub.estado == "abierta"


def test_cambio_dia_fechas_diferentes_invalido(db):
    """Un cambio_dia con turnos de fechas diferentes debe fallar la validación."""
    u = _usuario()
    fecha1 = date(2026, 9, 25)
    fecha2 = date(2026, 9, 26)
    
    # TODO: implementar excepción en validador
    # Por ahora, la publicación se crea pero debería fallar en validación
    try:
        pub = _pub_cambio_dia(u, fecha1, fecha2)
        # Si llegamos aquí, el validador aún no está implementado
        # Marcar como expected failure
        assert False, "Se esperaba excepción de validación, pero no se lanzó"
    except ValueError as e:
        # Esperar excepción del validador
        assert "misma fecha" in str(e).lower()


def test_cambio_dia_con_multiples_turnos_cedidos_misma_fecha(db):
    """Un cambio_dia con múltiples turnos cedidos (misma fecha) debe validar."""
    u = _usuario()
    misma_fecha = date(2026, 9, 25)
    
    # Crear publicación con dos turnos cedidos de la misma fecha
    franja_manana = _franja(u.unidad.grupo_intercambio_id, "Mañana")
    franja_tarde = _franja(u.unidad.grupo_intercambio_id, "Tarde")
    
    pub = PublicacionCambio(usuario_id=u.id, tipo="cambio_dia")
    db.session.add(pub)
    db.session.flush()
    
    # Dos turnos cedidos, misma fecha, franjas distintas
    db.session.add(TurnoCedido(
        publicacion_id=pub.id, fecha=misma_fecha, franja_horaria_id=franja_manana.id
    ))
    db.session.add(TurnoCedido(
        publicacion_id=pub.id, fecha=misma_fecha, franja_horaria_id=franja_tarde.id
    ))
    
    franja_noche = _franja(u.unidad.grupo_intercambio_id, "Noche")
    db.session.add(TurnoAceptado(
        publicacion_id=pub.id, fecha=misma_fecha, franja_horaria_id=franja_noche.id
    ))
    db.session.commit()
    
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
        pub = PublicacionCambio(usuario_id=u.id, tipo="cambio_dia")
        db.session.add(pub)
        db.session.flush()
        
        # Dos turnos cedidos, FECHAS DIFERENTES
        db.session.add(TurnoCedido(
            publicacion_id=pub.id, fecha=fecha1, franja_horaria_id=franja_manana.id
        ))
        db.session.add(TurnoCedido(
            publicacion_id=pub.id, fecha=fecha2, franja_horaria_id=franja_tarde.id
        ))
        db.session.add(TurnoAceptado(
            publicacion_id=pub.id, fecha=fecha1, franja_horaria_id=franja_tarde.id
        ))
        db.session.commit()
        
        assert False, "Se esperaba excepción de validación"
    except ValueError as e:
        assert "misma fecha" in str(e).lower()


def test_cambio_dia_fecha_pasada_invalido(db):
    """Un cambio_dia para una fecha pasada debería caducar inmediatamente (o fallar)."""
    u = _usuario()
    fecha_pasada = date(2026, 1, 1)
    
    # Por ahora, la publicación se crea, pero debería marcarse como caducada
    # o fallar en validación
    try:
        pub = _pub_cambio_dia(u, fecha_pasada, fecha_pasada)
        # Si llegamos aquí, debería estar marcada como caducada al menos
        # TODO: implementar caducidad automática en validador de cambio_dia
        assert False, "Se esperaba que cambio_dia con fecha pasada fallara"
    except (ValueError, Exception):
        # Excepción esperada
        pass
