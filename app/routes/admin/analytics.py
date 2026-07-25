from flask import jsonify, render_template, request
from sqlalchemy import distinct, func

from app.extensions import db
from app.models import (
    AuditEliminacion,
    Categoria,
    Event,
    Hospital,
    MatchCambio,
    MatchParticipacion,
    PlanillaMes,
    PublicacionCambio,
    Unidad,
    Usuario,
)
from app.routes.admin import admin_required, bp


@bp.route("/analytics")
@admin_required
def analytics():
    stats = {
        "usuarios": Usuario.query.count(),
        "hospitales": Hospital.query.count(),
        "unidades": Unidad.query.count(),
        "categorias": Categoria.query.count(),
        "publicaciones": PublicacionCambio.query.filter_by(es_sintetica=False).count(),
        "oportunidades_3": PublicacionCambio.query.filter(
            PublicacionCambio.es_sintetica.is_(True),
            PublicacionCambio.sintetica_pub_intermedio_id.is_(None),
        ).count(),
        "oportunidades_4": PublicacionCambio.query.filter(
            PublicacionCambio.es_sintetica.is_(True),
            PublicacionCambio.sintetica_pub_intermedio_id.isnot(None),
        ).count(),
        "activas": PublicacionCambio.query.filter(
            PublicacionCambio.es_sintetica.is_(False),
            PublicacionCambio.estado.in_(["abierta", "parcialmente_resuelta"]),
        ).count(),
        "matches": MatchCambio.query.count(),
        "confirmados": MatchCambio.query.filter_by(estado="confirmado_total").count(),
        "eliminadas": AuditEliminacion.query.count(),
        "planillas_publicadas": (
            db.session.query(func.count(distinct(PlanillaMes.usuario_id)))
            .filter(PlanillaMes.publicada.is_(True))
            .scalar() or 0
        ),
    }
    unidades = (
        Unidad.query
        .join(Hospital)
        .outerjoin(Categoria, Unidad.categoria_id == Categoria.id)
        .order_by(Hospital.nombre, Categoria.nombre, Unidad.nombre)
        .all()
    )
    return render_template("admin/analytics.html", stats=stats, unidades=unidades)


@bp.route("/analytics/data")
@admin_required
def analytics_data():
    granularity = request.args.get("granularity", "day")
    if granularity not in ("day", "week", "month"):
        granularity = "day"
    unidad_id = request.args.get("unidad_id", type=int)

    def to_dict(rows):
        return {str(row.periodo.date()): row.total for row in rows if row.periodo is not None}

    # ── usuarios nuevos ──────────────────────────────────────────────────────
    q_u = db.session.query(
        func.date_trunc(granularity, Usuario.fecha_registro).label("periodo"),
        func.count(Usuario.id).label("total"),
    )
    if unidad_id:
        q_u = q_u.filter(Usuario.unidad_id == unidad_id)
    rows_u = q_u.group_by("periodo").order_by("periodo").all()

    # ── publicaciones nuevas ─────────────────────────────────────────────────
    q_p = db.session.query(
        func.date_trunc(granularity, PublicacionCambio.fecha_creacion).label("periodo"),
        func.count(PublicacionCambio.id).label("total"),
    ).filter(PublicacionCambio.es_sintetica.is_(False))
    if unidad_id:
        q_p = q_p.join(Usuario, Usuario.id == PublicacionCambio.usuario_id).filter(
            Usuario.unidad_id == unidad_id
        )
    rows_p = q_p.group_by("periodo").order_by("periodo").all()

    # ── publicaciones cerradas (para cálculo de activas acumuladas) ──────────
    q_pc = db.session.query(
        func.date_trunc(granularity, PublicacionCambio.fecha_cierre).label("periodo"),
        func.count(PublicacionCambio.id).label("total"),
    ).filter(
        PublicacionCambio.es_sintetica.is_(False),
        PublicacionCambio.fecha_cierre.isnot(None),
    )
    if unidad_id:
        q_pc = q_pc.join(Usuario, Usuario.id == PublicacionCambio.usuario_id).filter(
            Usuario.unidad_id == unidad_id
        )
    rows_pc = q_pc.group_by("periodo").order_by("periodo").all()

    # ── matches nuevos ───────────────────────────────────────────────────────
    q_m = db.session.query(
        func.date_trunc(granularity, MatchCambio.fecha_creacion).label("periodo"),
        func.count(distinct(MatchCambio.id)).label("total"),
    )
    if unidad_id:
        q_m = (
            q_m
            .join(MatchParticipacion, MatchParticipacion.match_id == MatchCambio.id)
            .join(PublicacionCambio, PublicacionCambio.id == MatchParticipacion.publicacion_id)
            .join(Usuario, Usuario.id == PublicacionCambio.usuario_id)
            .filter(Usuario.unidad_id == unidad_id)
        )
    rows_m = q_m.group_by("periodo").order_by("periodo").all()

    # ── confirmados ──────────────────────────────────────────────────────────
    q_c = db.session.query(
        func.date_trunc(granularity, MatchCambio.fecha_confirmacion_total).label("periodo"),
        func.count(distinct(MatchCambio.id)).label("total"),
    ).filter(
        MatchCambio.estado == "confirmado_total",
        MatchCambio.fecha_confirmacion_total.isnot(None),
    )
    if unidad_id:
        q_c = (
            q_c
            .join(MatchParticipacion, MatchParticipacion.match_id == MatchCambio.id)
            .join(PublicacionCambio, PublicacionCambio.id == MatchParticipacion.publicacion_id)
            .join(Usuario, Usuario.id == PublicacionCambio.usuario_id)
            .filter(Usuario.unidad_id == unidad_id)
        )
    rows_c = q_c.group_by("periodo").order_by("periodo").all()

    # ── clics "Me interesa" ──────────────────────────────────────────────────
    q_mi = db.session.query(
        func.date_trunc(granularity, Event.created_at).label("periodo"),
        func.count(Event.id).label("total"),
    ).filter(Event.event_type == "me_interesa")
    if unidad_id:
        q_mi = q_mi.join(Usuario, Usuario.id == Event.user_id).filter(
            Usuario.unidad_id == unidad_id
        )
    rows_mi = q_mi.group_by("periodo").order_by("periodo").all()

    # ── publicaciones eliminadas ─────────────────────────────────────────────
    q_e = db.session.query(
        func.date_trunc(granularity, AuditEliminacion.fecha).label("periodo"),
        func.count(AuditEliminacion.id).label("total"),
    )
    if unidad_id:
        q_e = q_e.filter(AuditEliminacion.unidad_id == unidad_id)
    rows_e = q_e.group_by("periodo").order_by("periodo").all()

    # ── planillas publicadas ─────────────────────────────────────────────────
    q_pp = db.session.query(
        func.date_trunc(granularity, Event.created_at).label("periodo"),
        func.count(Event.id).label("total"),
    ).filter(Event.event_type == "planilla_publicada")
    if unidad_id:
        q_pp = q_pp.join(Usuario, Usuario.id == Event.user_id).filter(
            Usuario.unidad_id == unidad_id
        )
    rows_pp = q_pp.group_by("periodo").order_by("periodo").all()

    d_u  = to_dict(rows_u)
    d_p  = to_dict(rows_p)
    d_pc = to_dict(rows_pc)
    d_m  = to_dict(rows_m)
    d_c  = to_dict(rows_c)
    d_mi = to_dict(rows_mi)
    d_e  = to_dict(rows_e)
    d_pp = to_dict(rows_pp)

    # Unión de todas las fechas con actividad
    all_dates = sorted(
        set(d_u) | set(d_p) | set(d_pc) | set(d_m) | set(d_c) | set(d_mi) | set(d_e) | set(d_pp)
    )

    # Activas acumuladas: suma corriente de (creadas - cerradas) por bucket
    all_delta_dates = sorted(set(d_p) | set(d_pc))
    i_delta = 0
    running_activas = 0
    d_activas = {}
    for d in all_dates:
        while i_delta < len(all_delta_dates) and all_delta_dates[i_delta] <= d:
            dd = all_delta_dates[i_delta]
            running_activas += d_p.get(dd, 0) - d_pc.get(dd, 0)
            i_delta += 1
        d_activas[d] = running_activas

    # ── Totales para los contadores ──────────────────────────────────────────
    if unidad_id:
        unidad_obj = db.session.get(Unidad, unidad_id)
        t_usuarios = Usuario.query.filter_by(unidad_id=unidad_id).count()
        t_hospitales = 1 if unidad_obj else 0
        t_unidades = 1 if unidad_obj else 0
        t_categorias = 1 if (unidad_obj and unidad_obj.categoria_id) else 0
        t_publicaciones = (
            PublicacionCambio.query.filter_by(es_sintetica=False)
            .join(Usuario, Usuario.id == PublicacionCambio.usuario_id)
            .filter(Usuario.unidad_id == unidad_id)
            .count()
        )
        t_oportunidades_3 = (
            PublicacionCambio.query.filter(
                PublicacionCambio.es_sintetica.is_(True),
                PublicacionCambio.sintetica_pub_intermedio_id.is_(None),
            )
            .join(Usuario, Usuario.id == PublicacionCambio.usuario_id)
            .filter(Usuario.unidad_id == unidad_id)
            .count()
        )
        t_oportunidades_4 = (
            PublicacionCambio.query.filter(
                PublicacionCambio.es_sintetica.is_(True),
                PublicacionCambio.sintetica_pub_intermedio_id.isnot(None),
            )
            .join(Usuario, Usuario.id == PublicacionCambio.usuario_id)
            .filter(Usuario.unidad_id == unidad_id)
            .count()
        )
        t_activas = (
            PublicacionCambio.query.filter(
                PublicacionCambio.es_sintetica.is_(False),
                PublicacionCambio.estado.in_(["abierta", "parcialmente_resuelta"]),
            )
            .join(Usuario, Usuario.id == PublicacionCambio.usuario_id)
            .filter(Usuario.unidad_id == unidad_id)
            .count()
        )
        t_matches = (
            db.session.query(func.count(distinct(MatchCambio.id)))
            .join(MatchParticipacion, MatchParticipacion.match_id == MatchCambio.id)
            .join(PublicacionCambio, PublicacionCambio.id == MatchParticipacion.publicacion_id)
            .join(Usuario, Usuario.id == PublicacionCambio.usuario_id)
            .filter(Usuario.unidad_id == unidad_id)
            .scalar() or 0
        )
        t_confirmados = (
            db.session.query(func.count(distinct(MatchCambio.id)))
            .filter(MatchCambio.estado == "confirmado_total")
            .join(MatchParticipacion, MatchParticipacion.match_id == MatchCambio.id)
            .join(PublicacionCambio, PublicacionCambio.id == MatchParticipacion.publicacion_id)
            .join(Usuario, Usuario.id == PublicacionCambio.usuario_id)
            .filter(Usuario.unidad_id == unidad_id)
            .scalar() or 0
        )
        t_eliminadas = AuditEliminacion.query.filter_by(unidad_id=unidad_id).count()
        t_planillas_publicadas = (
            db.session.query(func.count(distinct(PlanillaMes.usuario_id)))
            .join(Usuario, Usuario.id == PlanillaMes.usuario_id)
            .filter(PlanillaMes.publicada.is_(True), Usuario.unidad_id == unidad_id)
            .scalar() or 0
        )
        t_me_interesa = (
            db.session.query(func.count(Event.id))
            .filter(Event.event_type == "me_interesa")
            .join(Usuario, Usuario.id == Event.user_id)
            .filter(Usuario.unidad_id == unidad_id)
            .scalar() or 0
        )
    else:
        t_usuarios = Usuario.query.count()
        t_hospitales = Hospital.query.count()
        t_unidades = Unidad.query.count()
        t_categorias = Categoria.query.count()
        t_publicaciones = PublicacionCambio.query.filter_by(es_sintetica=False).count()
        t_oportunidades_3 = PublicacionCambio.query.filter(
            PublicacionCambio.es_sintetica.is_(True),
            PublicacionCambio.sintetica_pub_intermedio_id.is_(None),
        ).count()
        t_oportunidades_4 = PublicacionCambio.query.filter(
            PublicacionCambio.es_sintetica.is_(True),
            PublicacionCambio.sintetica_pub_intermedio_id.isnot(None),
        ).count()
        t_activas = PublicacionCambio.query.filter(
            PublicacionCambio.es_sintetica.is_(False),
            PublicacionCambio.estado.in_(["abierta", "parcialmente_resuelta"]),
        ).count()
        t_matches = MatchCambio.query.count()
        t_confirmados = MatchCambio.query.filter_by(estado="confirmado_total").count()
        t_eliminadas = AuditEliminacion.query.count()
        t_planillas_publicadas = (
            db.session.query(func.count(distinct(PlanillaMes.usuario_id)))
            .filter(PlanillaMes.publicada.is_(True))
            .scalar() or 0
        )
        t_me_interesa = (
            db.session.query(func.count(Event.id))
            .filter(Event.event_type == "me_interesa")
            .scalar() or 0
        )

    return jsonify({
        "labels": all_dates,
        "datasets": {
            "usuarios": [d_u.get(d, 0) for d in all_dates],
            "publicaciones": [d_p.get(d, 0) for d in all_dates],
            "activas": [d_activas.get(d, 0) for d in all_dates],
            "matches": [d_m.get(d, 0) for d in all_dates],
            "confirmados": [d_c.get(d, 0) for d in all_dates],
            "me_interesa": [d_mi.get(d, 0) for d in all_dates],
            "eliminadas": [d_e.get(d, 0) for d in all_dates],
            "planillas_publicadas": [d_pp.get(d, 0) for d in all_dates],
        },
        "totals": {
            "usuarios": t_usuarios,
            "hospitales": t_hospitales,
            "unidades": t_unidades,
            "categorias": t_categorias,
            "publicaciones": t_publicaciones,
            "oportunidades_3": t_oportunidades_3,
            "oportunidades_4": t_oportunidades_4,
            "activas": t_activas,
            "matches": t_matches,
            "confirmados": t_confirmados,
            "eliminadas": t_eliminadas,
            "planillas_publicadas": t_planillas_publicadas,
            "me_interesa": t_me_interesa,
        },
    })
