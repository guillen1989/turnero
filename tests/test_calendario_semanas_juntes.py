"""Tests del servicio de agregación semanal para el calendario visual, modo
'juntes': a diferencia de ofertas/peticiones (día a día), un junte de noches
es un patrón semanal completo, así que aquí se agrupa por semana natural
(lunes a domingo) en vez de por día."""
from datetime import date, timedelta

from app.extensions import db
from app.models import (
    Categoria,
    FranjaHoraria,
    PublicacionCambio,
    TurnoAceptado,
    TurnoCedido,
    insertar_categorias_semilla,
)
from app.services.calendario_mercado import construir_semanas_juntes, preparar_semanas_juntes
from app.services.registro import registrar_usuario


def _categoria(nombre="Enfermería"):
    insertar_categorias_semilla()
    return Categoria.query.filter_by(nombre=nombre).first()


def _usuario(nombre, email, hospital="H1", unidad="Urgencias", categoria=None):
    if categoria is None:
        categoria = _categoria()
    return registrar_usuario(nombre, email, "password123", hospital, unidad, categoria.id)


def _franja(grupo_id, nombre="Noche"):
    return FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id, nombre=nombre).first()


def _junte(usuario, cedidos, aceptados, estado="abierta"):
    """cedidos/aceptados: lista de fechas. Usa siempre la franja Noche."""
    pub = PublicacionCambio(usuario_id=usuario.id, tipo="junte", estado=estado)
    db.session.add(pub)
    db.session.flush()
    noche = _franja(usuario.unidad.grupo_intercambio_id)
    for fecha in cedidos:
        db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=fecha, franja_horaria_id=noche.id))
    for fecha in aceptados:
        db.session.add(TurnoAceptado(publicacion_id=pub.id, fecha=fecha, franja_horaria_id=noche.id))
    db.session.commit()
    return pub


# --- construir_semanas_juntes ---

def test_genera_una_semana_por_cada_lunes_que_solapa_el_mes(db):
    ana = _usuario("Ana", "ana@test.es")
    semanas = construir_semanas_juntes(ana, 2026, 7)
    # Julio 2026 empieza en miércoles (1 jul) y termina en viernes (31 jul):
    # semanas con lunes 29/6, 6/7, 13/7, 20/7, 27/7
    lunes_generados = [s["lunes"] for s in semanas]
    assert lunes_generados == [
        date(2026, 6, 29), date(2026, 7, 6), date(2026, 7, 13),
        date(2026, 7, 20), date(2026, 7, 27),
    ]
    assert all(s["domingo"] == s["lunes"] + timedelta(days=6) for s in semanas)


def test_asigna_junte_a_la_semana_de_sus_turnos(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    # LMVD: cede viernes(10/7) y domingo(12/7); recibe martes(7/7) y jueves(9/7)
    _junte(
        pedro,
        cedidos=[date(2026, 7, 10), date(2026, 7, 12)],
        aceptados=[date(2026, 7, 7), date(2026, 7, 9)],
    )

    semanas = construir_semanas_juntes(ana, 2026, 7)
    semana_6_12 = next(s for s in semanas if s["lunes"] == date(2026, 7, 6))
    assert len(semana_6_12["ofertas"]) == 1
    oferta = semana_6_12["ofertas"][0]
    assert oferta["usuario_nombre"] == "Pedro"
    assert oferta["trabaja"] == frozenset([0, 1, 2, 3])  # L M X J
    assert oferta["libra"] == frozenset([4, 5, 6])  # V S D

    otras_semanas = [s for s in semanas if s["lunes"] != date(2026, 7, 6)]
    assert all(s["ofertas"] == [] for s in otras_semanas)


def test_varios_juntes_en_la_misma_semana(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    marta = _usuario("Marta", "marta@test.es")
    _junte(pedro, cedidos=[date(2026, 7, 10)], aceptados=[date(2026, 7, 7)])
    _junte(marta, cedidos=[date(2026, 7, 11)], aceptados=[date(2026, 7, 8)])

    semanas = construir_semanas_juntes(ana, 2026, 7)
    semana_6_12 = next(s for s in semanas if s["lunes"] == date(2026, 7, 6))
    nombres = {o["usuario_nombre"] for o in semana_6_12["ofertas"]}
    assert nombres == {"Pedro", "Marta"}


def test_excluye_publicaciones_no_junte(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = ana.unidad.grupo_intercambio_id
    noche = _franja(gid)
    pub = PublicacionCambio(usuario_id=pedro.id, tipo="cambio")
    db.session.add(pub)
    db.session.flush()
    db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=date(2026, 7, 7), franja_horaria_id=noche.id))
    db.session.commit()

    semanas = construir_semanas_juntes(ana, 2026, 7)
    assert all(s["ofertas"] == [] for s in semanas)


def test_excluye_publicaciones_propias_y_de_otra_categoria(db):
    insertar_categorias_semilla()
    cat_enf = Categoria.query.filter_by(nombre="Enfermería").first()
    cat_aux = Categoria.query.filter_by(nombre="Auxiliar de enfermería (TCAE)").first()
    ana = registrar_usuario("Ana", "ana@test.es", "password123", "H1", "Urgencias", cat_enf.id)
    otra_cat = registrar_usuario("Bea", "bea@test.es", "password123", "H1", "Urgencias", cat_aux.id)

    _junte(ana, cedidos=[date(2026, 7, 10)], aceptados=[date(2026, 7, 7)])
    _junte(otra_cat, cedidos=[date(2026, 7, 10)], aceptados=[date(2026, 7, 7)])

    semanas = construir_semanas_juntes(ana, 2026, 7)
    assert all(s["ofertas"] == [] for s in semanas)


def test_excluye_juntes_cancelados(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    _junte(pedro, cedidos=[date(2026, 7, 10)], aceptados=[date(2026, 7, 7)], estado="cancelada")

    semanas = construir_semanas_juntes(ana, 2026, 7)
    assert all(s["ofertas"] == [] for s in semanas)


# --- preparar_semanas_juntes ---

def test_preparar_marca_semanas_parciales_fuera_del_mes(db):
    ana = _usuario("Ana", "ana@test.es")
    semanas = construir_semanas_juntes(ana, 2026, 7)
    vista = preparar_semanas_juntes(semanas, 7)

    assert vista[0]["lunes"] == date(2026, 6, 29)
    assert vista[0]["es_parcial"] is True
    assert vista[1]["lunes"] == date(2026, 7, 6)
    assert vista[1]["es_parcial"] is False
    assert vista[-1]["es_parcial"] is True


def test_preparar_genera_tira_de_7_dias_trabaja_libra(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    _junte(
        pedro,
        cedidos=[date(2026, 7, 10), date(2026, 7, 12)],
        aceptados=[date(2026, 7, 7), date(2026, 7, 9)],
    )

    semanas = construir_semanas_juntes(ana, 2026, 7)
    vista = preparar_semanas_juntes(semanas, 7)
    semana_6_12 = next(s for s in vista if s["lunes"] == date(2026, 7, 6))
    oferta = semana_6_12["ofertas"][0]

    assert oferta["usuario_nombre"] == "Pedro"
    assert len(oferta["dias"]) == 7
    estados = [d["estado"] for d in oferta["dias"]]
    assert estados == ["trabaja", "trabaja", "trabaja", "trabaja", "libra", "libra", "libra"]
    letras = [d["letra"] for d in oferta["dias"]]
    assert letras == ["L", "M", "X", "J", "V", "S", "D"]
    assert oferta["trabaja_str"] == "lunes, martes, miércoles y jueves"
    assert oferta["libra_str"] == "viernes, sábado y domingo"
