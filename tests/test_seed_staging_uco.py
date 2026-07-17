"""Tests para la ampliación aditiva de UCO·La Paz·Enfermería en
scripts/seed_staging.py: cuentas sintéticas + supervisora + rota jul-sep-2026
+ hojas de cambio, sin tocar a los usuarios reales ya existentes en esa
unidad.
"""
from datetime import date

import pytest

from app.extensions import db as _db
from app.models import (
    Categoria, DocumentoCambio, ParticipanteDocumentoCambio, PlanillaMes,
    TurnoPlanilla, Usuario, insertar_categorias_semilla,
)
from app.services.demo import BOT_ACCOUNTS, DEMO_ACCOUNTS, reset_demo
from app.services.registro import (
    encontrar_o_crear_ciudad, encontrar_o_crear_hospital, encontrar_o_crear_pais,
    encontrar_o_crear_provincia, encontrar_o_crear_unidad,
)
from scripts.seed_staging import (
    UCO_BOT_ACCOUNTS, UCO_CATEGORIA, UCO_DEMO_ACCOUNTS, UCO_HOSPITAL,
    UCO_SUPERVISORA_EMAIL, UCO_SUPERVISORA_PASSWORD, UCO_UNIDAD, ampliar_uco_la_paz,
)


def _unidad_uco():
    pais      = encontrar_o_crear_pais("España")
    provincia = encontrar_o_crear_provincia("Madrid", pais)
    ciudad    = encontrar_o_crear_ciudad("Madrid", provincia)
    hospital  = encontrar_o_crear_hospital(UCO_HOSPITAL, ciudad)
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre=UCO_CATEGORIA).first()
    unidad, _ = encontrar_o_crear_unidad(UCO_UNIDAD, hospital, cat)
    return unidad, cat


def _crear_usuario_real(unidad, cat, nombre="Usuario Real", email="real@test.es"):
    u = Usuario(nombre=nombre, email=email, unidad=unidad, categoria=cat)
    u.set_password("x")
    _db.session.add(u)
    _db.session.commit()
    return u


def test_crea_las_23_cuentas_sinteticas(db):
    ampliar_uco_la_paz()
    for _, email in UCO_DEMO_ACCOUNTS + UCO_BOT_ACCOUNTS:
        assert Usuario.query.filter_by(email=email).first() is not None


def test_cuentas_uco_no_chocan_con_las_de_la_unidad_demo_aislada(db):
    """Regresión: reset_demo() (flask seed-demo, DEMO_ENABLED=true, ya activo
    en staging) siembra su propia unidad con DEMO_ACCOUNTS/BOT_ACCOUNTS.
    Como el email es único a nivel de toda la BD, ampliar_uco_la_paz() debe
    usar emails distintos o revienta con un IntegrityError en cuanto ambas
    convivan en la misma base de datos -- exactamente lo que le pasó al
    usuario en el staging real."""
    reset_demo()

    ampliar_uco_la_paz()

    for _, email in UCO_DEMO_ACCOUNTS + UCO_BOT_ACCOUNTS:
        assert Usuario.query.filter_by(email=email).first() is not None
    for _, email in DEMO_ACCOUNTS + BOT_ACCOUNTS:
        assert Usuario.query.filter_by(email=email).first() is not None


def test_no_toca_a_un_usuario_real_ya_existente(db):
    unidad, cat = _unidad_uco()
    real = _crear_usuario_real(unidad, cat)
    real_id, real_password_hash = real.id, real.password_hash

    ampliar_uco_la_paz()

    real_tras = db.session.get(Usuario, real_id)
    assert real_tras is not None
    assert real_tras.password_hash == real_password_hash
    assert real_tras.unidad_id == unidad.id


def test_idempotente_no_duplica_usuarios(db):
    ampliar_uco_la_paz()
    n_usuarios_1 = Usuario.query.count()
    ampliar_uco_la_paz()
    assert Usuario.query.count() == n_usuarios_1


def test_crea_supervisora(db):
    ampliar_uco_la_paz()
    sup = Usuario.query.filter_by(email=UCO_SUPERVISORA_EMAIL).first()
    assert sup is not None
    assert sup.es_supervisora is True
    assert sup.check_password(UCO_SUPERVISORA_PASSWORD)


def test_supervisora_existente_sin_decisiones_se_sustituye(db):
    unidad, cat = _unidad_uco()
    vieja = Usuario(nombre="Supervisora Vieja", email="vieja@test.es",
                    unidad=unidad, categoria=cat, es_supervisora=True)
    vieja.set_password("x")
    db.session.add(vieja)
    db.session.commit()

    ampliar_uco_la_paz()

    assert Usuario.query.filter_by(email="vieja@test.es").first() is None
    assert Usuario.query.filter_by(email=UCO_SUPERVISORA_EMAIL).first() is not None


def test_supervisora_con_decisiones_no_se_borra(db):
    unidad, cat = _unidad_uco()
    vieja = Usuario(nombre="Supervisora Vieja", email="vieja@test.es",
                    unidad=unidad, categoria=cat, es_supervisora=True)
    vieja.set_password("x")
    a = Usuario(nombre="A", email="a@test.es", unidad=unidad, categoria=cat)
    a.set_password("x")
    b = Usuario(nombre="B", email="b@test.es", unidad=unidad, categoria=cat)
    b.set_password("x")
    db.session.add_all([vieja, a, b])
    db.session.flush()

    doc = DocumentoCambio(
        creado_por=a, unidad_id=unidad.id, numero_unidad=1,
        estado="completo", decision_supervisora="autorizado", supervisora=vieja,
    )
    db.session.add(doc)
    db.session.commit()

    ampliar_uco_la_paz()

    assert Usuario.query.filter_by(email="vieja@test.es").first() is not None


def test_rota_publicada_para_jul_ago_sep_2026(db):
    ampliar_uco_la_paz()
    usuarios = Usuario.query.filter_by(email=UCO_BOT_ACCOUNTS[0][1]).all()
    assert usuarios
    bot = usuarios[0]
    for mes in (7, 8, 9):
        pm = PlanillaMes.query.filter_by(usuario_id=bot.id, anyo=2026, mes=mes).first()
        assert pm is not None
        assert pm.publicada is True
    assert TurnoPlanilla.query.filter_by(usuario_id=bot.id).count() > 0


def test_cada_usuario_tiene_al_menos_dos_hojas_de_cambio(db):
    ampliar_uco_la_paz()
    unidad, _ = _unidad_uco()
    sup = Usuario.query.filter_by(email=UCO_SUPERVISORA_EMAIL).first()
    usuarios = Usuario.query.filter(
        Usuario.unidad_id == unidad.id, Usuario.id != sup.id,
    ).all()
    assert len(usuarios) >= 23

    for u in usuarios:
        n = ParticipanteDocumentoCambio.query.filter_by(usuario_id=u.id).count()
        assert n >= 2, f"{u.email} tiene solo {n} hojas de cambio"


def test_hojas_de_cambio_cubren_los_4_estados(db):
    ampliar_uco_la_paz()
    documentos = DocumentoCambio.query.all()
    assert documentos

    pendiente_firmas = [d for d in documentos if d.estado == "pendiente_firmas"]
    completo_pendiente = [
        d for d in documentos if d.estado == "completo" and d.decision_supervisora == "pendiente"
    ]
    autorizados = [d for d in documentos if d.decision_supervisora == "autorizado"]
    denegados = [d for d in documentos if d.decision_supervisora == "denegado"]

    assert pendiente_firmas
    assert completo_pendiente
    assert autorizados
    assert denegados


def test_hojas_de_cambio_en_fechas_agosto_septiembre(db):
    ampliar_uco_la_paz()
    participantes = ParticipanteDocumentoCambio.query.all()
    assert participantes
    for p in participantes:
        assert date(2026, 8, 1) <= p.turno_cede_fecha <= date(2026, 9, 30)
        assert date(2026, 8, 1) <= p.turno_recibe_fecha <= date(2026, 9, 30)


def test_con_usuarios_reales_preexistentes_tambien_cumple_dos_hojas_por_usuario(db):
    """Simula el caso real de staging: 16 usuarios ya existentes en la unidad
    antes de ejecutar el script. Ninguno debe quedarse sin sus >=2 hojas."""
    unidad, cat = _unidad_uco()
    reales = [
        _crear_usuario_real(unidad, cat, nombre=f"Real {i}", email=f"real{i}@test.es")
        for i in range(16)
    ]

    ampliar_uco_la_paz()

    sup = Usuario.query.filter_by(email=UCO_SUPERVISORA_EMAIL).first()
    usuarios = Usuario.query.filter(
        Usuario.unidad_id == unidad.id, Usuario.id != sup.id,
    ).all()
    assert len(usuarios) == 16 + 23

    for u in usuarios:
        n = ParticipanteDocumentoCambio.query.filter_by(usuario_id=u.id).count()
        assert n >= 2, f"{u.email} tiene solo {n} hojas de cambio"


def test_autorizado_vuelca_el_cambio_a_las_planillas(db):
    ampliar_uco_la_paz()
    autorizado = DocumentoCambio.query.filter_by(decision_supervisora="autorizado").first()
    assert autorizado is not None
    for p in autorizado.participantes:
        recibido = TurnoPlanilla.query.filter_by(
            usuario_id=p.usuario_id, fecha=p.turno_recibe_fecha,
            franja_horaria_id=p.turno_recibe_franja_id,
        ).first()
        assert recibido is not None
