from urllib.parse import quote as _urlquote

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import and_, exists, extract, or_
from sqlalchemy.orm import contains_eager, joinedload, selectinload

from app.extensions import db
from app.models import BusquedaGuardada, CompatibilidadPlanilla, FranjaHoraria, MatchCambio, MatchParticipacion, Notificacion, PublicacionCambio, TurnoCedido, TurnoAceptado, Unidad, Usuario
from app.services.caducidad import caducar_publicaciones_expiradas
from app.services.junte_semanal import calcular_distribucion, resumen_textual

bp = Blueprint("main", __name__)


def _junte_info(pub):
    """Para una publicación de tipo junte, devuelve número de noches, días y semana."""
    lunes, trabaja, libra, num_noches = calcular_distribucion(pub)
    trabaja_str, libra_str = resumen_textual(trabaja, libra)

    return {
        'num_noches':  num_noches,
        'semana_str':  lunes.strftime('%d/%m/%Y') if lunes else '',
        'trabaja_str': trabaja_str,
        'libra_str':   libra_str,
    }


@bp.app_template_filter("urlquote")
def urlquote_filter(s):
    return _urlquote(s, safe="")

@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@bp.get("/como-funciona")
@login_required
def como_funciona():
    if not current_user.onboarding_visto and not current_user.es_demo:
        current_user.onboarding_visto = True
        db.session.commit()
    return render_template("main/como_funciona.html")


def _mi_participacion(match, usuario_id):
    return next((p for p in match.participaciones if p.publicacion.usuario_id == usuario_id), None)


def _otras_participaciones(match, usuario_id):
    return [p for p in match.participaciones if p.publicacion.usuario_id != usuario_id]


def _calcular_trabajas(match):
    """Para cada participación devuelve un dict {fecha, franja} del turno que trabaja,
    o None si no trabaja nada (coincidencia parcial).

    Regla: en el ciclo A→B→C→A cada participante trabaja el turno cedido del
    participante anterior.  Para coincidencias parciales (regalo/petición), quien
    tiene turno_aceptado ya lo trabaja explícitamente; quien no tiene ningún
    'trabaja' recibe None.
    """
    partes = sorted(match.participaciones, key=lambda p: p.id)
    n = len(partes)
    trabajas = {}
    for i, part in enumerate(partes):
        if part.turno_aceptado:
            ta = part.turno_aceptado
            cualquier = ta.cualquier_franja
            trabajas[part.id] = {
                "fecha": ta.fecha.strftime("%d/%m/%Y"),
                "franja": None if cualquier else ta.franja_horaria.nombre,
            }
        elif part.turno_cedido:
            prev = partes[(i - 1) % n]
            tc = prev.turno_cedido  # None para coincidencias parciales
            trabajas[part.id] = (
                {"fecha": tc.fecha.strftime("%d/%m/%Y"), "franja": tc.franja_horaria.nombre}
                if tc else None
            )
        else:
            trabajas[part.id] = None
    return trabajas


def _partners_confirmados(usuario_id):
    """Devuelve dict {pub_id: nombres_partners} para publicaciones con match confirmado_total."""
    raw = (
        MatchCambio.query
        .join(MatchParticipacion, MatchCambio.id == MatchParticipacion.match_id)
        .join(PublicacionCambio, MatchParticipacion.publicacion_id == PublicacionCambio.id)
        .filter(
            PublicacionCambio.usuario_id == usuario_id,
            MatchCambio.estado == "confirmado_total",
        )
        .options(
            selectinload(MatchCambio.participaciones)
            .joinedload(MatchParticipacion.publicacion)
            .joinedload(PublicacionCambio.usuario)
        )
        .distinct()
        .all()
    )
    result = {}
    for match in raw:
        mi = _mi_participacion(match, usuario_id)
        otras = _otras_participaciones(match, usuario_id)
        if mi and otras:
            nombres = " y ".join(p.publicacion.usuario.nombre for p in otras)
            result[mi.publicacion_id] = nombres
    return result


def _query_publicaciones_con_match(usuario_id, estados_match):
    """Publicaciones del usuario que tienen algún match en alguno de los estados dados."""
    return (
        PublicacionCambio.query
        .join(MatchParticipacion, PublicacionCambio.id == MatchParticipacion.publicacion_id)
        .join(MatchCambio, MatchParticipacion.match_id == MatchCambio.id)
        .filter(
            PublicacionCambio.usuario_id == usuario_id,
            MatchCambio.estado.in_(estados_match),
        )
        .distinct()
    )


def _query_con_match_activo(usuario_id):
    return _query_publicaciones_con_match(usuario_id, ["propuesto", "confirmado_parcial"])


def _query_compatibles(usuario_id):
    return _query_publicaciones_con_match(usuario_id, ["propuesto"])


def _query_pendientes(usuario_id):
    return _query_publicaciones_con_match(usuario_id, ["confirmado_parcial"])


def _matches_para_tab(usuario_id, estado_match):
    """Devuelve lista de (match, mi_participacion, [otras_participaciones]) para un estado."""
    raw = (
        MatchCambio.query
        .join(MatchParticipacion, MatchCambio.id == MatchParticipacion.match_id)
        .join(PublicacionCambio, MatchParticipacion.publicacion_id == PublicacionCambio.id)
        .filter(
            PublicacionCambio.usuario_id == usuario_id,
            MatchCambio.estado == estado_match,
        )
        .options(
            selectinload(MatchCambio.participaciones)
            .joinedload(MatchParticipacion.publicacion)
            .joinedload(PublicacionCambio.usuario)
        )
        .distinct()
        .all()
    )
    resultado = []
    for match in raw:
        mi = _mi_participacion(match, usuario_id)
        otras = _otras_participaciones(match, usuario_id)
        if mi and otras:
            resultado.append((match, mi, otras, _calcular_trabajas(match)))
    return resultado


_ESTADOS_DASHBOARD = {
    "activos": None,   # handled specially
    "pendiente": None,  # handled specially
    "confirmada": ["confirmada"],
    "caducada": ["caducada"],
}

# Backward-compat aliases: old URL params map to the new state name
_ALIASES_ESTADO = {"compatible": "activos", "abierta": "activos"}


def _conteos_tabs(usuario_id):
    from sqlalchemy import func, select as sa_select
    activos_subq = (
        _query_con_match_activo(usuario_id)
        .with_entities(PublicacionCambio.id)
        .subquery()
    )
    activos_select = sa_select(activos_subq)

    abiertas = (
        PublicacionCambio.query
        .filter_by(usuario_id=usuario_id)
        .filter(PublicacionCambio.estado.in_(["abierta", "parcialmente_resuelta"]))
        .filter(~PublicacionCambio.id.in_(activos_select))
        .count()
    )

    est_rows = db.session.execute(
        sa_select(PublicacionCambio.estado, func.count(PublicacionCambio.id).label("n"))
        .where(
            PublicacionCambio.usuario_id == usuario_id,
            PublicacionCambio.estado.in_(["confirmada", "caducada"]),
        )
        .group_by(PublicacionCambio.estado)
    ).all()
    est_counts = {row.estado: row.n for row in est_rows}

    # Matches confirmado_total cuya publicación sigue parcialmente_resuelta
    # (no se contabilizan aún en est_counts["confirmada"])
    matches_parciales_n = (
        MatchCambio.query
        .join(MatchParticipacion, MatchCambio.id == MatchParticipacion.match_id)
        .join(PublicacionCambio, MatchParticipacion.publicacion_id == PublicacionCambio.id)
        .filter(
            PublicacionCambio.usuario_id == usuario_id,
            MatchCambio.estado == "confirmado_total",
            PublicacionCambio.estado == "parcialmente_resuelta",
        )
        .distinct()
        .count()
    )

    return {
        "activos": len(_matches_para_tab(usuario_id, "propuesto")) + abiertas,
        "pendiente": _query_pendientes(usuario_id).count(),
        "confirmada": est_counts.get("confirmada", 0) + matches_parciales_n,
        "caducada": est_counts.get("caducada", 0),
    }


@bp.get("/")
def index():
    if current_user.is_authenticated:
        caducar_publicaciones_expiradas()
        estado_filtro = request.args.get("estado", "activos")
        estado_filtro = _ALIASES_ESTADO.get(estado_filtro, estado_filtro)
        if estado_filtro not in _ESTADOS_DASHBOARD:
            estado_filtro = "activos"

        oportunidades_3 = []
        avisos_interes = []
        compat_por_pub: dict = {}
        mostrar_nombres_por_pub: dict = {}

        if estado_filtro == "activos":
            from sqlalchemy import select as sa_select
            activos_subq = (
                _query_con_match_activo(current_user.id)
                .with_entities(PublicacionCambio.id)
                .subquery()
            )
            publicaciones = (
                PublicacionCambio.query
                .filter_by(usuario_id=current_user.id)
                .filter(PublicacionCambio.estado.in_(["abierta", "parcialmente_resuelta"]))
                .filter(PublicacionCambio.es_sintetica.is_(False))
                .filter(~PublicacionCambio.id.in_(sa_select(activos_subq)))
                .order_by(PublicacionCambio.fecha_creacion.desc())
                .all()
            )
            matches = _matches_para_tab(current_user.id, "propuesto")
            Notificacion.query.filter_by(
                usuario_id=current_user.id, tipo="nuevo_match", leida=False
            ).update({"leida": True})
            db.session.commit()

            mis_pubs_ids = [
                row[0] for row in db.session.execute(
                    sa_select(PublicacionCambio.id).where(
                        PublicacionCambio.usuario_id == current_user.id,
                        PublicacionCambio.estado.in_(["abierta", "parcialmente_resuelta"]),
                        PublicacionCambio.es_sintetica.is_(False),
                    )
                ).all()
            ]
            if mis_pubs_ids:
                oportunidades_3 = (
                    PublicacionCambio.query
                    .filter(
                        PublicacionCambio.es_sintetica.is_(True),
                        PublicacionCambio.estado == "abierta",
                        or_(
                            PublicacionCambio.sintetica_pub_a_id.in_(mis_pubs_ids),
                            PublicacionCambio.sintetica_pub_b_id.in_(mis_pubs_ids),
                        )
                    )
                    .options(
                        selectinload(PublicacionCambio.turnos_cedidos).joinedload(TurnoCedido.franja_horaria),
                        selectinload(PublicacionCambio.turnos_aceptados).joinedload(TurnoAceptado.franja_horaria),
                    )
                    .all()
                )
            avisos_interes = (
                Notificacion.query
                .filter_by(usuario_id=current_user.id, tipo="aviso_oportunidad_3")
                .options(db.joinedload(Notificacion.publicacion).joinedload(PublicacionCambio.usuario))
                .order_by(Notificacion.fecha.desc())
                .all()
            )

            if publicaciones:
                pub_ids = [p.id for p in publicaciones]
                entries = (
                    CompatibilidadPlanilla.query
                    .filter(CompatibilidadPlanilla.publicacion_id.in_(pub_ids))
                    .options(joinedload(CompatibilidadPlanilla.usuario))
                    .all()
                )
                for entry in entries:
                    grp = compat_por_pub.setdefault(
                        entry.publicacion_id, {"libres": [], "compatibles": []}
                    )
                    key = "libres" if entry.tipo == "libre" else "compatibles"
                    grp[key].append(entry.usuario)

                meses_publicados = {
                    (pm.anyo, pm.mes)
                    for pm in current_user.planillas_mes.all()
                    if pm.publicada
                }
                for pub in publicaciones:
                    cedidos_meses = {
                        (tc.fecha.year, tc.fecha.month) for tc in pub.turnos_cedidos
                    }
                    mostrar_nombres_por_pub[pub.id] = bool(cedidos_meses & meses_publicados)

        elif estado_filtro == "pendiente":
            publicaciones = []
            matches = _matches_para_tab(current_user.id, "confirmado_parcial")
        elif estado_filtro == "confirmada":
            publicaciones = (
                PublicacionCambio.query
                .filter_by(usuario_id=current_user.id)
                .filter(PublicacionCambio.estado == "confirmada")
                .filter(PublicacionCambio.es_sintetica.is_(False))
                .order_by(PublicacionCambio.fecha_creacion.desc())
                .all()
            )
            # Matches confirmado_total cuya pub aún no está del todo resuelta
            all_confirmados = _matches_para_tab(current_user.id, "confirmado_total")
            matches = [
                (m, mi, otras, t) for m, mi, otras, t in all_confirmados
                if mi.publicacion.estado == "parcialmente_resuelta"
            ]
        else:
            estados = _ESTADOS_DASHBOARD[estado_filtro]
            publicaciones = (
                PublicacionCambio.query
                .filter_by(usuario_id=current_user.id)
                .filter(PublicacionCambio.estado.in_(estados))
                .filter(PublicacionCambio.es_sintetica.is_(False))
                .order_by(PublicacionCambio.fecha_creacion.desc())
                .all()
            )
            matches = []

        conteos = _conteos_tabs(current_user.id)
        partners = _partners_confirmados(current_user.id) if estado_filtro == "confirmada" else {}
        junte_info = {pub.id: _junte_info(pub) for pub in publicaciones if pub.tipo == 'junte'}
        sint_info = _cargar_sint_info(oportunidades_3)
        return render_template(
            "main/dashboard.html",
            publicaciones=publicaciones,
            matches=matches,
            estado_filtro=estado_filtro,
            conteos=conteos,
            partners=partners,
            junte_info=junte_info,
            oportunidades_3=oportunidades_3,
            avisos_interes=avisos_interes,
            sint_info=sint_info,
            compat_por_pub=compat_por_pub,
            mostrar_nombres_por_pub=mostrar_nombres_por_pub,
        )
    demo_login_enabled = bool(current_app.config.get("DEMO_LOGIN_EMAIL"))
    return render_template("main/index.html", demo_login_enabled=demo_login_enabled)


@bp.get("/cambios")
@login_required
def cambios():
    mes = request.args.get("mes", type=int)
    dia = request.args.get("dia", type=int)
    nombre = request.args.get("usuario", "").strip()
    franja_id = request.args.get("franja", type=int)
    tipo = request.args.get("tipo", "").strip()
    tipo_fecha = request.args.get("tipo_fecha", "").strip()
    _TIPOS_VALIDOS = {"cambio", "regalo", "peticion", "junte", "cambio_dia", "sintetica"}
    if tipo not in _TIPOS_VALIDOS:
        tipo = ""
    if tipo_fecha not in {"cedido", "aceptado"}:
        tipo_fecha = ""

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
        .options(
            contains_eager(PublicacionCambio.usuario),
            selectinload(PublicacionCambio.turnos_cedidos)
            .joinedload(TurnoCedido.franja_horaria),
            selectinload(PublicacionCambio.turnos_aceptados)
            .joinedload(TurnoAceptado.franja_horaria),
        )
    )

    pub_id = request.args.get("pub_id", type=int)
    if pub_id:
        q = q.filter(PublicacionCambio.id == pub_id)

    if mes or dia or franja_id:
        cedido_parts = [TurnoCedido.publicacion_id == PublicacionCambio.id]
        aceptado_parts = [TurnoAceptado.publicacion_id == PublicacionCambio.id]
        if mes:
            cedido_parts.append(extract("month", TurnoCedido.fecha) == mes)
            aceptado_parts.append(extract("month", TurnoAceptado.fecha) == mes)
        if dia:
            cedido_parts.append(extract("day", TurnoCedido.fecha) == dia)
            aceptado_parts.append(extract("day", TurnoAceptado.fecha) == dia)
        if franja_id:
            cedido_parts.append(TurnoCedido.franja_horaria_id == franja_id)
            aceptado_parts.append(TurnoAceptado.franja_horaria_id == franja_id)
        if tipo_fecha == "cedido":
            q = q.filter(exists().where(and_(*cedido_parts)))
        elif tipo_fecha == "aceptado":
            q = q.filter(exists().where(and_(*aceptado_parts)))
        else:
            q = q.filter(or_(
                exists().where(and_(*cedido_parts)),
                exists().where(and_(*aceptado_parts)),
            ))
    if nombre:
        q = q.filter(Usuario.nombre.ilike(f"%{nombre}%"))
    if tipo == "sintetica":
        q = q.filter(PublicacionCambio.es_sintetica.is_(True))
    elif tipo:
        q = q.filter(PublicacionCambio.tipo == tipo, PublicacionCambio.es_sintetica.is_(False))

    publicaciones = q.distinct().order_by(PublicacionCambio.fecha_creacion.desc()).all()

    pub_js_data = {pub.id: _pub_js_data(pub) for pub in publicaciones}
    franjas_js = [{"id": f.id, "nombre": f.nombre} for f in franjas]
    junte_info = {pub.id: _junte_info(pub) for pub in publicaciones if pub.tipo == 'junte'}

    sint_info = _cargar_sint_info([p for p in publicaciones if p.es_sintetica])

    tab = request.args.get("tab", "resultados")
    busquedas = (
        BusquedaGuardada.query
        .filter_by(usuario_id=current_user.id)
        .order_by(BusquedaGuardada.creada_en.desc())
        .all()
    )

    return render_template("main/cambios.html", publicaciones=publicaciones,
                           mes=mes, dia=dia, nombre=nombre, franja_id=franja_id,
                           tipo=tipo, tipo_fecha=tipo_fecha,
                           franjas=franjas, pub_js_data=pub_js_data, franjas_js=franjas_js,
                           tab=tab, busquedas=busquedas, junte_info=junte_info,
                           sint_info=sint_info)


def _cargar_sint_info(sinteticas):
    """Devuelve {sint_id: {'pub_a': pub_a_obj, 'pub_b': pub_b_obj}} para la lista dada."""
    if not sinteticas:
        return {}
    pub_ids = set()
    for s in sinteticas:
        if s.sintetica_pub_a_id:
            pub_ids.add(s.sintetica_pub_a_id)
        if s.sintetica_pub_b_id:
            pub_ids.add(s.sintetica_pub_b_id)
    pubs_by_id = {
        p.id: p
        for p in PublicacionCambio.query
        .filter(PublicacionCambio.id.in_(pub_ids))
        .options(joinedload(PublicacionCambio.usuario))
        .all()
    }
    return {
        s.id: {
            "pub_a": pubs_by_id.get(s.sintetica_pub_a_id),
            "pub_b": pubs_by_id.get(s.sintetica_pub_b_id),
        }
        for s in sinteticas
    }


def _pub_js_data(pub):
    return {
        "id": pub.id,
        "tipo": pub.tipo,
        "autor": pub.usuario.nombre,
        "cedidos": [
            {
                "id": tc.id,
                "fecha": tc.fecha.strftime("%d/%m/%Y"),
                "franja": tc.franja_horaria.nombre if tc.franja_horaria_id is not None else None,
                "cualquierFranja": tc.franja_horaria_id is None,
            }
            for tc in pub.turnos_cedidos if tc.estado == "abierto"
        ],
        "aceptados": [
            {
                "id": ta.id,
                "fecha": ta.fecha.strftime("%d/%m/%Y"),
                "franja": ta.franja_horaria.nombre if not ta.cualquier_franja else None,
                "cualquierFranja": ta.cualquier_franja,
            }
            for ta in pub.turnos_aceptados
        ],
    }
