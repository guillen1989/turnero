from datetime import date, time

from app.models import (
    Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria, Usuario,
    DocumentoCambio, ParticipanteDocumentoCambio,
)
from app.services.planilla import añadir_turno, establecer_estado_dia
from app.services.planilla_supervision import (
    get_turnos_mes_unidad, get_estados_mes_unidad, get_cambios_autorizados_mes_unidad,
)


def _setup(db, sufijo="a"):
    hospital = Hospital(nombre=f"H-{sufijo}")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    unidad = Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo)
    otra_unidad = Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo)
    categoria = Categoria(nombre=f"Cat-{sufijo}")
    franja_m = FranjaHoraria(
        nombre="Mañana", hora_inicio=time(8, 0), hora_fin=time(15, 0), grupo_intercambio=grupo
    )
    franja_t = FranjaHoraria(
        nombre="Tarde", hora_inicio=time(15, 0), hora_fin=time(22, 0), grupo_intercambio=grupo
    )
    db.session.add_all([unidad, otra_unidad, categoria, franja_m, franja_t])
    db.session.commit()

    def crear(nombre, email, u=unidad):
        usuario = Usuario(nombre=nombre, email=email, unidad=u, categoria=categoria)
        usuario.set_password("pass")
        db.session.add(usuario)
        db.session.commit()
        return usuario

    ana = crear("Ana", f"ana_{sufijo}@test.es")
    bea = crear("Bea", f"bea_{sufijo}@test.es")
    cris = crear("Cris", f"cris_{sufijo}@test.es", u=otra_unidad)
    return unidad, otra_unidad, ana, bea, cris, franja_m, franja_t


def test_get_turnos_mes_unidad_agrupa_por_usuario_y_fecha(db):
    unidad, _, ana, bea, _, franja_m, _ = _setup(db, "a")
    añadir_turno(ana, date(2026, 7, 1), franja_m.id)
    añadir_turno(bea, date(2026, 7, 1), franja_m.id)
    añadir_turno(ana, date(2026, 7, 2), franja_m.id)

    turnos = get_turnos_mes_unidad(unidad, 2026, 7)

    assert set(turnos.keys()) == {
        (ana.id, date(2026, 7, 1)),
        (bea.id, date(2026, 7, 1)),
        (ana.id, date(2026, 7, 2)),
    }
    assert turnos[(ana.id, date(2026, 7, 1))][0].franja_horaria_id == franja_m.id


def test_get_turnos_mes_unidad_no_incluye_otro_mes(db):
    unidad, _, ana, _, _, franja_m, _ = _setup(db, "b")
    añadir_turno(ana, date(2026, 8, 1), franja_m.id)

    assert get_turnos_mes_unidad(unidad, 2026, 7) == {}


def test_get_turnos_mes_unidad_no_incluye_otra_unidad(db):
    unidad, _, _, _, cris, franja_m, _ = _setup(db, "c")
    añadir_turno(cris, date(2026, 7, 1), franja_m.id)

    assert get_turnos_mes_unidad(unidad, 2026, 7) == {}


def test_get_turnos_mes_unidad_soporta_doblaje(db):
    unidad, _, ana, _, _, franja_m, franja_t = _setup(db, "d")
    añadir_turno(ana, date(2026, 7, 1), franja_m.id)
    añadir_turno(ana, date(2026, 7, 1), franja_t.id)

    turnos = get_turnos_mes_unidad(unidad, 2026, 7)
    assert len(turnos[(ana.id, date(2026, 7, 1))]) == 2


# ── get_estados_mes_unidad ────────────────────────────────────────────────────

def test_get_estados_mes_unidad_agrupa_por_usuario_y_fecha(db):
    unidad, _, ana, bea, _, _, _ = _setup(db, "e")
    establecer_estado_dia(ana, date(2026, 7, 1), "libre")
    establecer_estado_dia(bea, date(2026, 7, 1), "vacaciones")

    estados = get_estados_mes_unidad(unidad, 2026, 7)

    assert estados[(ana.id, date(2026, 7, 1))].tipo == "libre"
    assert estados[(bea.id, date(2026, 7, 1))].tipo == "vacaciones"


def test_get_estados_mes_unidad_no_incluye_otra_unidad(db):
    unidad, _, _, _, cris, _, _ = _setup(db, "f")
    establecer_estado_dia(cris, date(2026, 7, 1), "libre")

    assert get_estados_mes_unidad(unidad, 2026, 7) == {}


# ── get_cambios_autorizados_mes_unidad ────────────────────────────────────────

def _crear_documento(db, ana, pedro, unidad, franja_m, franja_t, sufijo,
                      decision_supervisora="autorizado", anulado=False,
                      cede_ana=date(2026, 7, 25), recibe_ana=date(2026, 7, 26)):
    documento = DocumentoCambio(
        creado_por=ana, unidad=unidad, numero_unidad=int(sufijo, 36),
        decision_supervisora=decision_supervisora, anulado=anulado,
    )
    db.session.add(documento)
    db.session.flush()
    documento.participantes.append(ParticipanteDocumentoCambio(
        usuario=ana,
        turno_cede_fecha=cede_ana, turno_cede_franja=franja_m,
        turno_recibe_fecha=recibe_ana, turno_recibe_franja=franja_t,
    ))
    documento.participantes.append(ParticipanteDocumentoCambio(
        usuario=pedro,
        turno_cede_fecha=recibe_ana, turno_cede_franja=franja_t,
        turno_recibe_fecha=cede_ana, turno_recibe_franja=franja_m,
    ))
    db.session.commit()
    return documento


def test_get_cambios_autorizados_mes_unidad_incluye_cede_y_recibe(db):
    unidad, _, ana, pedro, _, franja_m, franja_t = _setup(db, "g")
    documento = _crear_documento(db, ana, pedro, unidad, franja_m, franja_t, "g")

    cambios = get_cambios_autorizados_mes_unidad(unidad, 2026, 7)

    assert cambios[(ana.id, date(2026, 7, 25))].id == documento.id
    assert cambios[(ana.id, date(2026, 7, 26))].id == documento.id
    assert cambios[(pedro.id, date(2026, 7, 25))].id == documento.id
    assert cambios[(pedro.id, date(2026, 7, 26))].id == documento.id


def test_get_cambios_autorizados_mes_unidad_excluye_no_autorizado(db):
    unidad, _, ana, pedro, _, franja_m, franja_t = _setup(db, "h")
    _crear_documento(db, ana, pedro, unidad, franja_m, franja_t, "h",
                      decision_supervisora="pendiente")

    assert get_cambios_autorizados_mes_unidad(unidad, 2026, 7) == {}


def test_get_cambios_autorizados_mes_unidad_excluye_anulado(db):
    unidad, _, ana, pedro, _, franja_m, franja_t = _setup(db, "i")
    _crear_documento(db, ana, pedro, unidad, franja_m, franja_t, "i", anulado=True)

    assert get_cambios_autorizados_mes_unidad(unidad, 2026, 7) == {}


def test_get_cambios_autorizados_mes_unidad_excluye_otra_unidad(db):
    unidad, otra_unidad, ana, pedro, _, franja_m, franja_t = _setup(db, "j")
    _crear_documento(db, ana, pedro, unidad, franja_m, franja_t, "j")

    assert get_cambios_autorizados_mes_unidad(otra_unidad, 2026, 7) == {}


def test_get_cambios_autorizados_mes_unidad_filtra_por_mes_cuando_cruza_mes(db):
    unidad, _, ana, pedro, _, franja_m, franja_t = _setup(db, "k")
    _crear_documento(
        db, ana, pedro, unidad, franja_m, franja_t, "k",
        cede_ana=date(2026, 7, 31), recibe_ana=date(2026, 8, 1),
    )

    cambios_julio = get_cambios_autorizados_mes_unidad(unidad, 2026, 7)
    cambios_agosto = get_cambios_autorizados_mes_unidad(unidad, 2026, 8)

    assert (ana.id, date(2026, 7, 31)) in cambios_julio
    assert (ana.id, date(2026, 8, 1)) not in cambios_julio
    assert (ana.id, date(2026, 8, 1)) in cambios_agosto
