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
    crear_usuario, manyana, tarde = _setup(db, sufijo)
    claudia = crear_usuario(f"Claudia{sufijo}", f"claudia{sufijo}@h.es")
    juan = crear_usuario(f"Juan{sufijo}", f"juan{sufijo}@h.es")
    documento = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja_id=manyana.id,
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
