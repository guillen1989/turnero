"""
Capa de búsqueda y creación de matches: conecta el motor puro con la base de datos.

Responsabilidades:
  - Filtrar candidatas por categoría, grupo de intercambio y estado activo.
  - Extraer los conjuntos de turnos de cada publicación ORM.
  - Delegar la lógica de coincidencia al motor puro (engine.py).
  - Crear registros MatchCambio, MatchParticipacion y Notificacion.
"""
from app.extensions import db
from app.models import (
    MatchCambio,
    MatchParticipacion,
    Notificacion,
    PublicacionCambio,
    Unidad,
    Usuario,
)
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


def _primer_cedido_que_acepta(pub, aceptados_contraparte):
    """Primer TurnoCedido abierto de pub cuya clave (fecha, franja_id) está en aceptados_contraparte."""
    for t in pub.turnos_cedidos:
        if t.estado == "abierto" and (t.fecha, t.franja_horaria_id) in aceptados_contraparte:
            return t
    return None


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


def crear_match_directo(pub_a, pub_b):
    """
    Crea un MatchCambio directo (2 bandas) entre pub_a y pub_b con sus
    MatchParticipacion y las Notificacion para cada usuario implicado.
    """
    aceptados_a = _aceptados(pub_a)
    aceptados_b = _aceptados(pub_b)

    turno_a = _primer_cedido_que_acepta(pub_a, aceptados_b)
    turno_b = _primer_cedido_que_acepta(pub_b, aceptados_a)

    match = MatchCambio(tipo="directo_2", estado="propuesto")
    db.session.add(match)
    db.session.flush()

    db.session.add(MatchParticipacion(
        match_id=match.id,
        publicacion_id=pub_a.id,
        turno_cedido_id=turno_a.id,
    ))
    db.session.add(MatchParticipacion(
        match_id=match.id,
        publicacion_id=pub_b.id,
        turno_cedido_id=turno_b.id,
    ))

    db.session.add(Notificacion(
        usuario_id=pub_a.usuario_id,
        match_id=match.id,
        tipo="nuevo_match",
    ))
    db.session.add(Notificacion(
        usuario_id=pub_b.usuario_id,
        match_id=match.id,
        tipo="nuevo_match",
    ))

    db.session.commit()
    return match
