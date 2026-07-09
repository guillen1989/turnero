"""Tests del servicio de agregación mensual para el calendario visual de
ofertas/peticiones (Paso 1 del plan). Módulo puro: agrupa turnos abiertos
de publicaciones activas y visibles para el usuario, por fecha y franja.
"""
from datetime import date

import pytest

from app.extensions import db
from app.models import (
    Categoria,
    FranjaHoraria,
    PublicacionCambio,
    TurnoAceptado,
    TurnoCedido,
    insertar_categorias_semilla,
)
from app.services.calendario_mercado import construir_calendario_mes, preparar_celdas_mes
from app.services.registro import registrar_usuario


# --- Helpers ---

def _categoria(nombre="Enfermería"):
    insertar_categorias_semilla()
    return Categoria.query.filter_by(nombre=nombre).first()


def _usuario(nombre, email, hospital="H1", unidad="Urgencias", categoria=None):
    if categoria is None:
        categoria = _categoria()
    return registrar_usuario(nombre, email, "password123", hospital, unidad, categoria.id)


def _franja(grupo_id, nombre="Mañana"):
    return FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_id, nombre=nombre).first()


def _pub(usuario, tipo, cedidos=None, aceptados=None, estado="abierta", es_sintetica=False):
    """cedidos/aceptados: lista de (fecha, franja) o (fecha, franja, cualquier_franja)."""
    pub = PublicacionCambio(usuario_id=usuario.id, tipo=tipo, estado=estado, es_sintetica=es_sintetica)
    db.session.add(pub)
    db.session.flush()
    for item in (cedidos or []):
        fecha, franja = item[0], item[1]
        db.session.add(TurnoCedido(publicacion_id=pub.id, fecha=fecha, franja_horaria_id=franja.id))
    for item in (aceptados or []):
        fecha, franja = item[0], item[1]
        cualquier = item[2] if len(item) > 2 else False
        db.session.add(TurnoAceptado(
            publicacion_id=pub.id, fecha=fecha,
            franja_horaria_id=None if cualquier else franja.id,
            cualquier_franja=cualquier,
        ))
    db.session.commit()
    return pub


# --- Ofertas: agrupa turno_aceptado ---

def test_ofertas_agrupa_turno_aceptado_por_fecha_y_franja(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = ana.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")

    pub = _pub(pedro, "regalo", aceptados=[(date(2026, 7, 3), manana)])

    resultado = construir_calendario_mes(ana, 2026, 7, "ofertas")
    assert resultado == {date(2026, 7, 3): {manana.id: [pub.id]}}


def test_peticiones_agrupa_turno_cedido_por_fecha_y_franja(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = ana.unidad.grupo_intercambio_id
    tarde = _franja(gid, "Tarde")

    pub = _pub(pedro, "peticion", cedidos=[(date(2026, 7, 5), tarde)])

    resultado = construir_calendario_mes(ana, 2026, 7, "peticiones")
    assert resultado == {date(2026, 7, 5): {tarde.id: [pub.id]}}


# --- Tipo 'cambio' cuenta en ambos modos ---

def test_ofertas_incluye_turno_aceptado_de_tipo_cambio(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = ana.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")
    noche = _franja(gid, "Noche")

    pub = _pub(pedro, "cambio", cedidos=[(date(2026, 7, 1), noche)], aceptados=[(date(2026, 7, 3), manana)])

    resultado = construir_calendario_mes(ana, 2026, 7, "ofertas")
    assert resultado[date(2026, 7, 3)] == {manana.id: [pub.id]}


def test_peticiones_incluye_turno_cedido_de_tipo_cambio(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = ana.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")
    noche = _franja(gid, "Noche")

    pub = _pub(pedro, "cambio", cedidos=[(date(2026, 7, 1), noche)], aceptados=[(date(2026, 7, 3), manana)])

    resultado = construir_calendario_mes(ana, 2026, 7, "peticiones")
    assert resultado[date(2026, 7, 1)] == {noche.id: [pub.id]}


# --- cambio_dia cuenta en ambos modos ---

def test_cambio_dia_aparece_en_ofertas_y_peticiones(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = ana.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")
    tarde = _franja(gid, "Tarde")

    pub = _pub(pedro, "cambio_dia", cedidos=[(date(2026, 7, 10), manana)], aceptados=[(date(2026, 7, 10), tarde)])

    ofertas = construir_calendario_mes(ana, 2026, 7, "ofertas")
    peticiones = construir_calendario_mes(ana, 2026, 7, "peticiones")
    assert ofertas[date(2026, 7, 10)] == {tarde.id: [pub.id]}
    assert peticiones[date(2026, 7, 10)] == {manana.id: [pub.id]}


# --- Exclusiones ---

def test_excluye_tipo_junte(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = ana.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")

    _pub(pedro, "junte", aceptados=[(date(2026, 7, 3), manana)])

    assert construir_calendario_mes(ana, 2026, 7, "ofertas") == {}


def test_excluye_publicaciones_propias(db):
    ana = _usuario("Ana", "ana@test.es")
    gid = ana.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")

    _pub(ana, "regalo", aceptados=[(date(2026, 7, 3), manana)])

    assert construir_calendario_mes(ana, 2026, 7, "ofertas") == {}


def test_excluye_categoria_distinta(db):
    cat_enf = _categoria("Enfermería")
    cat_aux = _categoria("Auxiliar de enfermería (TCAE)")
    ana = _usuario("Ana", "ana@test.es", categoria=cat_enf)
    pedro = _usuario("Pedro", "pedro@test.es", categoria=cat_aux)
    gid = ana.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")

    _pub(pedro, "regalo", aceptados=[(date(2026, 7, 3), manana)])

    assert construir_calendario_mes(ana, 2026, 7, "ofertas") == {}


def test_excluye_grupo_intercambio_distinto(db):
    ana = _usuario("Ana", "ana@test.es", unidad="Urgencias")
    pedro = _usuario("Pedro", "pedro@test.es", unidad="Traumatología")
    gid_pedro = pedro.unidad.grupo_intercambio_id
    manana = _franja(gid_pedro, "Mañana")

    _pub(pedro, "regalo", aceptados=[(date(2026, 7, 3), manana)])

    assert construir_calendario_mes(ana, 2026, 7, "ofertas") == {}


@pytest.mark.parametrize("estado", ["cancelada", "caducada", "confirmada"])
def test_excluye_publicaciones_no_activas(db, estado):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = ana.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")

    _pub(pedro, "regalo", aceptados=[(date(2026, 7, 3), manana)], estado=estado)

    assert construir_calendario_mes(ana, 2026, 7, "ofertas") == {}


def test_incluye_sinteticas_en_ofertas(db):
    """Las oportunidades a 3 (publicaciones sintéticas) también se muestran en
    el calendario — son justo el tipo de match más difícil de descubrir.

    Para una sintética, crear_pub_sintetica() copia como turno_cedido el
    ACEPTADO de pub_a (una oferta real: alguien que sí trabajaría ese día),
    así que en el calendario debe aparecer en 'ofertas', no en 'peticiones'."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = ana.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")

    pub = _pub(pedro, "cambio", cedidos=[(date(2026, 7, 3), manana)], es_sintetica=True)

    assert construir_calendario_mes(ana, 2026, 7, "ofertas") == {date(2026, 7, 3): {manana.id: [pub.id]}}


def test_incluye_sinteticas_en_peticiones(db):
    """Simétrico al anterior: crear_pub_sintetica() copia como turno_aceptado
    el CEDIDO de pub_b (una petición real: alguien que necesita cobertura),
    así que en el calendario debe aparecer en 'peticiones', no en 'ofertas'."""
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = ana.unidad.grupo_intercambio_id
    tarde = _franja(gid, "Tarde")

    pub = _pub(pedro, "cambio", aceptados=[(date(2026, 7, 5), tarde)], es_sintetica=True)

    assert construir_calendario_mes(ana, 2026, 7, "peticiones") == {date(2026, 7, 5): {tarde.id: [pub.id]}}


def test_sintetica_generada_por_crear_pub_sintetica_muestra_peticion_de_b_en_peticiones(db):
    """Regresión: caso real de una oportunidad a 3 (issue del calendario
    'al revés'). Victoria (pub_b) publica un cambio pidiendo cobertura para
    una noche; Marta (pub_a) puede cubrirla y a cambio acepta trabajar otro
    día. La sintética resultante debe mostrar la noche de Victoria como
    petición (necesita voluntario), no como oferta."""
    from app.matching.service import crear_pub_sintetica

    marta = _usuario("Marta", "marta@test.es")
    victoria = _usuario("Victoria", "victoria@test.es")
    # Viewer distinto de marta y victoria: la sintética queda excluida del
    # calendario de su propia autora (marta, dueña de pub_a), así que hace
    # falta un tercero para verla como candidata.
    carla = _usuario("Carla", "carla@test.es")
    gid = marta.unidad.grupo_intercambio_id
    noche = _franja(gid, "Noche")
    manana = _franja(gid, "Mañana")

    pub_a = _pub(marta, "cambio", aceptados=[(date(2026, 8, 13), manana)])
    pub_b = _pub(victoria, "cambio", cedidos=[(date(2026, 8, 6), noche)])

    sint = crear_pub_sintetica(pub_a, pub_b)

    peticiones = construir_calendario_mes(carla, 2026, 8, "peticiones")
    ofertas = construir_calendario_mes(carla, 2026, 8, "ofertas")

    assert sint.id in peticiones[date(2026, 8, 6)][noche.id]
    assert sint.id not in ofertas.get(date(2026, 8, 6), {}).get(noche.id, [])


def test_excluye_turnos_fuera_de_mes(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = ana.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")

    _pub(pedro, "regalo", aceptados=[(date(2026, 8, 1), manana)])

    assert construir_calendario_mes(ana, 2026, 7, "ofertas") == {}


def test_excluye_turnos_ya_resueltos(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = ana.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")

    pub = _pub(pedro, "regalo", aceptados=[(date(2026, 7, 3), manana)])
    pub.turnos_aceptados[0].estado = "resuelto"
    db.session.commit()

    assert construir_calendario_mes(ana, 2026, 7, "ofertas") == {}


# --- cualquier_franja ---

def test_cualquier_franja_se_agrupa_bajo_clave_especial(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = ana.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")

    pub = _pub(pedro, "regalo", aceptados=[(date(2026, 7, 3), manana, True)])

    resultado = construir_calendario_mes(ana, 2026, 7, "ofertas")
    assert resultado == {date(2026, 7, 3): {"cualquiera": [pub.id]}}


# --- Multi-turno ---

def test_multiples_turnos_misma_publicacion_caen_en_dias_distintos(db):
    ana = _usuario("Ana", "ana@test.es")
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = ana.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")
    noche = _franja(gid, "Noche")

    pub = _pub(pedro, "regalo", aceptados=[
        (date(2026, 7, 3), manana),
        (date(2026, 7, 8), noche),
    ])

    resultado = construir_calendario_mes(ana, 2026, 7, "ofertas")
    assert resultado == {
        date(2026, 7, 3): {manana.id: [pub.id]},
        date(2026, 7, 8): {noche.id: [pub.id]},
    }


# --- Validación de modo ---

def test_modo_invalido_lanza_error(db):
    ana = _usuario("Ana", "ana@test.es")
    with pytest.raises(ValueError):
        construir_calendario_mes(ana, 2026, 7, "juntes")


# --- preparar_celdas_mes (Paso 3: presentación del grid) ---

def test_preparar_celdas_dia_sin_franjas_es_vacio(db):
    ana = _usuario("Ana", "ana@test.es")
    gid = ana.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")

    dias = [date(2026, 7, 1), date(2026, 7, 2)]
    celdas = preparar_celdas_mes(dias, {}, [manana])

    assert celdas[date(2026, 7, 1)] == {"mod": "cal-celda--vacio", "estilo": "", "etiqueta": "", "tooltip": "", "bandas": []}
    assert celdas[date(2026, 7, 2)] == {"mod": "cal-celda--vacio", "estilo": "", "etiqueta": "", "tooltip": "", "bandas": []}


def test_preparar_celdas_dia_con_una_franja(db):
    ana = _usuario("Ana", "ana@test.es")
    gid = ana.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")

    dias = [date(2026, 7, 1)]
    calendario_mes = {date(2026, 7, 1): {manana.id: [1]}}
    celdas = preparar_celdas_mes(dias, calendario_mes, [manana])

    celda = celdas[date(2026, 7, 1)]
    assert celda["mod"] == "cal-celda--turno"
    color = manana.color or "#3B82F6"
    assert color in celda["estilo"]
    assert celda["etiqueta"] == "M"
    assert celda["tooltip"] == "Mañana"


def test_preparar_celdas_dia_con_cualquier_franja(db):
    ana = _usuario("Ana", "ana@test.es")
    gid = ana.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")

    dias = [date(2026, 7, 1)]
    calendario_mes = {date(2026, 7, 1): {"cualquiera": [1]}}
    celdas = preparar_celdas_mes(dias, calendario_mes, [manana])

    celda = celdas[date(2026, 7, 1)]
    assert celda["mod"] == "cal-celda--turno"
    assert celda["etiqueta"] == "?"
    assert celda["tooltip"] == "Cualquiera"


def test_preparar_celdas_dia_con_dos_franjas_genera_una_banda_por_franja(db):
    ana = _usuario("Ana", "ana@test.es")
    gid = ana.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")
    tarde = _franja(gid, "Tarde")

    dias = [date(2026, 7, 1)]
    calendario_mes = {date(2026, 7, 1): {manana.id: [1], tarde.id: [2]}}
    celdas = preparar_celdas_mes(dias, calendario_mes, [manana, tarde])

    celda = celdas[date(2026, 7, 1)]
    assert celda["mod"] == "cal-celda--multi"
    assert celda["estilo"] == ""
    assert celda["etiqueta"] == ""
    assert celda["tooltip"] == "Mañana, Tarde"
    assert celda["bandas"] == [
        {"color": manana.color or "#3B82F6", "color_texto": manana.color_texto, "letra": "M"},
        {"color": tarde.color, "color_texto": tarde.color_texto, "letra": "T"},
    ]


def test_preparar_celdas_banda_usa_color_texto_legible_sobre_color_claro(db):
    """Regresión: una franja personalizada con un color claro (p. ej. amarillo)
    debe llevar texto oscuro en su banda, no blanco fijo — igual que ya hace
    el caso de una sola franja con franja.color_texto."""
    ana = _usuario("Ana", "ana@test.es")
    gid = ana.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")
    from app.models import FranjaHoraria
    from datetime import time
    amarilla = FranjaHoraria(
        nombre="Turno personalizado", hora_inicio=time(6, 0), hora_fin=time(6, 0),
        grupo_intercambio_id=gid, color="#EAB308",
    )
    db.session.add(amarilla)
    db.session.commit()

    dias = [date(2026, 7, 1)]
    calendario_mes = {date(2026, 7, 1): {manana.id: [1], amarilla.id: [2]}}
    celdas = preparar_celdas_mes(dias, calendario_mes, [amarilla, manana])

    bandas = celdas[date(2026, 7, 1)]["bandas"]
    banda_amarilla = next(b for b in bandas if b["color"] == "#EAB308")
    assert banda_amarilla["color_texto"] == amarilla.color_texto
    assert banda_amarilla["color_texto"] != "#ffffff"


def test_preparar_celdas_bandas_respetan_orden_por_hora_inicio(db):
    """Las bandas siguen el orden cronológico de las franjas, no el de inserción."""
    ana = _usuario("Ana", "ana@test.es")
    gid = ana.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")
    tarde = _franja(gid, "Tarde")
    noche = _franja(gid, "Noche")

    dias = [date(2026, 7, 1)]
    # Insertadas en desorden en el dict de datos (Noche, Mañana, Tarde)
    calendario_mes = {date(2026, 7, 1): {noche.id: [1], manana.id: [2], tarde.id: [3]}}
    celdas = preparar_celdas_mes(dias, calendario_mes, [manana, tarde, noche])

    bandas = celdas[date(2026, 7, 1)]["bandas"]
    assert [b["letra"] for b in bandas] == ["M", "T", "N"]
    assert bandas[0]["color"] == (manana.color or "#3B82F6")
    assert bandas[1]["color"] == tarde.color
    assert bandas[2]["color"] == noche.color


def test_preparar_celdas_cualquiera_va_al_final_de_las_bandas(db):
    ana = _usuario("Ana", "ana@test.es")
    gid = ana.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")
    tarde = _franja(gid, "Tarde")

    dias = [date(2026, 7, 1)]
    calendario_mes = {date(2026, 7, 1): {"cualquiera": [1], manana.id: [2], tarde.id: [3]}}
    celdas = preparar_celdas_mes(dias, calendario_mes, [manana, tarde])

    bandas = celdas[date(2026, 7, 1)]["bandas"]
    assert [b["letra"] for b in bandas] == ["M", "T", "?"]
    assert bandas[-1]["color"] == "#9333ea"


def test_preparar_celdas_mas_de_cuatro_franjas_usa_fallback_neutro(db):
    """Más de 4 tipos distintos: demasiadas bandas serían ilegibles, se mantiene
    el tratamiento neutro con el número de tipos distintos."""
    ana = _usuario("Ana", "ana@test.es")
    gid = ana.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")
    tarde = _franja(gid, "Tarde")
    noche = _franja(gid, "Noche")
    from app.models import FranjaHoraria
    from datetime import time
    f4 = FranjaHoraria(nombre="Guardia especial A", hora_inicio=time(6, 0), hora_fin=time(6, 0), grupo_intercambio_id=gid, color="#111111")
    f5 = FranjaHoraria(nombre="Guardia especial B", hora_inicio=time(9, 0), hora_fin=time(21, 0), grupo_intercambio_id=gid, color="#222222")
    db.session.add_all([f4, f5])
    db.session.commit()

    dias = [date(2026, 7, 1)]
    calendario_mes = {date(2026, 7, 1): {
        manana.id: [1], tarde.id: [2], noche.id: [3], f4.id: [4], f5.id: [5],
    }}
    celdas = preparar_celdas_mes(dias, calendario_mes, [manana, tarde, noche, f4, f5])

    celda = celdas[date(2026, 7, 1)]
    assert celda["mod"] == "cal-celda--multi"
    assert celda["bandas"] == []
    assert celda["etiqueta"] == "5"


# --- resumen_publicaciones (Paso 4: datos mínimos para el drill-down) ---

def test_resumen_publicaciones_devuelve_usuario_y_tipo(db):
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = pedro.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")
    pub = _pub(pedro, "regalo", aceptados=[(date(2026, 7, 3), manana)])

    from app.services.calendario_mercado import resumen_publicaciones
    resumen = resumen_publicaciones([pub.id])

    assert resumen == [{"id": pub.id, "usuario_nombre": "Pedro", "tipo": "regalo", "es_sintetica": False}]


def test_resumen_publicaciones_indica_si_es_sintetica(db):
    pedro = _usuario("Pedro", "pedro@test.es")
    gid = pedro.unidad.grupo_intercambio_id
    manana = _franja(gid, "Mañana")
    pub = _pub(pedro, "cambio", aceptados=[(date(2026, 7, 3), manana)], es_sintetica=True)

    from app.services.calendario_mercado import resumen_publicaciones
    resumen = resumen_publicaciones([pub.id])

    assert resumen == [{"id": pub.id, "usuario_nombre": "Pedro", "tipo": "cambio", "es_sintetica": True}]


def test_resumen_publicaciones_lista_vacia_sin_ids(db):
    from app.services.calendario_mercado import resumen_publicaciones
    assert resumen_publicaciones([]) == []
