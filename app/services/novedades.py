"""Consulta del feed de novedades: cambios activos publicados en la unidad
del usuario, en orden LIFO (más reciente primero), paginados por cursor."""
from sqlalchemy.orm import contains_eager, selectinload

from app.models import PublicacionCambio, TurnoAceptado, TurnoCedido, Unidad, Usuario
from app.services.unidad_usuario import categoria_en_unidad

TAMANO_LOTE = 20

_ESTADOS_ACTIVOS = ("abierta", "parcialmente_resuelta")


def publicaciones_activas(usuario, unidad, despues_id=None, limite=TAMANO_LOTE):
    """Devuelve (publicaciones, hay_mas) para el feed de novedades.

    Visibilidad: misma categoría profesional y mismo grupo de intercambio
    que `usuario` en `unidad` (igual regla que /cambios), sin excluir las
    publicaciones propias, ya que el feed replica ver "todo lo publicado".
    Orden LIFO por fecha de creación (id, que crece con ella): las más
    recientes primero, y el cursor avanza hacia las más antiguas.
    """
    categoria = categoria_en_unidad(usuario, unidad)
    grupo_id = unidad.grupo_intercambio_id

    q = (
        PublicacionCambio.query
        .join(Usuario, PublicacionCambio.usuario_id == Usuario.id)
        .join(Unidad, Usuario.unidad_id == Unidad.id)
        .filter(
            PublicacionCambio.estado.in_(_ESTADOS_ACTIVOS),
            Usuario.categoria_id == categoria.id,
            Unidad.grupo_intercambio_id == grupo_id,
        )
        .options(
            contains_eager(PublicacionCambio.usuario),
            selectinload(PublicacionCambio.turnos_cedidos)
            .joinedload(TurnoCedido.franja_horaria),
            selectinload(PublicacionCambio.turnos_aceptados)
            .joinedload(TurnoAceptado.franja_horaria),
        )
    )
    if despues_id is not None:
        q = q.filter(PublicacionCambio.id < despues_id)

    publicaciones = (
        q.distinct()
        .order_by(PublicacionCambio.id.desc())
        .limit(limite + 1)
        .all()
    )
    hay_mas = len(publicaciones) > limite
    return publicaciones[:limite], hay_mas
