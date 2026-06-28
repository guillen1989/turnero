from app.extensions import db
from app.models.planilla import CompatibilidadPlanilla
from app.services.compatibilidad_planilla import compatibilidad_para_cedido


def calcular_y_guardar_compatibilidad(pub):
    """Calcula y persiste la compatibilidad de planilla para una publicación.

    Agrega compañeros compatibles de todos los cedidos. Un compañero que
    libra en alguna fecha se almacena como 'libre' (tiene prioridad sobre
    'compatible').  Sólo crea entradas si hay compañeros realmente disponibles.
    """
    users_libres: set[int] = set()
    users_compat: set[int] = set()

    for tc in pub.turnos_cedidos:
        if tc.franja_horaria_id is None:
            continue
        fh = tc.franja_horaria
        resultado = compatibilidad_para_cedido(
            pub.usuario, tc.fecha, fh.hora_inicio, fh.hora_fin
        )
        users_libres.update(u.id for u in resultado.libres)
        users_compat.update(u.id for u in resultado.compatibles)

    all_users: dict[int, str] = {uid: "libre" for uid in users_libres}
    for uid in users_compat:
        if uid not in all_users:
            all_users[uid] = "compatible"

    CompatibilidadPlanilla.query.filter_by(publicacion_id=pub.id).delete()

    for uid, tipo in all_users.items():
        db.session.add(CompatibilidadPlanilla(
            publicacion_id=pub.id,
            usuario_id=uid,
            tipo=tipo,
        ))

    db.session.commit()


def actualizar_compat_tras_publicar_planilla(usuario, anyo: int, mes: int):
    """Al publicar la planilla de un mes, recalcula la compatibilidad de las
    publicaciones propias que tienen cedidos en ese mes.
    """
    from sqlalchemy import extract
    from app.models import PublicacionCambio, TurnoCedido

    pubs = (
        PublicacionCambio.query
        .filter_by(usuario_id=usuario.id, es_sintetica=False)
        .filter(PublicacionCambio.estado.in_(["abierta", "parcialmente_resuelta"]))
        .join(TurnoCedido, TurnoCedido.publicacion_id == PublicacionCambio.id)
        .filter(
            extract("year",  TurnoCedido.fecha) == anyo,
            extract("month", TurnoCedido.fecha) == mes,
        )
        .distinct()
        .all()
    )

    for pub in pubs:
        calcular_y_guardar_compatibilidad(pub)
