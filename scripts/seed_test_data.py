#!/usr/bin/env python
"""
Seed de datos de prueba para tests manuales locales.

Uso:
    python scripts/seed_test_data.py           # añade datos si no existen
    python scripts/seed_test_data.py --reset   # trunca TODO y recrea desde cero

Usuarios creados (contraseña: test123):
  admin@test.com  — Admin (es_admin=True)
  ana@test.com    — Enfermería, UCO, La Paz      ← mismo grupo que Bruno y Carlos
  bruno@test.com  — Enfermería, UCO, La Paz      ← mismo grupo que Ana y Carlos
  carlos@test.com — Enfermería, UCO, La Paz      ← mismo grupo que Ana y Bruno
  carmen@test.com — Enfermería, Urgencias, La Paz ← grupo distinto (no puede matchear con Ana)
  david@test.com  — TCAE, UCO, La Paz            ← categoría distinta (no puede matchear con Ana)
  eva@test.com    — Enfermería, Cardiología, 12 Oct ← hospital distinto

Publicaciones:
  5 abiertas (una por tipo: cambio, regalo, petición, junte, cambio_dia)
  1 match propuesto      (Ana ↔ Bruno, pendiente de confirmar)
  1 match confirmado_parcial (Ana confirmó, Carlos pendiente)
  1 match confirmado_total   (Bruno ↔ Carlos, publicaciones confirmadas)
  1 parcialmente_resuelta    (Ana: 2 turnos, 1 ya resuelto)
  1 cancelada  (Carmen)
  1 caducada   (Eva)
"""
import os
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from sqlalchemy import text
from app.models import (
    insertar_categorias_semilla,
    Categoria, Usuario,
    PublicacionCambio, TurnoCedido, TurnoAceptado,
    MatchCambio, MatchParticipacion,
    FranjaHoraria,
)
from app.services.registro import (
    encontrar_o_crear_pais,
    encontrar_o_crear_provincia,
    encontrar_o_crear_ciudad,
    encontrar_o_crear_hospital,
    encontrar_o_crear_unidad,
)

_SEED_MARKER = "admin@test.com"
_PASSWORD = "test123"

_TODAS_LAS_TABLAS = (
    "event, busqueda_guardada, suscripcion_publicaciones, feedback, "
    "notificacion, match_participacion, match_cambio, "
    "turno_cedido, turno_aceptado, publicacion_cambio, "
    "usuario, franja_horaria, unidad, grupo_intercambio, "
    "hospital, categoria, ciudad, provincia, pais"
)


# ─── helpers ────────────────────────────────────────────────────────────────

def _ya_sembrado():
    return bool(Usuario.query.filter_by(email=_SEED_MARKER).first())


def _truncar():
    db.session.execute(
        text(f"TRUNCATE {_TODAS_LAS_TABLAS} RESTART IDENTITY CASCADE")
    )
    db.session.commit()
    print("Tablas vaciadas.")


def _usuario(nombre, email, unidad, categoria, es_admin=False):
    u = Usuario(
        nombre=nombre,
        email=email,
        unidad=unidad,
        categoria=categoria,
        es_admin=es_admin,
        onboarding_visto=True,
    )
    u.set_password(_PASSWORD)
    db.session.add(u)
    return u


def _pub(usuario, tipo, estado="abierta", mensaje=None):
    p = PublicacionCambio(usuario=usuario, tipo=tipo, estado=estado, mensaje=mensaje)
    db.session.add(p)
    return p


def _tc(pub, fecha, franja, estado="abierto"):
    t = TurnoCedido(publicacion=pub, fecha=fecha, franja_horaria=franja, estado=estado)
    db.session.add(t)
    return t


def _ta(pub, fecha, franja=None, cualquier_franja=False, estado="abierto"):
    t = TurnoAceptado(
        publicacion=pub,
        fecha=fecha,
        franja_horaria=franja,
        cualquier_franja=cualquier_franja,
        estado=estado,
    )
    db.session.add(t)
    return t


def _match(tipo="directo_2", estado="propuesto"):
    m = MatchCambio(tipo=tipo, estado=estado)
    db.session.add(m)
    return m


def _part(match, pub, tc=None, ta=None, confirmado=False):
    p = MatchParticipacion(
        match=match,
        publicacion=pub,
        turno_cedido=tc,
        turno_aceptado=ta,
        confirmado=confirmado,
        fecha_confirmacion=datetime.now(timezone.utc) if confirmado else None,
    )
    db.session.add(p)
    return p


def _franja(grupo, nombre):
    return FranjaHoraria.query.filter_by(
        grupo_intercambio_id=grupo.id, nombre=nombre
    ).first()


# ─── seed principal ──────────────────────────────────────────────────────────

def sembrar():
    # 1. Categorías semilla
    insertar_categorias_semilla()
    cat_enf  = Categoria.query.filter_by(nombre="Enfermería").first()
    cat_tcae = Categoria.query.filter_by(nombre="Auxiliar de enfermería (TCAE)").first()

    # Categoría para el admin (no está en la semilla)
    cat_admin = Categoria.query.filter_by(nombre="Administrador").first()
    if not cat_admin:
        cat_admin = Categoria(nombre="Administrador")
        db.session.add(cat_admin)
        db.session.flush()

    # 2. Geografía
    pais      = encontrar_o_crear_pais("España")
    provincia = encontrar_o_crear_provincia("Madrid", pais)
    ciudad    = encontrar_o_crear_ciudad("Madrid", provincia)

    # 3. Hospitales
    lapaz = encontrar_o_crear_hospital("Hospital Universitario La Paz", ciudad)
    doce  = encontrar_o_crear_hospital("Hospital 12 de Octubre", ciudad)

    # 4. Unidades (cada una genera su propio GrupoIntercambio con franjas M/T/N/D12/N12)
    uco_enf,      _ = encontrar_o_crear_unidad("UCO",         lapaz, cat_enf)
    urgencias_enf,_ = encontrar_o_crear_unidad("Urgencias",   lapaz, cat_enf)
    uco_tcae,     _ = encontrar_o_crear_unidad("UCO",         lapaz, cat_tcae)
    cardio_enf,   _ = encontrar_o_crear_unidad("Cardiología", doce,  cat_enf)

    # Unidad aislada para el admin
    hosp_sistema   = encontrar_o_crear_hospital("Sistema")
    unid_admin, _  = encontrar_o_crear_unidad("Administración", hosp_sistema)
    db.session.flush()

    # Franjas del grupo UCO+Enfermería (el grupo con más actividad de prueba)
    g = uco_enf.grupo_intercambio
    manana = _franja(g, "Mañana")
    tarde  = _franja(g, "Tarde")
    noche  = _franja(g, "Noche")
    diurno = _franja(g, "Diurno 12h")

    # Franjas de los grupos secundarios
    g_urg    = urgencias_enf.grupo_intercambio
    g_cardio = cardio_enf.grupo_intercambio

    # 5. Usuarios
    admin  = _usuario("Admin Test",   _SEED_MARKER,    unid_admin,    cat_admin,  es_admin=True)
    ana    = _usuario("Ana García",   "ana@test.com",   uco_enf,      cat_enf)
    bruno  = _usuario("Bruno López",  "bruno@test.com", uco_enf,      cat_enf)
    carlos = _usuario("Carlos Ruiz",  "carlos@test.com",uco_enf,      cat_enf)
    carmen = _usuario("Carmen Vega",  "carmen@test.com",urgencias_enf,cat_enf)
    _      = _usuario("David Mora",   "david@test.com", uco_tcae,     cat_tcae)
    eva    = _usuario("Eva Torres",   "eva@test.com",   cardio_enf,   cat_enf)
    db.session.flush()

    # 6. Publicaciones abiertas (una por cada tipo)

    # cambio: Ana cede una mañana, acepta una tarde
    pub_cambio = _pub(ana, "cambio", mensaje="Necesito el 20 de agosto de tarde")
    _tc(pub_cambio, date(2026, 8, 15), manana)
    _ta(pub_cambio, date(2026, 8, 20), tarde)

    # regalo: Bruno regala una tarde
    pub_regalo = _pub(bruno, "regalo", mensaje="Regalo mi tarde del 10, me voy de viaje")
    _tc(pub_regalo, date(2026, 8, 10), tarde)

    # petición: Ana quiere librar una mañana sin ofrecer nada
    pub_peticion = _pub(ana, "peticion")
    _ta(pub_peticion, date(2026, 7, 15), manana)

    # junte: Bruno cede noche 1-sep, acepta noche 8-sep
    pub_junte = _pub(bruno, "junte")
    _tc(pub_junte, date(2026, 9,  1), noche)
    _ta(pub_junte, date(2026, 9,  8), noche)

    # cambio_dia: Carlos cede un diurno 12h, acepta cualquier franja
    pub_cambio_dia = _pub(carlos, "cambio_dia")
    _tc(pub_cambio_dia, date(2026, 9,  5), diurno)
    _ta(pub_cambio_dia, date(2026, 9, 15), cualquier_franja=True)

    db.session.flush()

    # 7. Match propuesto: Ana (mañana 20-jul) ↔ Bruno (tarde 25-jul)
    pub_prop_ana   = _pub(ana,   "cambio")
    tc_prop_ana    = _tc(pub_prop_ana,   date(2026, 7, 20), manana)
    ta_prop_ana    = _ta(pub_prop_ana,   date(2026, 7, 25), tarde)

    pub_prop_bruno = _pub(bruno, "cambio")
    tc_prop_bruno  = _tc(pub_prop_bruno, date(2026, 7, 25), tarde)
    ta_prop_bruno  = _ta(pub_prop_bruno, date(2026, 7, 20), manana)

    db.session.flush()

    m_prop = _match(estado="propuesto")
    db.session.flush()
    _part(m_prop, pub_prop_ana,   tc=tc_prop_ana,   ta=ta_prop_ana)
    _part(m_prop, pub_prop_bruno, tc=tc_prop_bruno, ta=ta_prop_bruno)

    # 8. Match confirmado_parcial: Ana confirmó, Carlos pendiente
    pub_cp_ana    = _pub(ana,    "cambio")
    tc_cp_ana     = _tc(pub_cp_ana,    date(2026, 8,  1), manana)
    ta_cp_ana     = _ta(pub_cp_ana,    date(2026, 8,  5), tarde)

    pub_cp_carlos = _pub(carlos, "cambio")
    tc_cp_carlos  = _tc(pub_cp_carlos, date(2026, 8,  5), tarde)
    ta_cp_carlos  = _ta(pub_cp_carlos, date(2026, 8,  1), manana)

    db.session.flush()

    m_cp = _match(estado="confirmado_parcial")
    db.session.flush()
    _part(m_cp, pub_cp_ana,    tc=tc_cp_ana,    ta=ta_cp_ana,    confirmado=True)
    _part(m_cp, pub_cp_carlos, tc=tc_cp_carlos, ta=ta_cp_carlos, confirmado=False)

    # 9. Match confirmado_total: Bruno (tarde 15-jun) ↔ Carlos (mañana 16-jun)
    pub_ct_bruno  = _pub(bruno,  "cambio", estado="confirmada")
    tc_ct_bruno   = _tc(pub_ct_bruno,  date(2026, 6, 15), tarde,  estado="resuelto")
    ta_ct_bruno   = _ta(pub_ct_bruno,  date(2026, 6, 16), manana, estado="resuelto")

    pub_ct_carlos = _pub(carlos, "cambio", estado="confirmada")
    tc_ct_carlos  = _tc(pub_ct_carlos, date(2026, 6, 16), manana, estado="resuelto")
    ta_ct_carlos  = _ta(pub_ct_carlos, date(2026, 6, 15), tarde,  estado="resuelto")

    db.session.flush()

    m_ct = _match(estado="confirmado_total")
    db.session.flush()
    _part(m_ct, pub_ct_bruno,  tc=tc_ct_bruno,  ta=ta_ct_bruno,  confirmado=True)
    _part(m_ct, pub_ct_carlos, tc=tc_ct_carlos, ta=ta_ct_carlos, confirmado=True)

    # 10. Parcialmente resuelta: Ana tiene 2 turnos cedidos; el primero ya fue
    #     resuelto en un match confirmado_total con Bruno, el segundo sigue abierto.
    pub_par_ana   = _pub(ana,   "cambio", estado="parcialmente_resuelta")
    tc_par_ana_1  = _tc(pub_par_ana, date(2026, 7,  1), manana, estado="resuelto")
    tc_par_ana_2  = _tc(pub_par_ana, date(2026, 7,  8), manana)   # abierto
    ta_par_ana    = _ta(pub_par_ana, date(2026, 7, 10), tarde,  estado="resuelto")

    pub_par_bruno = _pub(bruno, "cambio", estado="confirmada")
    tc_par_bruno  = _tc(pub_par_bruno, date(2026, 7, 10), tarde,  estado="resuelto")
    ta_par_bruno  = _ta(pub_par_bruno, date(2026, 7,  1), manana, estado="resuelto")

    db.session.flush()

    m_par = _match(estado="confirmado_total")
    db.session.flush()
    _part(m_par, pub_par_ana,   tc=tc_par_ana_1, ta=ta_par_ana,   confirmado=True)
    _part(m_par, pub_par_bruno, tc=tc_par_bruno,  ta=ta_par_bruno, confirmado=True)

    # 11. Cancelada: Carmen
    pub_cancelada = _pub(carmen, "cambio", estado="cancelada")
    _tc(pub_cancelada, date(2026, 8, 20), _franja(g_urg, "Mañana"))
    _ta(pub_cancelada, date(2026, 8, 25), _franja(g_urg, "Tarde"))

    # 12. Caducada: Eva (turno en fecha pasada)
    pub_caducada = _pub(eva, "cambio", estado="caducada")
    _tc(pub_caducada, date(2026, 1, 15), _franja(g_cardio, "Mañana"))
    _ta(pub_caducada, date(2026, 1, 20), _franja(g_cardio, "Tarde"))

    db.session.commit()

    _imprimir_resumen()


def _imprimir_resumen():
    sep = "─" * 60
    print(f"\n{sep}")
    print("  SEED DE PRUEBA COMPLETADO")
    print(sep)
    print(f"\n  Contraseña de todos los usuarios: {_PASSWORD}\n")
    print("  USUARIOS")
    filas = [
        (_SEED_MARKER,    "Admin Test",   "admin (es_admin=True)"),
        ("ana@test.com",   "Ana García",   "UCO · Enfermería · La Paz"),
        ("bruno@test.com", "Bruno López",  "UCO · Enfermería · La Paz  ← mismo grupo que Ana"),
        ("carlos@test.com","Carlos Ruiz",  "UCO · Enfermería · La Paz  ← mismo grupo que Ana"),
        ("carmen@test.com","Carmen Vega",  "Urgencias · Enfermería · La Paz  ← grupo distinto"),
        ("david@test.com", "David Mora",   "UCO · TCAE · La Paz  ← categoría distinta"),
        ("eva@test.com",   "Eva Torres",   "Cardiología · Enfermería · 12 Oct  ← hospital distinto"),
    ]
    for email, nombre, desc in filas:
        print(f"    {email:<24} {nombre:<16} {desc}")
    print()
    print("  PUBLICACIONES")
    print("    5 abiertas          (cambio, regalo, petición, junte, cambio_dia)")
    print("    1 match propuesto   Ana ↔ Bruno  (mañana 20-jul / tarde 25-jul)")
    print("    1 confirmado_parcial Ana confirmó ✓, Carlos pendiente")
    print("    1 confirmado_total  Bruno ↔ Carlos (junio, publicaciones confirmadas)")
    print("    1 parcialm_resuelta Ana: turno 1-jul resuelto, turno 8-jul abierto")
    print("    1 cancelada         Carmen")
    print("    1 caducada          Eva")
    print(f"\n{sep}\n")


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    app = create_app("development")
    with app.app_context():
        if not reset and _ya_sembrado():
            print(
                "El seed ya está aplicado. "
                "Usa --reset para truncar todo y recrear desde cero."
            )
            sys.exit(0)
        if reset:
            _truncar()
        sembrar()
