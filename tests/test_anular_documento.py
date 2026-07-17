"""Tests del servicio de anulación de una hoja de cambio ya autorizada:
deshacer el volcado a planillas y, si el cambio venía de un match del
motor de matching, reabrir ese match y sus publicaciones."""
from datetime import date, time, timedelta

from app.extensions import db
from app.models import (
    Categoria, FranjaHoraria, GrupoIntercambio, Hospital, MatchCambio,
    MatchParticipacion, PublicacionCambio, TurnoAceptado, TurnoCedido,
    TurnoPlanilla, Unidad, Usuario,
)
from app.services.documento_cambio import (
    anular_documento, autorizar_documento, crear_documento_cambio,
    crear_documento_cambio_desde_match, firmar_documento, puede_anularse,
)

_FIRMA_PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAADklE"
    "QVR4nGNgGAWDEwAAAZoAAR2CVqgAAAAASUVORK5CYII="
)


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


def _fechas_futuras():
    hoy = date.today()
    return hoy + timedelta(days=10), hoy + timedelta(days=20)


def _documento_autorizado(db, sufijo):
    """Cambio manual (sin match) ya autorizado, con fechas futuras."""
    crear_usuario, manyana, tarde = _setup(db, sufijo)
    claudia = crear_usuario(f"Claudia{sufijo}", f"claudia{sufijo}@h.es")
    juan = crear_usuario(f"Juan{sufijo}", f"juan{sufijo}@h.es")
    supervisora = crear_usuario(f"Marta{sufijo}", f"marta{sufijo}@h.es")

    fecha_cede, fecha_recibe = _fechas_futuras()
    documento = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=fecha_cede, turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=fecha_recibe, turno_recibe_franja_id=manyana.id,
    )
    firmar_documento(documento, claudia, _FIRMA_PNG)
    firmar_documento(documento, juan, _FIRMA_PNG)
    autorizar_documento(documento, supervisora)
    return documento, claudia, juan, supervisora, manyana, fecha_cede, fecha_recibe


def test_anular_documento_devuelve_la_planilla_al_estado_original(db):
    documento, claudia, juan, supervisora, manyana, fecha_cede, fecha_recibe = _documento_autorizado(db, "a")

    anular_documento(documento, supervisora, "Motivo de prueba")

    # Claudia recupera lo que cedió y pierde lo que había ganado.
    assert TurnoPlanilla.query.filter_by(
        usuario_id=claudia.id, fecha=fecha_cede, franja_horaria_id=manyana.id
    ).first() is not None
    assert TurnoPlanilla.query.filter_by(
        usuario_id=claudia.id, fecha=fecha_recibe, franja_horaria_id=manyana.id
    ).first() is None

    # Juan al revés.
    assert TurnoPlanilla.query.filter_by(
        usuario_id=juan.id, fecha=fecha_recibe, franja_horaria_id=manyana.id
    ).first() is not None
    assert TurnoPlanilla.query.filter_by(
        usuario_id=juan.id, fecha=fecha_cede, franja_horaria_id=manyana.id
    ).first() is None


def test_anular_documento_marca_los_campos_de_anulacion(db):
    documento, claudia, juan, supervisora, manyana, *_ = _documento_autorizado(db, "b")

    anular_documento(documento, supervisora, "Ya no hace falta")

    assert documento.anulado is True
    assert documento.anulado_por_id == supervisora.id
    assert documento.fecha_anulacion is not None
    assert documento.motivo_anulacion == "Ya no hace falta"
    # decision_supervisora conserva el histórico: sigue diciendo que se autorizó.
    assert documento.decision_supervisora == "autorizado"


def test_anular_documento_notifica_a_los_implicados(db):
    from app.models import Notificacion

    documento, claudia, juan, supervisora, *_ = _documento_autorizado(db, "c")
    anular_documento(documento, supervisora, "motivo")

    assert Notificacion.query.filter_by(usuario_id=claudia.id, tipo="documento_cambio_anulado").count() == 1
    assert Notificacion.query.filter_by(usuario_id=juan.id, tipo="documento_cambio_anulado").count() == 1


# --- puede_anularse ---

def test_puede_anularse_falso_si_no_esta_autorizado(db):
    crear_usuario, manyana, tarde = _setup(db, "d")
    claudia = crear_usuario("Claudia", "claudiad@h.es")
    juan = crear_usuario("Juan", "juand@h.es")
    fecha_cede, fecha_recibe = _fechas_futuras()
    documento = crear_documento_cambio(
        claudia, juan, fecha_cede, manyana.id, fecha_recibe, manyana.id,
    )
    firmar_documento(documento, claudia, _FIRMA_PNG)
    firmar_documento(documento, juan, _FIRMA_PNG)

    ok, motivo = puede_anularse(documento)
    assert ok is False
    assert motivo


def test_puede_anularse_falso_si_ya_esta_anulado(db):
    documento, claudia, juan, supervisora, *_ = _documento_autorizado(db, "e")
    anular_documento(documento, supervisora, "motivo")

    ok, motivo = puede_anularse(documento)
    assert ok is False


def test_puede_anularse_falso_si_algun_turno_ya_paso(db):
    crear_usuario, manyana, tarde = _setup(db, "f")
    claudia = crear_usuario("Claudia", "claudiaf@h.es")
    juan = crear_usuario("Juan", "juanf@h.es")
    supervisora = crear_usuario("Marta", "martaf@h.es")

    hoy = date.today()
    documento = crear_documento_cambio(
        claudia, juan, hoy - timedelta(days=3), manyana.id, hoy + timedelta(days=10), manyana.id,
    )
    firmar_documento(documento, claudia, _FIRMA_PNG)
    firmar_documento(documento, juan, _FIRMA_PNG)
    autorizar_documento(documento, supervisora)

    ok, motivo = puede_anularse(documento)
    assert ok is False


def test_puede_anularse_falso_si_otro_cambio_toco_la_planilla_despues(db):
    """Si el turno original que se recuperaría ya está ocupado por otro
    cambio posterior, no se debe poder anular a ciegas."""
    documento, claudia, juan, supervisora, manyana, fecha_cede, fecha_recibe = _documento_autorizado(db, "g")

    # Alguien más le puso a Claudia otro turno justo en la fecha que cedió.
    db.session.add(TurnoPlanilla(usuario_id=claudia.id, fecha=fecha_cede, franja_horaria_id=manyana.id))
    db.session.commit()

    ok, motivo = puede_anularse(documento)
    assert ok is False


def test_puede_anularse_true_en_el_caso_normal(db):
    documento, *_ = _documento_autorizado(db, "h")
    ok, motivo = puede_anularse(documento)
    assert ok is True
    assert motivo is None


# --- reapertura del match cuando el documento viene del motor de matching ---

def _match_cambio_simetrico_confirmado(db, sufijo):
    crear_usuario, manyana, tarde = _setup(db, sufijo)
    ana = crear_usuario(f"Ana{sufijo}", f"ana{sufijo}@h.es")
    pedro = crear_usuario(f"Pedro{sufijo}", f"pedro{sufijo}@h.es")
    supervisora = crear_usuario(f"Marta{sufijo}", f"marta{sufijo}@h.es")

    fecha_a, fecha_b = _fechas_futuras()

    pub_ana = PublicacionCambio(usuario_id=ana.id)
    db.session.add(pub_ana)
    db.session.flush()
    tc_ana = TurnoCedido(publicacion_id=pub_ana.id, fecha=fecha_a, franja_horaria_id=manyana.id)
    ta_ana = TurnoAceptado(publicacion_id=pub_ana.id, fecha=fecha_b, franja_horaria_id=manyana.id)
    db.session.add_all([tc_ana, ta_ana])

    pub_pedro = PublicacionCambio(usuario_id=pedro.id)
    db.session.add(pub_pedro)
    db.session.flush()
    tc_pedro = TurnoCedido(publicacion_id=pub_pedro.id, fecha=fecha_b, franja_horaria_id=manyana.id)
    ta_pedro = TurnoAceptado(publicacion_id=pub_pedro.id, fecha=fecha_a, franja_horaria_id=manyana.id)
    db.session.add_all([tc_pedro, ta_pedro])
    db.session.flush()

    # Estado que dejaría confirmar_participacion() al llegar a confirmado_total.
    tc_ana.estado = tc_pedro.estado = "resuelto"
    ta_ana.estado = ta_pedro.estado = "resuelto"
    pub_ana.estado = pub_pedro.estado = "confirmada"

    match = MatchCambio(tipo="directo_2", estado="confirmado_total")
    db.session.add(match)
    db.session.flush()
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_ana.id, turno_cedido_id=tc_ana.id, turno_aceptado_id=ta_ana.id, confirmado=True))
    db.session.add(MatchParticipacion(match_id=match.id, publicacion_id=pub_pedro.id, turno_cedido_id=tc_pedro.id, turno_aceptado_id=ta_pedro.id, confirmado=True))
    db.session.commit()

    documento = crear_documento_cambio_desde_match(match)
    firmar_documento(documento, ana, _FIRMA_PNG)
    firmar_documento(documento, pedro, _FIRMA_PNG)
    autorizar_documento(documento, supervisora)

    return documento, match, pub_ana, pub_pedro, tc_ana, tc_pedro, ta_ana, ta_pedro, ana, pedro, supervisora


def test_anular_documento_de_un_match_reabre_el_match(db):
    documento, match, *_rest = _match_cambio_simetrico_confirmado(db, "i")
    supervisora = _rest[-1]

    anular_documento(documento, supervisora, "motivo")

    assert match.estado == "anulado"


def test_anular_documento_de_un_match_reabre_los_turnos_y_publicaciones(db):
    (documento, match, pub_ana, pub_pedro, tc_ana, tc_pedro, ta_ana, ta_pedro,
     ana, pedro, supervisora) = _match_cambio_simetrico_confirmado(db, "j")

    anular_documento(documento, supervisora, "motivo")

    assert tc_ana.estado == "abierto"
    assert tc_pedro.estado == "abierto"
    assert ta_ana.estado == "abierto"
    assert ta_pedro.estado == "abierto"
    assert pub_ana.estado == "abierta"
    assert pub_pedro.estado == "abierta"


def test_anular_documento_manual_no_toca_ningun_match(db):
    """Un cambio creado a mano (sin match_id) no debe intentar tocar nada
    de MatchCambio al anularse (no debe lanzar, y match_id sigue None)."""
    documento, claudia, juan, supervisora, *_ = _documento_autorizado(db, "k")
    assert documento.match_id is None
    anular_documento(documento, supervisora, "motivo")
    assert documento.match_id is None
