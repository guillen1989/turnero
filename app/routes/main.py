from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import and_, exists, extract, or_

from app.extensions import db
from app.models import FranjaHoraria, MatchCambio, MatchParticipacion, PublicacionCambio, TurnoCedido, TurnoAceptado, Unidad, Usuario
from app.services.caducidad import caducar_publicaciones_expiradas

bp = Blueprint("main", __name__)


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


def _matches_activos(usuario_id):
    """Devuelve lista de (match, mi_participacion, otra_participacion) pendientes del usuario."""
    raw = (
        MatchCambio.query
        .join(MatchParticipacion, MatchCambio.id == MatchParticipacion.match_id)
        .join(PublicacionCambio, MatchParticipacion.publicacion_id == PublicacionCambio.id)
        .filter(
            PublicacionCambio.usuario_id == usuario_id,
            MatchCambio.estado.in_(["propuesto", "confirmado_parcial"]),
        )
        .distinct()
        .all()
    )
    resultado = []
    for match in raw:
        mi = next((p for p in match.participaciones if p.publicacion.usuario_id == usuario_id), None)
        otra = next((p for p in match.participaciones if p.publicacion.usuario_id != usuario_id), None)
        if mi and otra:
            resultado.append((match, mi, otra))
    return resultado


@bp.get("/")
def index():
    if current_user.is_authenticated:
        caducar_publicaciones_expiradas()
        publicaciones = (
            PublicacionCambio.query
            .filter_by(usuario_id=current_user.id)
            .order_by(PublicacionCambio.fecha_creacion.desc())
            .all()
        )
        matches = _matches_activos(current_user.id)
        return render_template("main/dashboard.html", publicaciones=publicaciones, matches=matches)
    return render_template("main/index.html")


@bp.get("/cambios")
@login_required
def cambios():
    mes = request.args.get("mes", type=int)
    dia = request.args.get("dia", type=int)
    nombre = request.args.get("usuario", "").strip()
    franja_id = request.args.get("franja", type=int)

    grupo_id = current_user.unidad.grupo_intercambio_id
    franjas = (
        FranjaHoraria.query
        .filter_by(grupo_intercambio_id=grupo_id)
        .order_by(FranjaHoraria.hora_inicio)
        .all()
    )

    q = (
        PublicacionCambio.query
        .join(TurnoCedido, PublicacionCambio.id == TurnoCedido.publicacion_id)
        .join(Usuario, PublicacionCambio.usuario_id == Usuario.id)
        .join(Unidad, Usuario.unidad_id == Unidad.id)
        .filter(
            PublicacionCambio.estado.in_(["abierta", "parcialmente_resuelta"]),
            PublicacionCambio.usuario_id != current_user.id,
            Usuario.categoria_id == current_user.categoria_id,
            Unidad.grupo_intercambio_id == grupo_id,
        )
    )

    if mes or dia:
        cedido_parts = []
        aceptado_parts = [TurnoAceptado.publicacion_id == PublicacionCambio.id]
        if mes:
            cedido_parts.append(extract("month", TurnoCedido.fecha) == mes)
            aceptado_parts.append(extract("month", TurnoAceptado.fecha) == mes)
        if dia:
            cedido_parts.append(extract("day", TurnoCedido.fecha) == dia)
            aceptado_parts.append(extract("day", TurnoAceptado.fecha) == dia)
        q = q.filter(or_(
            and_(*cedido_parts),
            exists().where(and_(*aceptado_parts)),
        ))
    if nombre:
        q = q.filter(Usuario.nombre.ilike(f"%{nombre}%"))
    if franja_id:
        q = q.filter(TurnoCedido.franja_horaria_id == franja_id)

    publicaciones = q.distinct().order_by(PublicacionCambio.fecha_creacion.desc()).all()

    return render_template("main/cambios.html", publicaciones=publicaciones,
                           mes=mes, dia=dia, nombre=nombre, franja_id=franja_id, franjas=franjas)
