"""
Capa de búsqueda de matches: conecta el motor puro con la base de datos.

Responsabilidades:
  - Filtrar candidatas por categoría, grupo de intercambio y estado activo.
  - Extraer los conjuntos de turnos de cada publicación ORM.
  - Delegar la lógica de coincidencia al motor puro (engine.py).
"""
from app.extensions import db
from app.models import PublicacionCambio, Usuario, Unidad
from app.matching.engine import detectar_match_directo


def _cedidos_abiertos(pub):
    return frozenset(
        (t.fecha, t.franja_horaria_id)
        for t in pub.turnos_cedidos
        if t.estado == "abierto"
    )


def _aceptados(pub):
    return frozenset(
        (t.fecha, t.franja_horaria_id)
        for t in pub.turnos_aceptados
    )


def buscar_matches_para(publicacion):
    """
    Devuelve las publicaciones activas que hacen match directo con `publicacion`.

    Solo considera candidatas del mismo grupo de intercambio y misma categoría,
    excluyendo la propia publicación y las inactivas.
    """
    propietario = db.session.get(Usuario, publicacion.usuario_id)
    grupo_id = propietario.unidad.grupo_intercambio_id

    candidatas = (
        PublicacionCambio.query
        .join(Usuario, PublicacionCambio.usuario_id == Usuario.id)
        .join(Unidad, Usuario.unidad_id == Unidad.id)
        .filter(
            PublicacionCambio.id != publicacion.id,
            PublicacionCambio.estado.in_(("abierta", "parcialmente_resuelta")),
            Usuario.categoria_id == propietario.categoria_id,
            Unidad.grupo_intercambio_id == grupo_id,
        )
        .all()
    )

    cedidos_pub = _cedidos_abiertos(publicacion)
    aceptados_pub = _aceptados(publicacion)

    return [
        c for c in candidatas
        if detectar_match_directo(
            cedidos_pub,
            aceptados_pub,
            _cedidos_abiertos(c),
            _aceptados(c),
        )
    ]
