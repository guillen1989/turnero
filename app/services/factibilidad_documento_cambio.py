"""
Comprobación de factibilidad de una hoja de cambio contra las planillas
subidas: para cada participante, verifica que de verdad trabaja el turno
que dice ceder y que está libre para el turno que dice recibir.

Reutiliza las mismas reglas que el motor de compatibilidad de planilla
(app/services/compatibilidad_planilla.py) en vez de reinventarlas.
"""
from __future__ import annotations

from datetime import time, timedelta

from app.models import DocumentoCambio, TurnoPlanilla, EstadoDiaPlanilla
from app.services.planilla import tiene_mes_publicado
from app.services.compatibilidad_planilla import turnos_solapan


def _construir_overlay(documento, excluir_participante=None):
    """
    Construye un overlay del estado hipotético de las planillas a partir de:
    - la cadena de documentos predecesores aún pendientes de autorización, y
    - las propias filas de `documento.participantes` (necesario en un junte
      de varias noches, donde ceder/recibir una noche afecta a la racha de
      días consecutivos y al descanso nocturno de las otras noches del mismo
      documento -- las "noches hermanas").

    `excluir_participante`, si se indica, omite esa fila propia al construir
    el overlay: se usa al comprobar si esa misma fila cede/recibe lo que
    dice, para no comparar la fila contra su propia hipótesis (ver
    `comprobar_factibilidad`).

    Devuelve (added, removed) donde:
    - added:   set de (usuario_id, fecha, franja_id) que se añadirían
    - removed: set de (usuario_id, fecha, franja_id) que se quitarían
    """
    added = set()
    removed = set()
    visitados = set()

    cursor_id = documento.depende_de_id
    while cursor_id is not None:
        if cursor_id in visitados:
            break  # ciclo defensivo: no debería ocurrir, pero por si acaso
        visitados.add(cursor_id)

        predecesor = DocumentoCambio.query.get(cursor_id)
        if predecesor is None:
            break

        # Solo acumulamos deltas de predecesores que todavía no han sido
        # resueltos (ni autorizados ni denegados ni anulados).
        if (
            predecesor.estado == "completo"
            and predecesor.decision_supervisora == "pendiente"
            and not predecesor.anulado
        ):
            for p in predecesor.participantes:
                removed.add((p.usuario_id, p.turno_cede_fecha, p.turno_cede_franja_id))
                added.add((p.usuario_id, p.turno_recibe_fecha, p.turno_recibe_franja_id))

        cursor_id = predecesor.depende_de_id

    for p in documento.participantes:
        if p is excluir_participante:
            continue
        removed.add((p.usuario_id, p.turno_cede_fecha, p.turno_cede_franja_id))
        added.add((p.usuario_id, p.turno_recibe_fecha, p.turno_recibe_franja_id))

    return added, removed


def _aplica_overlay(usuario_id, fecha, franja_id, overlay):
    """
    Dado un overlay (added, removed), indica si el turno debe considerarse
    como presente (True), ausente (False) o None si no está en el overlay
    (consultar la BD real).
    """
    if overlay is None:
        return None
    added, removed = overlay
    key = (usuario_id, fecha, franja_id)
    if key in added:
        return True
    if key in removed:
        return False
    return None


def _cubre_periodo_nocturno(franja) -> bool:
    """True si el horario de la franja incluye algún instante entre las
    0:00 y las 6:00 (turnos de noche/nocturno de 12h que cruzan la
    medianoche, almacenados con hora_inicio > hora_fin)."""
    if franja.hora_inicio > franja.hora_fin:
        return franja.hora_fin > time(0, 0)
    return franja.hora_inicio < time(6, 0)


def _viola_descanso_nocturno(usuario, fecha, franja, fecha_cedida, overlay=None) -> bool:
    """Regla de descanso: ningún turno puede empezar antes de las 14:00 el
    día siguiente a un turno que cubra el periodo 0:00-6:00.

    `fecha_cedida` es el día que este mismo usuario cede en el mismo
    documento: si coincide con el día anterior o siguiente, ese turno deja
    de ser suyo con este cambio y no cuenta para la regla."""
    dia_anterior = fecha - timedelta(days=1)
    turnos_dia_anterior = [] if dia_anterior == fecha_cedida else _turnos_dia(
        usuario.id, dia_anterior, overlay
    )
    if franja.hora_inicio < time(14, 0) and any(
        _cubre_periodo_nocturno(t.franja_horaria) for t in turnos_dia_anterior
    ):
        return True

    if _cubre_periodo_nocturno(franja):
        dia_siguiente = fecha + timedelta(days=1)
        turnos_dia_siguiente = [] if dia_siguiente == fecha_cedida else _turnos_dia(
            usuario.id, dia_siguiente, overlay
        )
        if any(t.franja_horaria.hora_inicio < time(14, 0) for t in turnos_dia_siguiente):
            return True

    return False


def _turnos_dia(usuario_id, fecha, overlay):
    """
    Devuelve la lista de turnos efectivos para un usuario en una fecha,
    aplicando el overlay si está presente. Si no hay overlay, consulta
    la base de datos directamente.
    """
    if overlay is None:
        return TurnoPlanilla.query.filter_by(usuario_id=usuario_id, fecha=fecha).all()

    added, removed = overlay
    # Empezamos con los turnos reales y aplicamos los deltas del overlay.
    turnos_reales = TurnoPlanilla.query.filter_by(usuario_id=usuario_id, fecha=fecha).all()
    resultado = []
    for t in turnos_reales:
        if (usuario_id, fecha, t.franja_horaria_id) not in removed:
            resultado.append(t)

    # Añadimos los turnos que vienen del overlay y no están ya.
    ids_presentes = {t.franja_horaria_id for t in resultado}
    for (uid, f, fid) in added:
        if uid == usuario_id and f == fecha and fid not in ids_presentes:
            # Creamos un objeto ligero con la info mínima necesaria.
            from app.models import FranjaHoraria
            franja = FranjaHoraria.query.get(fid)
            if franja is not None:
                resultado.append(TurnoPlanilla(
                    usuario_id=usuario_id, fecha=fecha, franja_horaria=franja
                ))
                ids_presentes.add(fid)

    return resultado


def _trabaja_el_dia(usuario, fecha, fecha_hipotetica, fecha_cedida, overlay=None) -> bool:
    if fecha == fecha_hipotetica:
        return True
    if fecha == fecha_cedida:
        return False
    estado = EstadoDiaPlanilla.query.filter_by(usuario_id=usuario.id, fecha=fecha).first()
    if estado is not None:
        # El overlay no afecta a los estados de día (vacaciones, baja, etc.)
        # ya que estos no son turnos — son ausencias planificadas.
        return False
    return len(_turnos_dia(usuario.id, fecha, overlay)) > 0


def _contar_dias_consecutivos_trabajados(usuario, fecha, fecha_cedida, overlay=None) -> int:
    """Cuenta la racha de días seguidos trabajados que incluiría `fecha`,
    contando hacia atrás y hacia delante a partir de los turnos/estados ya
    persistidos, asumiendo que `fecha` se trabajaría (turno recibido).

    `fecha_cedida` es el día que este mismo usuario cede en el mismo
    documento: aunque las planillas publicadas todavía lo marquen como
    trabajado, deja de serlo con este cambio, así que no debe contar."""
    total = 1
    cursor = fecha - timedelta(days=1)
    while _trabaja_el_dia(usuario, cursor, fecha, fecha_cedida, overlay):
        total += 1
        cursor -= timedelta(days=1)
    cursor = fecha + timedelta(days=1)
    while _trabaja_el_dia(usuario, cursor, fecha, fecha_cedida, overlay):
        total += 1
        cursor += timedelta(days=1)
    return total


def _viola_limite_dias_consecutivos(usuario, fecha, fecha_cedida, overlay=None) -> bool:
    limite = usuario.grupo_intercambio.limite_dias_consecutivos
    return _contar_dias_consecutivos_trabajados(usuario, fecha, fecha_cedida, overlay) > limite


def _trabaja_turno(usuario, fecha, franja, overlay=None) -> bool:
    resultado = _aplica_overlay(usuario.id, fecha, franja.id, overlay)
    if resultado is not None:
        return resultado
    return TurnoPlanilla.query.filter_by(
        usuario_id=usuario.id, fecha=fecha, franja_horaria_id=franja.id
    ).first() is not None


def _libre_para_turno(usuario, fecha, franja, overlay=None) -> bool:
    estado = EstadoDiaPlanilla.query.filter_by(usuario_id=usuario.id, fecha=fecha).first()
    if estado is not None:
        return estado.tipo == "libre"

    turnos_dia = _turnos_dia(usuario.id, fecha, overlay)
    if not turnos_dia:
        return True  # libre implícito

    return not any(
        turnos_solapan(
            franja.hora_inicio, franja.hora_fin,
            t.franja_horaria.hora_inicio, t.franja_horaria.hora_fin,
        )
        for t in turnos_dia
    )


def comprobar_factibilidad(documento) -> tuple[str, list[str]]:
    """
    Devuelve (estado, motivos) donde:
    - estado: uno de ESTADOS_FACTIBILIDAD.
    - motivos: lista de cadenas legibles explicando cada fallo detectado
      (una por participante, una por cada causa distinta), vacía si el
      cambio es factible o si la verificación aún no es posible.

    Estado 'no_verificado': falta la planilla publicada de algún
    participante para alguno de los meses implicados (no se puede comprobar).
    Estado 'no_factible': hay planilla de todos, pero alguna parte no
    trabaja lo que dice ceder, no está libre para lo que dice recibir, o
    recibir supondría violar el límite de días consecutivos o el descanso
    tras una noche (reglas de comprobación de la supervisora).
    Estado 'factible': cuadra todo.
    """
    motivos = []
    for p in documento.participantes:
        if not tiene_mes_publicado(p.usuario, p.turno_cede_fecha):
            return "no_verificado", []
        if not tiene_mes_publicado(p.usuario, p.turno_recibe_fecha):
            return "no_verificado", []

    # Overlay del estado hipotético de las planillas: cadena de predecesores
    # más las propias filas del documento (noches hermanas en un junte).
    overlay = _construir_overlay(documento)

    for p in documento.participantes:
        nombre = p.usuario.nombre or f"#{p.usuario_id}"
        fecha_str = p.turno_cede_fecha.strftime("%d/%m/%Y")
        # Al comprobar si esta fila cede/recibe lo que dice, excluimos su
        # propio delta del overlay: si no, siempre "quitaría" lo que cede y
        # "añadiría" lo que recibe contra sí misma (tautológico).
        overlay_sin_propia = _construir_overlay(documento, excluir_participante=p)
        if not _trabaja_turno(p.usuario, p.turno_cede_fecha, p.turno_cede_franja, overlay_sin_propia):
            motivos.append(
                f"{nombre}: no trabaja {p.turno_cede_franja.nombre} el {fecha_str}"
            )
        fecha_recibe_str = p.turno_recibe_fecha.strftime("%d/%m/%Y")
        if not _libre_para_turno(p.usuario, p.turno_recibe_fecha, p.turno_recibe_franja, overlay_sin_propia):
            motivos.append(
                f"{nombre}: no esta libre para {p.turno_recibe_franja.nombre} el {fecha_recibe_str}"
            )
        limite = p.usuario.grupo_intercambio.limite_dias_consecutivos
        if _viola_limite_dias_consecutivos(p.usuario, p.turno_recibe_fecha, p.turno_cede_fecha, overlay):
            racha = _contar_dias_consecutivos_trabajados(
                p.usuario, p.turno_recibe_fecha, p.turno_cede_fecha, overlay
            )
            motivos.append(
                f"{nombre}: recibir {p.turno_recibe_franja.nombre} el {fecha_recibe_str} "
                f"haría {racha} días consecutivos, superando el limite de {limite}"
            )
        if _viola_descanso_nocturno(
            p.usuario, p.turno_recibe_fecha, p.turno_recibe_franja, p.turno_cede_fecha, overlay
        ):
            motivos.append(
                f"{nombre}: recibir {p.turno_recibe_franja.nombre} el {fecha_recibe_str} "
                f"no respeta el descanso tras turno nocturno"
            )

    if motivos:
        return "no_factible", motivos
    return "factible", []
