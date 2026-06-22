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


def _partners_confirmados(usuario_id):
    """Devuelve dict {pub_id: nombre_partner} para publicaciones con match confirmado_total."""
    raw = (
        MatchCambio.query
        .join(MatchParticipacion, MatchCambio.id == MatchParticipacion.match_id)
        .join(PublicacionCambio, MatchParticipacion.publicacion_id == PublicacionCambio.id)
        .filter(
            PublicacionCambio.usuario_id == usuario_id,
            MatchCambio.estado == "confirmado_total",
        )
        .distinct()
        .all()
    )
    result = {}
    for match in raw:
        mi = next((p for p in match.participaciones if p.publicacion.usuario_id == usuario_id), None)
        otra = next((p for p in match.participaciones if p.publicacion.usuario_id != usuario_id), None)
        if mi and otra:
            result[mi.publicacion_id] = otra.publicacion.usuario.nombre
    return result


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


_ESTADOS_DASHBOARD = {
    "abierta": ["abierta", "parcialmente_resuelta"],
    "pendiente": None,
    "confirmada": ["confirmada"],
    "caducada": ["caducada"],
}


def _query_pendientes(usuario_id):
    """Publicaciones del usuario con algún match activo (propuesto o confirmado parcialmente)."""
    return (
        PublicacionCambio.query
        .join(MatchParticipacion, PublicacionCambio.id == MatchParticipacion.publicacion_id)
        .join(MatchCambio, MatchParticipacion.match_id == MatchCambio.id)
        .filter(
            PublicacionCambio.usuario_id == usuario_id,
            MatchCambio.estado.in_(["propuesto", "confirmado_parcial"]),
        )
        .distinct()
    )


def _publicaciones_pendientes(usuario_id):
    """Publicaciones con match activo (pendiente de confirmar por alguna de las partes)."""
    return _query_pendientes(usuario_id).order_by(PublicacionCambio.fecha_creacion.desc()).all()


def _conteos_tabs(usuario_id):
    pendientes_subq = (
        _query_pendientes(usuario_id)
        .with_entities(PublicacionCambio.id)
        .subquery()
    )
    from sqlalchemy import select as sa_select
    pendientes_select = sa_select(pendientes_subq)

    def _count(estados, exclude_pendientes=False):
        q = (
            PublicacionCambio.query
            .filter_by(usuario_id=usuario_id)
            .filter(PublicacionCambio.estado.in_(estados))
        )
        if exclude_pendientes:
            q = q.filter(~PublicacionCambio.id.in_(pendientes_select))
        return q.count()

    return {
        "abierta": _count(["abierta", "parcialmente_resuelta"], exclude_pendientes=True),
        "pendiente": _query_pendientes(usuario_id).count(),
        "confirmada": _count(["confirmada"]),
        "caducada": _count(["caducada"]),
    }


@bp.get("/")
def index():
    if current_user.is_authenticated:
        caducar_publicaciones_expiradas()
        estado_filtro = request.args.get("estado", "abierta")
        if estado_filtro not in _ESTADOS_DASHBOARD:
            estado_filtro = "abierta"

        if estado_filtro == "pendiente":
            publicaciones = _publicaciones_pendientes(current_user.id)
        elif estado_filtro == "abierta":
            from sqlalchemy import select as sa_select
            pendientes_subq = (
                _query_pendientes(current_user.id)
                .with_entities(PublicacionCambio.id)
                .subquery()
            )
            publicaciones = (
                PublicacionCambio.query
                .filter_by(usuario_id=current_user.id)
                .filter(PublicacionCambio.estado.in_(["abierta", "parcialmente_resuelta"]))
                .filter(~PublicacionCambio.id.in_(sa_select(pendientes_subq)))
                .order_by(PublicacionCambio.fecha_creacion.desc())
                .all()
            )
        else:
            estados = _ESTADOS_DASHBOARD[estado_filtro]
            publicaciones = (
                PublicacionCambio.query
                .filter_by(usuario_id=current_user.id)
                .filter(PublicacionCambio.estado.in_(estados))
                .order_by(PublicacionCambio.fecha_creacion.desc())
                .all()
            )

        matches = _matches_activos(current_user.id)
        conteos = _conteos_tabs(current_user.id)
        partners = _partners_confirmados(current_user.id) if estado_filtro == "confirmada" else {}
        return render_template(
            "main/dashboard.html",
            publicaciones=publicaciones,
            matches=matches,
            estado_filtro=estado_filtro,
            conteos=conteos,
            partners=partners,
        )
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
        cedido_parts = [TurnoCedido.publicacion_id == PublicacionCambio.id]
        aceptado_parts = [TurnoAceptado.publicacion_id == PublicacionCambio.id]
        if mes:
            cedido_parts.append(extract("month", TurnoCedido.fecha) == mes)
            aceptado_parts.append(extract("month", TurnoAceptado.fecha) == mes)
        if dia:
            cedido_parts.append(extract("day", TurnoCedido.fecha) == dia)
            aceptado_parts.append(extract("day", TurnoAceptado.fecha) == dia)
        q = q.filter(or_(
            exists().where(and_(*cedido_parts)),
            exists().where(and_(*aceptado_parts)),
        ))
    if nombre:
        q = q.filter(Usuario.nombre.ilike(f"%{nombre}%"))
    if franja_id:
        cedido_franja = exists().where(
            and_(TurnoCedido.publicacion_id == PublicacionCambio.id,
                 TurnoCedido.franja_horaria_id == franja_id)
        )
        aceptado_franja = exists().where(
            and_(TurnoAceptado.publicacion_id == PublicacionCambio.id,
                 TurnoAceptado.franja_horaria_id == franja_id)
        )
        q = q.filter(or_(cedido_franja, aceptado_franja))

    publicaciones = q.distinct().order_by(PublicacionCambio.fecha_creacion.desc()).all()

    return render_template("main/cambios.html", publicaciones=publicaciones,
                           mes=mes, dia=dia, nombre=nombre, franja_id=franja_id, franjas=franjas)
