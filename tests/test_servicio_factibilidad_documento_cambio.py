from datetime import date, time
from app.extensions import db
from app.models import (
    Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria, Usuario,
    TurnoPlanilla, PlanillaMes, EstadoDiaPlanilla,
    DocumentoCambio, ParticipanteDocumentoCambio,
)
from app.services.documento_cambio import crear_documento_cambio
from app.services.factibilidad_documento_cambio import comprobar_factibilidad


def _setup(db, sufijo="a"):
    hospital = Hospital(nombre=f"Hospital {sufijo}")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    categoria = Categoria(nombre=f"Enfermería {sufijo}")
    unidad = Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo)
    manyana = FranjaHoraria(nombre="Mañana", hora_inicio=time(7, 0), hora_fin=time(15, 0), grupo_intercambio=grupo)
    tarde = FranjaHoraria(nombre="Tarde", hora_inicio=time(15, 0), hora_fin=time(22, 0), grupo_intercambio=grupo)
    db.session.add_all([categoria, unidad, manyana, tarde])
    db.session.commit()

    def crear_usuario(nombre, email):
        u = Usuario(nombre=nombre, email=email, unidad=unidad, categoria=categoria)
        u.set_password("pass")
        db.session.add(u)
        db.session.commit()
        return u

    return crear_usuario, manyana, tarde


def _publicar_mes(usuario, anyo, mes):
    db.session.add(PlanillaMes(usuario=usuario, anyo=anyo, mes=mes, publicada=True))
    db.session.commit()


def _crear_documento(db, sufijo):
    return _crear_documento_fechas(db, sufijo, date(2026, 7, 7), date(2026, 7, 28))


def _crear_documento_fechas(db, sufijo, cede_fecha, recibe_fecha):
    crear_usuario, manyana, tarde = _setup(db, sufijo)
    claudia = crear_usuario(f"Claudia{sufijo}", f"claudia{sufijo}@h.es")
    juan = crear_usuario(f"Juan{sufijo}", f"juan{sufijo}@h.es")
    documento = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=cede_fecha, turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=recibe_fecha, turno_recibe_franja_id=manyana.id,
    )
    return documento, claudia, juan, manyana, tarde


def _estado_y_motivos(documento):
    """Wrapper que extrae el estado del tuple devuelto por comprobar_factibilidad."""
    return comprobar_factibilidad(documento)[0]


def test_no_verificado_si_falta_planilla_publicada(db):
    documento, claudia, juan, manyana, tarde = _crear_documento(db, "a")
    # Ninguna planilla publicada.
    assert _estado_y_motivos(documento) == "no_verificado"


def test_no_verificado_si_solo_una_parte_tiene_planilla(db):
    documento, claudia, juan, manyana, tarde = _crear_documento(db, "b")
    _publicar_mes(claudia, 2026, 7)
    # Falta la de Juan.
    assert _estado_y_motivos(documento) == "no_verificado"


def test_factible_si_ambos_cumplen_su_parte(db):
    documento, claudia, juan, manyana, tarde = _crear_documento(db, "c")
    _publicar_mes(claudia, 2026, 7)
    _publicar_mes(juan, 2026, 7)

    # Claudia trabaja mañana el 7/7 (lo cede) y está libre el 28/7 (lo recibe).
    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 7), franja_horaria=manyana))
    # Juan trabaja mañana el 28/7 (lo cede) y está libre el 7/7 (lo recibe).
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 28), franja_horaria=manyana))
    db.session.commit()

    assert _estado_y_motivos(documento) == "factible"


def test_no_factible_si_alguien_no_trabaja_lo_que_dice_ceder(db):
    documento, claudia, juan, manyana, tarde = _crear_documento(db, "d")
    _publicar_mes(claudia, 2026, 7)
    _publicar_mes(juan, 2026, 7)
    # Claudia NO tiene turno de mañana el 7/7 -> no puede cederlo.
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 28), franja_horaria=manyana))
    db.session.commit()

    assert _estado_y_motivos(documento) == "no_factible"


def test_no_factible_si_alguien_no_esta_libre_para_lo_que_recibe(db):
    documento, claudia, juan, manyana, tarde = _crear_documento(db, "e")
    _publicar_mes(claudia, 2026, 7)
    _publicar_mes(juan, 2026, 7)
    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 7), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 28), franja_horaria=manyana))
    # Claudia está de vacaciones el 28/7, el día que recibiría el turno.
    db.session.add(EstadoDiaPlanilla(usuario=claudia, fecha=date(2026, 7, 28), tipo="vacaciones"))
    db.session.commit()

    assert _estado_y_motivos(documento) == "no_factible"


def test_no_factible_si_recibir_el_turno_supera_el_limite_de_dias_consecutivos(db):
    documento, claudia, juan, manyana, tarde = _crear_documento(db, "f")
    _publicar_mes(claudia, 2026, 7)
    _publicar_mes(juan, 2026, 7)
    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 7), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 28), franja_horaria=manyana))

    claudia.unidad.grupo_intercambio.limite_dias_consecutivos = 3
    # Claudia ya trabaja 26, 27, 29 y 30 de julio; recibir el turno del 28
    # completaría una racha de 5 días seguidos, por encima del límite de 3.
    for dia in (26, 27, 29, 30):
        db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, dia), franja_horaria=manyana))
    db.session.commit()

    assert _estado_y_motivos(documento) == "no_factible"


def test_factible_si_recibir_el_turno_no_supera_el_limite_de_dias_consecutivos(db):
    documento, claudia, juan, manyana, tarde = _crear_documento(db, "g")
    _publicar_mes(claudia, 2026, 7)
    _publicar_mes(juan, 2026, 7)
    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 7), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 28), franja_horaria=manyana))
    claudia.unidad.grupo_intercambio.limite_dias_consecutivos = 3
    db.session.commit()

    assert _estado_y_motivos(documento) == "factible"


def test_no_factible_si_el_turno_recibido_empieza_antes_de_las_14_tras_una_noche(db):
    documento, claudia, juan, manyana, tarde = _crear_documento(db, "h")
    _publicar_mes(claudia, 2026, 7)
    _publicar_mes(juan, 2026, 7)
    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 7), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 28), franja_horaria=manyana))

    noche = FranjaHoraria(
        nombre="Noche", hora_inicio=time(22, 0), hora_fin=time(6, 0),
        grupo_intercambio=claudia.unidad.grupo_intercambio,
    )
    db.session.add(noche)
    db.session.commit()
    # Claudia trabaja de noche el 27/7; el turno que recibiría el 28/7 es de
    # mañana (empieza a las 7:00, antes de las 14:00) -> viola el descanso.
    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 27), franja_horaria=noche))
    db.session.commit()

    assert _estado_y_motivos(documento) == "no_factible"


def test_factible_si_el_turno_recibido_empieza_a_partir_de_las_14_tras_una_noche(db):
    documento, claudia, juan, manyana, tarde = _crear_documento(db, "i")
    # Claudia recibe "Tarde" (empieza a las 15:00) en vez de "Mañana" el
    # 28/7 -- lo que cede Juan debe ser espejo de lo que recibe Claudia.
    documento.participantes[0].turno_recibe_franja_id = tarde.id
    documento.participantes[1].turno_cede_franja_id = tarde.id
    _publicar_mes(claudia, 2026, 7)
    _publicar_mes(juan, 2026, 7)
    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 7), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 28), franja_horaria=tarde))

    noche = FranjaHoraria(
        nombre="Noche", hora_inicio=time(22, 0), hora_fin=time(6, 0),
        grupo_intercambio=claudia.unidad.grupo_intercambio,
    )
    db.session.add(noche)
    db.session.commit()
    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 27), franja_horaria=noche))
    db.session.commit()

    assert _estado_y_motivos(documento) == "factible"


def test_factible_si_el_dia_cedido_forma_parte_de_la_racha_hacia_el_dia_recibido(db):
    # Reproduce un cambio en papel real: Claudia cede el 10/7 (turno que
    # deja de ser suyo en este mismo documento) y recibe el 13/7. Sin
    # descontar el día cedido de su propia racha, el 10/7 seguiría contando
    # como trabajado y superaría el límite -- pero al cederlo, ya no es su
    # turno y no debería contar.
    documento, claudia, juan, manyana, tarde = _crear_documento_fechas(
        db, "j", date(2026, 7, 10), date(2026, 7, 13)
    )
    _publicar_mes(claudia, 2026, 7)
    _publicar_mes(juan, 2026, 7)
    claudia.unidad.grupo_intercambio.limite_dias_consecutivos = 3

    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 10), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 11), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 12), franja_horaria=manyana))
    # Juan trabaja el 13/7 (lo cede) y está libre el 10/7 (lo recibe).
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 13), franja_horaria=manyana))
    db.session.commit()

    assert _estado_y_motivos(documento) == "factible"


def test_factible_si_el_dia_cedido_es_la_noche_anterior_al_dia_recibido(db):
    # Mismo principio que el test anterior, pero para el descanso nocturno:
    # Claudia cede la noche del 10/7 y recibiría "Mañana" el 11/7. Sin
    # descontar la noche cedida, parecería que rompe su propio descanso,
    # pero esa noche deja de ser suya en este mismo cambio.
    documento, claudia, juan, manyana, tarde = _crear_documento_fechas(
        db, "k", date(2026, 7, 10), date(2026, 7, 11)
    )
    noche = FranjaHoraria(
        nombre="Noche", hora_inicio=time(22, 0), hora_fin=time(6, 0),
        grupo_intercambio=claudia.unidad.grupo_intercambio,
    )
    db.session.add(noche)
    db.session.commit()
    documento.participantes[0].turno_cede_franja_id = noche.id
    documento.participantes[1].turno_recibe_franja_id = noche.id
    _publicar_mes(claudia, 2026, 7)
    _publicar_mes(juan, 2026, 7)

    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 10), franja_horaria=noche))
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 11), franja_horaria=manyana))
    db.session.commit()

    assert _estado_y_motivos(documento) == "factible"


# ── Tests nuevos: acumulación de motivos ──────────────────────────────────────


def test_comprobar_factibilidad_devuelve_motivos_cuando_no_factible(db):
    documento, claudia, juan, manyana, tarde = _crear_documento(db, "m1")
    _publicar_mes(claudia, 2026, 7)
    _publicar_mes(juan, 2026, 7)
    # Claudia no tiene el turno de mañana del 7/7 (no puede cederlo).
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 28), franja_horaria=manyana))
    db.session.commit()

    estado, motivos = comprobar_factibilidad(documento)
    assert estado == "no_factible"
    assert len(motivos) == 1
    assert "Claudia" in motivos[0]
    assert "Mañana" in motivos[0]
    assert "07/07/2026" in motivos[0]


def test_comprobar_factibilidad_acumula_varios_motivos_por_participante(db):
    documento, claudia, juan, manyana, tarde = _crear_documento(db, "m2")
    _publicar_mes(claudia, 2026, 7)
    _publicar_mes(juan, 2026, 7)
    # Ambos fallos de Claudia: no trabaja lo que dice ceder (Mañana 7/7),
    # y está de vacaciones el día que recibiría (28/7). Juan no falla nada.
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 28), franja_horaria=manyana))
    db.session.add(EstadoDiaPlanilla(usuario=claudia, fecha=date(2026, 7, 28), tipo="vacaciones"))
    db.session.commit()

    estado, motivos = comprobar_factibilidad(documento)
    assert estado == "no_factible"
    assert len(motivos) == 2
    assert any("Claudia" in m for m in motivos)
    assert any("vacaciones" not in m.lower() and "no esta libre" in m.lower() for m in motivos)


def test_comprobar_factibilidad_incluye_motivo_por_limite_consecutivos(db):
    documento, claudia, juan, manyana, tarde = _crear_documento(db, "m3")
    _publicar_mes(claudia, 2026, 7)
    _publicar_mes(juan, 2026, 7)
    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 7), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 28), franja_horaria=manyana))
    claudia.unidad.grupo_intercambio.limite_dias_consecutivos = 3
    for dia in (26, 27, 29, 30):
        db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, dia), franja_horaria=manyana))
    db.session.commit()

    estado, motivos = comprobar_factibilidad(documento)
    assert estado == "no_factible"
    assert len(motivos) >= 1
    limite_motivo = next(m for m in motivos if "consecutivos" in m.lower())
    assert "Claudia" in limite_motivo


def test_comprobar_factibilidad_incluye_motivo_por_descanso_nocturno(db):
    documento, claudia, juan, manyana, tarde = _crear_documento(db, "m4")
    _publicar_mes(claudia, 2026, 7)
    _publicar_mes(juan, 2026, 7)
    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 7), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 28), franja_horaria=manyana))
    noche = FranjaHoraria(
        nombre="Noche", hora_inicio=time(22, 0), hora_fin=time(6, 0),
        grupo_intercambio=claudia.unidad.grupo_intercambio,
    )
    db.session.add(noche)
    db.session.commit()
    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 27), franja_horaria=noche))
    db.session.commit()

    estado, motivos = comprobar_factibilidad(documento)
    assert estado == "no_factible"
    assert len(motivos) >= 1
    nocturno_motivo = next(m for m in motivos if "nocturno" in m.lower())
    assert "Claudia" in nocturno_motivo


def test_comprobar_factibilidad_motivos_vacio_cuando_factible(db):
    documento, claudia, juan, manyana, tarde = _crear_documento(db, "m5")
    _publicar_mes(claudia, 2026, 7)
    _publicar_mes(juan, 2026, 7)
    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 7), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 28), franja_horaria=manyana))
    db.session.commit()

    estado, motivos = comprobar_factibilidad(documento)
    assert estado == "factible"
    assert motivos == []


# ── Tests nuevos: overlay de documentos encadenados ──────────────────────────


def test_overlay_vacio_sin_dependencia(db):
    """Sin dependencia, comprobar_factibilidad no usa overlay: comportamiento
    idéntico al actual (compatible hacia atrás)."""
    documento, claudia, juan, manyana, tarde = _crear_documento(db, "ov1")
    _publicar_mes(claudia, 2026, 7)
    _publicar_mes(juan, 2026, 7)
    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 7), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 28), franja_horaria=manyana))
    db.session.commit()

    assert documento.depende_de_id is None
    estado, motivos = comprobar_factibilidad(documento)
    assert estado == "factible"


def test_overlay_con_dependencia_es_factible_gracias_al_overlay(db):
    """Documento hijo que por sí solo no sería factible (Juan no trabaja
    7/7) se vuelve factible porque el overlay del predecesor le da ese turno."""
    from app.models import DocumentoCambio

    crear_usuario, manyana, tarde = _setup(db, "ov2")
    claudia = crear_usuario("Claudiaov2", "claudiaov2@h.es")
    juan = crear_usuario("Juanov2", "juanov2@h.es")
    ana = crear_usuario("Anaov2", "anaov2@h.es")
    for u in (claudia, juan, ana):
        _publicar_mes(u, 2026, 7)

    # Planilla real: Claudia tiene 7/7, Juan tiene 14/7, Ana tiene 21/7
    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 7), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 14), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=ana, fecha=date(2026, 7, 21), franja_horaria=manyana))
    db.session.commit()

    # Documento predecesor: Claudia cede 7/7 ↔ Juan cede 14/7
    doc_predecesor = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 14), turno_recibe_franja_id=manyana.id,
    )
    doc_predecesor.estado = "completo"
    doc_predecesor.decision_supervisora = "pendiente"
    db.session.commit()
    # Overlay: Juan gana 7/7, Claudia gana 14/7

    # Documento hijo: Juan (cede 7/7, ganada en overlay) ↔ Ana (cede 21/7)
    documento_hijo = DocumentoCambio(
        creado_por=juan,
        unidad_id=juan.unidad_id,
        numero_unidad=99,
        depende_de_id=doc_predecesor.id,
    )
    db.session.add(documento_hijo)
    db.session.flush()
    documento_hijo.participantes.append(ParticipanteDocumentoCambio(
        usuario=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja=manyana,
        turno_recibe_fecha=date(2026, 7, 21), turno_recibe_franja=manyana,
    ))
    documento_hijo.participantes.append(ParticipanteDocumentoCambio(
        usuario=ana,
        turno_cede_fecha=date(2026, 7, 21), turno_cede_franja=manyana,
        turno_recibe_fecha=date(2026, 7, 7), turno_recibe_franja=manyana,
    ))
    db.session.commit()

    # Juan no tiene 7/7 en planilla real → sin overlay sería no_factible.
    # Pero con overlay, el predecesor le da 7/7 → factible.
    estado, motivos = comprobar_factibilidad(documento_hijo)
    assert estado == "factible", f"Esperaba factible, obtuve {estado}: {motivos}"


def test_overlay_removed_quita_turnos_cedidos_por_predecesor(db):
    """El overlay quita el turno que el predecesor cede, así que el hijo
    no puede volver a cederlo (el removed lo hace desaparecer)."""
    from app.models import DocumentoCambio, ParticipanteDocumentoCambio

    crear_usuario, manyana, tarde = _setup(db, "ov3")
    claudia = crear_usuario("Claudiaov3", "claudiaov3@h.es")
    juan = crear_usuario("Juanov3", "juanov3@h.es")
    _publicar_mes(claudia, 2026, 7)
    _publicar_mes(juan, 2026, 7)

    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 7), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 14), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 28), franja_horaria=manyana))
    db.session.commit()

    # Predecesor: Claudia cede 7/7 ↔ Juan cede 14/7
    doc_predecesor = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 14), turno_recibe_franja_id=manyana.id,
    )
    doc_predecesor.estado = "completo"
    doc_predecesor.decision_supervisora = "pendiente"
    db.session.commit()

    # Hijo: Juan intenta ceder 14/7 otra vez. En la planilla real lo tiene,
    # pero el overlay dice que lo perdió en el predecesor → no factible.
    documento_hijo = DocumentoCambio(
        creado_por=juan, unidad_id=juan.unidad_id, numero_unidad=99,
        depende_de_id=doc_predecesor.id,
    )
    db.session.add(documento_hijo)
    db.session.flush()
    documento_hijo.participantes.append(ParticipanteDocumentoCambio(
        usuario=juan,
        turno_cede_fecha=date(2026, 7, 14), turno_cede_franja=manyana,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja=manyana,
    ))
    # El compañero sería Claudia, que ya tiene 7/7 y 14/7...
    # Mejor: creamos un 3er usuario.
    ana = crear_usuario("Anaov3", "anaov3@h.es")
    _publicar_mes(ana, 2026, 7)
    db.session.add(TurnoPlanilla(usuario=ana, fecha=date(2026, 7, 28), franja_horaria=manyana))
    db.session.commit()

    documento_hijo.participantes.append(ParticipanteDocumentoCambio(
        usuario=ana,
        turno_cede_fecha=date(2026, 7, 28), turno_cede_franja=manyana,
        turno_recibe_fecha=date(2026, 7, 14), turno_recibe_franja=manyana,
    ))
    db.session.commit()

    estado, motivos = comprobar_factibilidad(documento_hijo)
    assert estado == "no_factible"
    assert any("Juan" in m and "14" in m for m in motivos)


def test_cadena_dos_niveles(db):
    """Cadena: doc C depende de B que depende de A. El overlay de C ve los
    deltas acumulados de B y A."""
    from app.models import DocumentoCambio, ParticipanteDocumentoCambio

    crear_usuario, manyana, tarde = _setup(db, "ov4")
    claudia = crear_usuario("Claudiaov4", "claudiaov4@h.es")
    juan = crear_usuario("Juanov4", "juanov4@h.es")
    ana = crear_usuario("Anaov4", "anaov4@h.es")
    luis = crear_usuario("Luisov4", "luisov4@h.es")
    for u in (claudia, juan, ana, luis):
        _publicar_mes(u, 2026, 7)

    # Planillas reales:
    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 7), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 14), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=ana, fecha=date(2026, 7, 21), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=luis, fecha=date(2026, 7, 28), franja_horaria=manyana))
    db.session.commit()

    # Doc A (nivel 1): Claudia(7/7) ↔ Juan(14/7)
    doc_a = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 14), turno_recibe_franja_id=manyana.id,
    )
    doc_a.estado = "completo"
    doc_a.decision_supervisora = "pendiente"
    # overlay de A: Juan gana 7/7, Claudia gana 14/7

    # Doc B (nivel 2): Juan(7/7, ganado en A) ↔ Ana(21/7)
    doc_b = DocumentoCambio(
        creado_por=juan, unidad_id=juan.unidad_id, numero_unidad=98,
        depende_de_id=doc_a.id,
    )
    db.session.add(doc_b)
    db.session.flush()
    doc_b.participantes.append(ParticipanteDocumentoCambio(
        usuario=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja=manyana,
        turno_recibe_fecha=date(2026, 7, 21), turno_recibe_franja=manyana,
    ))
    doc_b.participantes.append(ParticipanteDocumentoCambio(
        usuario=ana,
        turno_cede_fecha=date(2026, 7, 21), turno_cede_franja=manyana,
        turno_recibe_fecha=date(2026, 7, 7), turno_recibe_franja=manyana,
    ))
    doc_b.estado = "completo"
    doc_b.decision_supervisora = "pendiente"
    db.session.commit()
    # overlay de B: Ana gana 7/7, Juan gana 21/7
    # Pero como B depende de A, el overlay de C verá A+B acumulados:
    # added: Juan(7/7) de A, Claudia(14/7) de A, Ana(7/7) de B, Juan(21/7) de B
    # removed: Claudia(7/7) de A, Juan(14/7) de A, Juan(7/7) de B, Ana(21/7) de B

    # Doc C (nivel 3): Ana(7/7, ganado en B) ↔ Luis(28/7)
    # Ana no tiene 7/7 en planilla real, pero gracias a la cadena (B→A) sí.
    doc_c = DocumentoCambio(
        creado_por=ana, unidad_id=ana.unidad_id, numero_unidad=97,
        depende_de_id=doc_b.id,
    )
    db.session.add(doc_c)
    db.session.flush()
    doc_c.participantes.append(ParticipanteDocumentoCambio(
        usuario=ana,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja=manyana,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja=manyana,
    ))
    doc_c.participantes.append(ParticipanteDocumentoCambio(
        usuario=luis,
        turno_cede_fecha=date(2026, 7, 28), turno_cede_franja=manyana,
        turno_recibe_fecha=date(2026, 7, 7), turno_recibe_franja=manyana,
    ))
    db.session.commit()

    estado, motivos = comprobar_factibilidad(doc_c)
    assert estado == "factible", f"Esperaba factible, obtuve {estado}: {motivos}"
