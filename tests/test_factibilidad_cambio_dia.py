"""Paso 5.1 del plan de cambios en el día: comprobar_factibilidad debe
verificar correctamente un DocumentoCambio cuyo turno cedido y recibido
caen el mismo día (distinta franja), sin distinguir ese caso del de un
cambio normal entre días distintos."""
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


def _crear_documento_cambio_dia(db, sufijo, dia):
    """Ana cede la Mañana de `dia` y recibe la Tarde del mismo `dia`."""
    crear_usuario, manyana, tarde = _setup(db, sufijo)
    ana = crear_usuario(f"Ana{sufijo}", f"ana{sufijo}@h.es")
    pedro = crear_usuario(f"Pedro{sufijo}", f"pedro{sufijo}@h.es")
    documento = crear_documento_cambio(
        creado_por=ana, companero=pedro,
        turno_cede_fecha=dia, turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=dia, turno_recibe_franja_id=tarde.id,
    )
    return documento, ana, pedro, manyana, tarde


def _estado(documento):
    return comprobar_factibilidad(documento)[0]


def test_factible_cambio_dia_si_ana_trabaja_la_manyana_y_esta_libre_la_tarde(db):
    dia = date(2026, 7, 15)
    documento, ana, pedro, manyana, tarde = _crear_documento_cambio_dia(db, "a", dia)
    _publicar_mes(ana, 2026, 7)
    _publicar_mes(pedro, 2026, 7)

    db.session.add(TurnoPlanilla(usuario=ana, fecha=dia, franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=pedro, fecha=dia, franja_horaria=tarde))
    db.session.commit()

    assert _estado(documento) == "factible"


def test_no_factible_cambio_dia_si_ana_no_trabaja_lo_que_cede(db):
    dia = date(2026, 7, 15)
    documento, ana, pedro, manyana, tarde = _crear_documento_cambio_dia(db, "b", dia)
    _publicar_mes(ana, 2026, 7)
    _publicar_mes(pedro, 2026, 7)
    # Ana no tiene turno de mañana ese día -> no puede cederlo.
    db.session.commit()

    assert _estado(documento) == "no_factible"


def test_no_factible_cambio_dia_si_ana_ya_trabaja_lo_que_recibe(db):
    dia = date(2026, 7, 15)
    documento, ana, pedro, manyana, tarde = _crear_documento_cambio_dia(db, "c", dia)
    _publicar_mes(ana, 2026, 7)
    _publicar_mes(pedro, 2026, 7)

    db.session.add(TurnoPlanilla(usuario=ana, fecha=dia, franja_horaria=manyana))
    # Ana ya tiene además la Tarde ese día (p. ej. doblaje excepcional ya
    # planificado): no está libre para recibirla de nuevo por el cambio.
    db.session.add(TurnoPlanilla(usuario=ana, fecha=dia, franja_horaria=tarde))
    db.session.commit()

    assert _estado(documento) == "no_factible"
