from datetime import date, time
from app.extensions import db
from app.models import (
    Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria, Usuario,
    TurnoPlanilla, PlanillaMes, EstadoDiaPlanilla,
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


def test_no_verificado_si_falta_planilla_publicada(db):
    documento, claudia, juan, manyana, tarde = _crear_documento(db, "a")
    # Ninguna planilla publicada.
    assert comprobar_factibilidad(documento) == "no_verificado"


def test_no_verificado_si_solo_una_parte_tiene_planilla(db):
    documento, claudia, juan, manyana, tarde = _crear_documento(db, "b")
    _publicar_mes(claudia, 2026, 7)
    # Falta la de Juan.
    assert comprobar_factibilidad(documento) == "no_verificado"


def test_factible_si_ambos_cumplen_su_parte(db):
    documento, claudia, juan, manyana, tarde = _crear_documento(db, "c")
    _publicar_mes(claudia, 2026, 7)
    _publicar_mes(juan, 2026, 7)

    # Claudia trabaja mañana el 7/7 (lo cede) y está libre el 28/7 (lo recibe).
    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 7), franja_horaria=manyana))
    # Juan trabaja mañana el 28/7 (lo cede) y está libre el 7/7 (lo recibe).
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 28), franja_horaria=manyana))
    db.session.commit()

    assert comprobar_factibilidad(documento) == "factible"


def test_no_factible_si_alguien_no_trabaja_lo_que_dice_ceder(db):
    documento, claudia, juan, manyana, tarde = _crear_documento(db, "d")
    _publicar_mes(claudia, 2026, 7)
    _publicar_mes(juan, 2026, 7)
    # Claudia NO tiene turno de mañana el 7/7 -> no puede cederlo.
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 28), franja_horaria=manyana))
    db.session.commit()

    assert comprobar_factibilidad(documento) == "no_factible"


def test_no_factible_si_alguien_no_esta_libre_para_lo_que_recibe(db):
    documento, claudia, juan, manyana, tarde = _crear_documento(db, "e")
    _publicar_mes(claudia, 2026, 7)
    _publicar_mes(juan, 2026, 7)
    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 7), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 28), franja_horaria=manyana))
    # Claudia está de vacaciones el 28/7, el día que recibiría el turno.
    db.session.add(EstadoDiaPlanilla(usuario=claudia, fecha=date(2026, 7, 28), tipo="vacaciones"))
    db.session.commit()

    assert comprobar_factibilidad(documento) == "no_factible"


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

    assert comprobar_factibilidad(documento) == "no_factible"


def test_factible_si_recibir_el_turno_no_supera_el_limite_de_dias_consecutivos(db):
    documento, claudia, juan, manyana, tarde = _crear_documento(db, "g")
    _publicar_mes(claudia, 2026, 7)
    _publicar_mes(juan, 2026, 7)
    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 7), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 28), franja_horaria=manyana))
    claudia.unidad.grupo_intercambio.limite_dias_consecutivos = 3
    db.session.commit()

    assert comprobar_factibilidad(documento) == "factible"


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

    assert comprobar_factibilidad(documento) == "no_factible"


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

    assert comprobar_factibilidad(documento) == "factible"


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

    assert comprobar_factibilidad(documento) == "factible"


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

    assert comprobar_factibilidad(documento) == "factible"
