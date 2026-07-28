"""Validador de publicaciones de tipo cambio_dia.

Un cambio de turno en el día requiere que todos los turnos cedidos y aceptados
sean de la misma fecha.
"""
from app.models import PublicacionCambio


class ErrorValidacionCambioDia(ValueError):
    """Excepción lanzada cuando la validación de cambio_dia falla."""
    pass


def validar_publicacion_cambio_dia(publicacion: PublicacionCambio) -> None:
    """
    Valida que una publicación de tipo cambio_dia cumpla la regla:
    todos los turnos cedidos y aceptados deben ser de la misma fecha.
    
    Args:
        publicacion: PublicacionCambio a validar
        
    Raises:
        ErrorValidacionCambioDia: si la validación falla
    """
    if publicacion.tipo != "cambio_dia":
        # Solo validar publicaciones de tipo cambio_dia
        return
    
    # Recolectar todas las fechas
    fechas = set()
    
    # Añadir fechas de turnos cedidos
    for turno_cedido in publicacion.turnos_cedidos:
        fechas.add(turno_cedido.fecha)
    
    # Añadir fechas de turnos aceptados
    for turno_aceptado in publicacion.turnos_aceptados:
        fechas.add(turno_aceptado.fecha)
    
    # Verificar que todas las fechas sean iguales
    if len(fechas) > 1:
        raise ErrorValidacionCambioDia(
            f"Un cambio en el día debe tener todos los turnos de la misma fecha. "
            f"Fechas encontradas: {sorted(fechas)}"
        )
    
    if not fechas:
        raise ErrorValidacionCambioDia(
            "Una publicación cambio_dia debe tener al menos un turno cedido y uno aceptado"
        )
