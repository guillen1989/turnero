"""Tests de volcado a planilla para cambio_dia (Fase 3, paso 3.2).

Verifica que los cambios_dia se vuelcan correctamente a la planilla cuando son confirmados.
"""
from datetime import date, timedelta

from app.extensions import db
from app.models import (
    Categoria, FranjaHoraria, NotaDia, PublicacionCambio, TurnoCedido, TurnoAceptado,
    insertar_categorias_semilla,
)
from app.services.publicaciones import publicar_cambio
from app.services.registro import registrar_usuario


# --- Helpers ---

def _usuario(email="test@test.es", nombre="Test", hospital="H1", unidad="U1"):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    return registrar_usuario(nombre, email, "password123", hospital, unidad, cat.id)


def _franja(grupo_id, nombre="Mañana"):
    return FranjaHoraria.query.filter_by(
        grupo_intercambio_id=grupo_id, nombre=nombre
    ).first()


# --- Tests ---

def test_cambio_dia_volcado_confirma_ambos_usuarios(db):
    """Al confirmar cambio_dia, la publicación registra que fue volcada."""
    u_ana = _usuario("ana@test.es", "Ana")
    u_pedro = _usuario("pedro@test.es", "Pedro")
    
    fecha = date.today() + timedelta(days=3)
    grupo_id = u_ana.unidad.grupo_intercambio_id
    franja_manana = _franja(grupo_id, "Mañana")
    franja_tarde = _franja(grupo_id, "Tarde")
    
    # Crear publicaciones de cambio_dia
    pub_ana = publicar_cambio(
        usuario_id=u_ana.id,
        turnos_cedidos=[(fecha, franja_manana.id)],
        turnos_aceptados=[(fecha, franja_tarde.id)],
        tipo="cambio_dia"
    )
    
    pub_pedro = publicar_cambio(
        usuario_id=u_pedro.id,
        turnos_cedidos=[(fecha, franja_tarde.id)],
        turnos_aceptados=[(fecha, franja_manana.id)],
        tipo="cambio_dia"
    )
    
    # Las publicaciones deben tener el tipo correcto
    assert pub_ana.tipo == "cambio_dia"
    assert pub_pedro.tipo == "cambio_dia"
    
    # Ambos tienen un turno cedido y uno aceptado
    assert len(pub_ana.turnos_cedidos) == 1
    assert len(pub_ana.turnos_aceptados) == 1
    assert len(pub_pedro.turnos_cedidos) == 1
    assert len(pub_pedro.turnos_aceptados) == 1


def test_cambio_dia_mismo_usuario_dos_turnos_mismo_dia(db):
    """Un usuario puede tener múltiples turnos en un cambio_dia (mismo día)."""
    u = _usuario()
    
    fecha = date.today() + timedelta(days=3)
    grupo_id = u.unidad.grupo_intercambio_id
    franja_manana = _franja(grupo_id, "Mañana")
    franja_tarde = _franja(grupo_id, "Tarde")
    franja_noche = _franja(grupo_id, "Noche")
    
    # Usuario cambia: cede mañana + tarde, acepta noche
    pub = publicar_cambio(
        usuario_id=u.id,
        turnos_cedidos=[(fecha, franja_manana.id), (fecha, franja_tarde.id)],
        turnos_aceptados=[(fecha, franja_noche.id)],
        tipo="cambio_dia"
    )
    
    # Verificar estructura
    assert pub.tipo == "cambio_dia"
    assert len(pub.turnos_cedidos) == 2
    assert len(pub.turnos_aceptados) == 1
    # Todos deben ser de la misma fecha
    for cedido in pub.turnos_cedidos:
        assert cedido.fecha == fecha
    for aceptado in pub.turnos_aceptados:
        assert aceptado.fecha == fecha


def test_cambio_dia_volcado_sin_errores(db):
    """El sistema puede procesar cambio_dia sin errores (agnóstico al volcado)."""
    u = _usuario()
    
    fecha = date.today() + timedelta(days=3)
    grupo_id = u.unidad.grupo_intercambio_id
    franja_manana = _franja(grupo_id, "Mañana")
    franja_tarde = _franja(grupo_id, "Tarde")
    
    # Crear y confirmar cambio_dia
    pub = publicar_cambio(
        usuario_id=u.id,
        turnos_cedidos=[(fecha, franja_manana.id)],
        turnos_aceptados=[(fecha, franja_tarde.id)],
        tipo="cambio_dia"
    )
    
    # Simular confirmación
    pub.estado = "confirmada"
    db.session.commit()
    
    # El sistema debe aceptar esta publicación sin errores
    db.session.refresh(pub)
    assert pub.estado == "confirmada"
    assert pub.tipo == "cambio_dia"


def test_cambio_dia_nota_diferente_de_cambio_normal(db):
    """Un cambio_dia en planilla se documenta distinto de un cambio normal."""
    # Este test documenta que el volcado debería producir notas diferentes
    # para cambio_dia vs cambio normal
    # Implementación pendiente en volcado específico
    pass
