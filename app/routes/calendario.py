import calendar
from datetime import date

from flask import Blueprint, abort, redirect, render_template, request, session, url_for
from flask_babel import _
from flask_login import login_required, current_user
from sqlalchemy.orm import contains_eager, joinedload, selectinload

from app.extensions import db
from app.models import PublicacionCambio, TurnoAceptado, TurnoCedido, Unidad, Usuario
from app.models.franja_horaria import FranjaHoraria
from app.routes.main import _cargar_sint_info, _junte_info, _pub_js_data
from app.services.calendario_mercado import (
    CUALQUIER_FRANJA,
    colores_por_clave,
    construir_calendario_mes,
    construir_semanas_juntes,
    preparar_celdas_mes,
    preparar_semanas_juntes,
    resumen_publicaciones,
)
from app.services.unidad_usuario import categoria_en_unidad, unidad_activa_o_403, unidades_de

bp = Blueprint("calendario", __name__, url_prefix="/calendario")

MODOS_VALIDOS = ("ofertas", "peticiones", "juntes")


@bp.route("/")
@login_required
def index():
    hoy = date.today()
    anyo = request.args.get("anyo", hoy.year, type=int)
    mes = request.args.get("mes", hoy.month, type=int)
    modo = request.args.get("modo", "ofertas")
    if modo not in MODOS_VALIDOS:
        modo = "ofertas"

    unidad_id = request.args.get("unidad_id", type=int)
    unidad_activa = unidad_activa_o_403(current_user, unidad_id)

    prev_mes = mes - 1 if mes > 1 else 12
    prev_anyo = anyo if mes > 1 else anyo - 1
    next_mes = mes + 1 if mes < 12 else 1
    next_anyo = anyo if mes < 12 else anyo + 1

    contexto = dict(
        anyo=anyo, mes=mes, modo=modo, hoy=hoy,
        prev_anyo=prev_anyo, prev_mes=prev_mes,
        next_anyo=next_anyo, next_mes=next_mes,
        unidad_activa=unidad_activa,
        unidades=unidades_de(current_user),
    )

    cat_id = categoria_en_unidad(current_user, unidad_activa).id
    grupo_id = unidad_activa.grupo_intercambio_id

    if modo == "juntes":
        semanas = preparar_semanas_juntes(
            construir_semanas_juntes(current_user, anyo, mes,
                                     categoria_id=cat_id, grupo_id=grupo_id),
            mes,
        )
        return render_template("calendario/calendario.html", semanas=semanas, **contexto)

    _primer_dia_semana, num_dias = calendar.monthrange(anyo, mes)
    dias = [date(anyo, mes, d) for d in range(1, num_dias + 1)]

    calendario_mes = construir_calendario_mes(
        current_user, anyo, mes, modo,
        current_user.mostrar_oportunidad_3, current_user.mostrar_oportunidad_4,
        categoria_id=cat_id, grupo_id=grupo_id,
    )

    franjas = (
        FranjaHoraria.query
        .filter_by(grupo_intercambio_id=grupo_id)
        .order_by(FranjaHoraria.hora_inicio)
        .all()
    )
    celdas = preparar_celdas_mes(dias, calendario_mes, franjas)

    claves_usadas = {clave for franjas_dia in calendario_mes.values() for clave in franjas_dia}
    nombre_franja_por_id = {f.id: f.nombre for f in franjas}
    nombre_franja_por_clave = {
        str(clave): (_("Cualquiera") if clave == CUALQUIER_FRANJA else nombre_franja_por_id.get(clave, "?"))
        for clave in claves_usadas
    }
    color_franja_por_clave = colores_por_clave(claves_usadas, franjas)

    datos_mes = {
        dia.isoformat(): {str(clave): ids for clave, ids in franjas_dia.items()}
        for dia, franjas_dia in calendario_mes.items()
    }

    pub_ids = {pid for franjas_dia in calendario_mes.values() for ids in franjas_dia.values() for pid in ids}
    datos_publicaciones = {
        str(p["id"]): {
            "usuario_nombre": p["usuario_nombre"],
            "contraoferta": p["contraoferta"],
            "contraoferta_prefijo": p["contraoferta_prefijo"],
            "contraoferta_capsulas": p["contraoferta_capsulas"],
            "contraoferta_sufijo": p["contraoferta_sufijo"],
        }
        for p in resumen_publicaciones(pub_ids, modo)
    }

    return render_template(
        "calendario/calendario.html",
        dias=dias,
        celdas=celdas,
        nombre_franja_por_clave=nombre_franja_por_clave,
        color_franja_por_clave=color_franja_por_clave,
        datos_mes=datos_mes,
        datos_publicaciones=datos_publicaciones,
        CUALQUIER_FRANJA=CUALQUIER_FRANJA,
        **contexto,
    )


@bp.get("/publicacion/<int:pub_id>")
@login_required
def panel_publicacion(pub_id):
    """Fragmento HTML con el detalle completo de una publicación (sin
    envoltorio de página), para inyectarlo en el panel de drill-down del
    calendario sin navegar a Buscar cambios."""
    unidad_id = request.args.get("unidad_id", type=int)
    unidad_activa = unidad_activa_o_403(current_user, unidad_id)
    categoria_id = categoria_en_unidad(current_user, unidad_activa).id
    grupo_id = unidad_activa.grupo_intercambio_id

    pub = (
        PublicacionCambio.query
        .join(Usuario, PublicacionCambio.usuario_id == Usuario.id)
        .join(Unidad, Usuario.unidad_id == Unidad.id)
        .filter(
            PublicacionCambio.id == pub_id,
            PublicacionCambio.estado.in_(["abierta", "parcialmente_resuelta"]),
            PublicacionCambio.usuario_id != current_user.id,
            Usuario.categoria_id == categoria_id,
            Unidad.grupo_intercambio_id == grupo_id,
        )
        .options(
            contains_eager(PublicacionCambio.usuario),
            selectinload(PublicacionCambio.turnos_cedidos).joinedload(TurnoCedido.franja_horaria),
            selectinload(PublicacionCambio.turnos_aceptados).joinedload(TurnoAceptado.franja_horaria),
        )
        .first()
    )
    if pub is None:
        abort(404)

    ji = _junte_info(pub) if pub.tipo == "junte" else None
    si = _cargar_sint_info([pub]).get(pub.id) if pub.es_sintetica else None

    franjas = (
        FranjaHoraria.query
        .filter_by(grupo_intercambio_id=grupo_id)
        .order_by(FranjaHoraria.hora_inicio)
        .all()
    )

    return render_template(
        "calendario/_panel_publicacion.html",
        pub=pub, ji=ji, si=si, pub_js_data=_pub_js_data(pub),
        franjas_js=[{"id": f.id, "nombre": f.nombre} for f in franjas],
    )


@bp.post("/preferencias")
@login_required
def guardar_preferencias():
    """Guarda la preferencia de mostrar/ocultar oportunidades a 3 y a 4 bandas
    en el calendario. Checkboxes ausentes en el form == desactivado."""
    current_user.mostrar_oportunidad_3 = "mostrar_oportunidad_3" in request.form
    current_user.mostrar_oportunidad_4 = "mostrar_oportunidad_4" in request.form
    db.session.commit()

    anyo = request.form.get("anyo", type=int)
    mes = request.form.get("mes", type=int)
    modo = request.form.get("modo", "ofertas")
    if modo not in MODOS_VALIDOS:
        modo = "ofertas"
    unidad_id = session.get("unidad_activa_id")
    return redirect(url_for("calendario.index", anyo=anyo, mes=mes, modo=modo, unidad_id=unidad_id))
