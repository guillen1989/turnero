from datetime import date

from app.extensions import db
from app.models.match import MatchCambio, MatchParticipacion
from app.models.planilla import NotaDia
from app.models.publicacion import PublicacionCambio
from app.services.planilla import añadir_turno, eliminar_turno


def _añadir_linea_nota(usuario, fecha: date, linea: str):
    """Añade una línea al texto de la nota del día, creando la nota si no existe."""
    nota = NotaDia.query.filter_by(usuario_id=usuario.id, fecha=fecha).first()
    if nota is None:
        nota = NotaDia(usuario=usuario, fecha=fecha, texto=linea)
        db.session.add(nota)
    else:
        nota.texto = (nota.texto + "\n" + linea) if nota.texto else linea


def _fmt(turno) -> str:
    """'22/07 (Tarde)' a partir de un TurnoCedido."""
    return f"{turno.fecha.strftime('%-d/%m')} ({turno.franja_horaria.nombre})"


def get_matches_pendientes_volcar(usuario) -> list[dict]:
    """
    Devuelve una lista de dicts con info de matches confirmados que el usuario
    todavía no ha volcado a su planilla. Cada dict contiene:
      match_id, participacion_id, companeros, cedido, recibido
    """
    participaciones = (
        MatchParticipacion.query
        .join(MatchParticipacion.match)
        .join(MatchParticipacion.publicacion)
        .filter(
            PublicacionCambio.usuario_id == usuario.id,
            MatchCambio.estado == "confirmado_total",
            MatchParticipacion.volcado_planilla == False,
        )
        .all()
    )

    result = []
    for p in participaciones:
        otras = [o for o in p.match.participaciones if o.publicacion.usuario_id != usuario.id]
        companeros = [o.publicacion.usuario for o in otras]

        recibido = None
        if p.turno_aceptado:
            fecha_rec = p.turno_aceptado.fecha
            for otra in otras:
                if otra.turno_cedido and otra.turno_cedido.fecha == fecha_rec:
                    recibido = otra.turno_cedido
                    break

        result.append({
            "match_id": p.match.id,
            "participacion_id": p.id,
            "companeros": companeros,
            "cedido": p.turno_cedido,
            "recibido": recibido,
        })

    return result


def volcar_matches_a_planilla(usuario, participacion_ids: list[int]) -> int:
    """
    Aplica los cambios de las participaciones indicadas a la planilla del usuario:
    - Elimina el turno cedido de la planilla
    - Añade el turno recibido a la planilla
    - Anota ambos días con información del compañero
    - Marca volcado_planilla = True en cada participación procesada

    Solo procesa participaciones que pertenezcan al usuario, sean de un match
    confirmado_total y no hayan sido volcadas previamente.

    Returns: número de participaciones efectivamente volcadas.
    """
    if not participacion_ids:
        return 0

    participaciones = MatchParticipacion.query.filter(
        MatchParticipacion.id.in_(participacion_ids)
    ).all()

    count = 0
    for p in participaciones:
        if p.publicacion.usuario_id != usuario.id:
            continue
        if p.match.estado != "confirmado_total":
            continue
        if p.volcado_planilla:
            continue

        otras = [o for o in p.match.participaciones if o.publicacion.usuario_id != usuario.id]
        companero_nombres = ", ".join(o.publicacion.usuario.nombre for o in otras)
        n_bandas = len(p.match.participaciones)
        prefijo = f"Cambio a {n_bandas} bandas con" if n_bandas > 2 else "Cambio con"

        # Localizar el turno que el usuario recibe a cambio
        turno_recibido = None
        if p.turno_aceptado:
            fecha_rec = p.turno_aceptado.fecha
            for otra in otras:
                if otra.turno_cedido and otra.turno_cedido.fecha == fecha_rec:
                    turno_recibido = otra.turno_cedido
                    break

        if p.turno_cedido:
            eliminar_turno(usuario, p.turno_cedido.fecha, p.turno_cedido.franja_horaria_id)
            nota = f"{prefijo} {companero_nombres}: cediste este turno."
            if turno_recibido:
                nota += f" A cambio, trabajas el {_fmt(turno_recibido)}."
            _añadir_linea_nota(usuario, p.turno_cedido.fecha, nota)

        if turno_recibido:
            añadir_turno(usuario, turno_recibido.fecha, turno_recibido.franja_horaria_id)
            nota = f"{prefijo} {companero_nombres}: recibiste este turno."
            if p.turno_cedido:
                nota += f" A cambio, cediste el {_fmt(p.turno_cedido)}."
            _añadir_linea_nota(usuario, turno_recibido.fecha, nota)

        p.volcado_planilla = True
        count += 1

    db.session.commit()
    return count
