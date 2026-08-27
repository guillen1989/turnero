import importlib.util
import pathlib

import pytest

from app.services.asistente.schema import PropuestaPublicacion

RUTA_SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "eval_parser.py"
_spec = importlib.util.spec_from_file_location("eval_parser", RUTA_SCRIPT)
eval_parser = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eval_parser)


def _propuesta(tipo="cambio", cedidos=None, aceptados=None, campos_faltantes=None):
    return PropuestaPublicacion(
        tipo=tipo,
        cedidos=[{"fecha": f, "franja": fr} for f, fr in (cedidos or [])],
        aceptados=[{"fecha": f, "franja": fr} for f, fr in (aceptados or [])],
        campos_faltantes=campos_faltantes or [],
    )


def _esperado(tipo="cambio", cedidos=None, aceptados=None):
    return {"tipo": tipo, "cedidos": cedidos or [], "aceptados": aceptados or []}


class TestCompararExacto:
    def test_coincide_exactamente(self):
        propuesta = _propuesta(cedidos=[("2026-09-11", "Tarde")], aceptados=[("2026-09-15", "Tarde")])
        esperado = _esperado(cedidos=[["2026-09-11", "Tarde"]], aceptados=[["2026-09-15", "Tarde"]])
        assert eval_parser.comparar_exacto(propuesta, esperado) is True

    def test_no_importa_el_orden_de_los_turnos(self):
        propuesta = _propuesta(cedidos=[("2026-09-11", "Tarde"), ("2026-09-12", "Tarde")])
        esperado = _esperado(cedidos=[["2026-09-12", "Tarde"], ["2026-09-11", "Tarde"]])
        assert eval_parser.comparar_exacto(propuesta, esperado) is True

    def test_falla_si_tipo_distinto(self):
        propuesta = _propuesta(tipo="peticion")
        esperado = _esperado(tipo="cambio")
        assert eval_parser.comparar_exacto(propuesta, esperado) is False

    def test_falla_si_falta_un_turno(self):
        propuesta = _propuesta(cedidos=[("2026-09-11", "Tarde")])
        esperado = _esperado(cedidos=[["2026-09-11", "Tarde"], ["2026-09-12", "Tarde"]])
        assert eval_parser.comparar_exacto(propuesta, esperado) is False

    def test_falla_si_sobra_un_turno(self):
        propuesta = _propuesta(cedidos=[["2026-09-11", "Tarde"], ["2026-09-12", "Tarde"]])
        esperado = _esperado(cedidos=[["2026-09-11", "Tarde"]])
        assert eval_parser.comparar_exacto(propuesta, esperado) is False

    def test_falla_si_la_franja_no_coincide(self):
        propuesta = _propuesta(cedidos=[("2026-09-11", "Mañana")])
        esperado = _esperado(cedidos=[["2026-09-11", "Tarde"]])
        assert eval_parser.comparar_exacto(propuesta, esperado) is False

    def test_franja_null_coincide_con_null(self):
        propuesta = _propuesta(aceptados=[("2026-09-11", None)])
        esperado = _esperado(aceptados=[["2026-09-11", None]])
        assert eval_parser.comparar_exacto(propuesta, esperado) is True


class TestDiagnosticar:
    def test_sin_fallos_devuelve_lista_vacia(self):
        propuesta = _propuesta(cedidos=[("2026-09-11", "Tarde")])
        esperado = _esperado(cedidos=[["2026-09-11", "Tarde"]])
        assert eval_parser.diagnosticar(propuesta, esperado) == []

    def test_marca_tipo_incorrecto(self):
        propuesta = _propuesta(tipo="peticion")
        esperado = _esperado(tipo="cambio")
        assert "tipo" in eval_parser.diagnosticar(propuesta, esperado)

    def test_marca_cedido_de_menos(self):
        propuesta = _propuesta(cedidos=[])
        esperado = _esperado(cedidos=[["2026-09-11", "Tarde"]])
        assert "cedido_de_menos" in eval_parser.diagnosticar(propuesta, esperado)

    def test_marca_cedido_de_mas(self):
        propuesta = _propuesta(cedidos=[("2026-09-11", "Tarde")])
        esperado = _esperado(cedidos=[])
        assert "cedido_de_mas" in eval_parser.diagnosticar(propuesta, esperado)

    def test_marca_aceptado_de_menos_y_de_mas(self):
        propuesta = _propuesta(aceptados=[("2026-09-11", "Tarde")])
        esperado = _esperado(aceptados=[["2026-09-12", "Tarde"]])
        fallos = eval_parser.diagnosticar(propuesta, esperado)
        assert "aceptado_de_menos" in fallos
        assert "aceptado_de_mas" in fallos


class TestErrorSilencioso:
    def test_no_es_error_silencioso_si_coincide(self):
        propuesta = _propuesta(cedidos=[("2026-09-11", "Tarde")])
        esperado = _esperado(cedidos=[["2026-09-11", "Tarde"]])
        assert eval_parser.es_error_silencioso(propuesta, esperado) is False

    def test_no_es_error_silencioso_si_se_abstiene(self):
        propuesta = _propuesta(cedidos=[], campos_faltantes=["cedidos"])
        esperado = _esperado(cedidos=[["2026-09-11", "Tarde"]])
        assert eval_parser.es_error_silencioso(propuesta, esperado) is False

    def test_es_error_silencioso_si_equivocada_y_sin_abstenerse(self):
        propuesta = _propuesta(cedidos=[("2026-09-12", "Tarde")])
        esperado = _esperado(cedidos=[["2026-09-11", "Tarde"]])
        assert eval_parser.es_error_silencioso(propuesta, esperado) is True


class TestCargarCorpus:
    def test_ignora_entradas_sin_anotar(self, tmp_path):
        ruta = tmp_path / "corpus.jsonl"
        ruta.write_text(
            '{"id": "w001", "texto": "a", "fecha_mensaje": "2026-08-01", "esperado": null}\n'
            '{"id": "w002", "texto": "b", "fecha_mensaje": "2026-08-01", '
            '"esperado": {"tipo": "cambio", "cedidos": [], "aceptados": []}}\n'
        )
        entradas = eval_parser.cargar_corpus(ruta)
        assert [e["id"] for e in entradas] == ["w002"]


class TestEvaluarCorpus:
    def test_agrega_metricas_sobre_varias_entradas(self):
        entradas = [
            {
                "id": "w001",
                "texto": "texto1",
                "fecha_mensaje": "2026-08-01",
                "esperado": _esperado(cedidos=[["2026-09-11", "Tarde"]]),
            },
            {
                "id": "w002",
                "texto": "texto2",
                "fecha_mensaje": "2026-08-01",
                "esperado": _esperado(cedidos=[["2026-09-11", "Tarde"]]),
            },
        ]
        respuestas = {
            "w001": _propuesta(cedidos=[("2026-09-11", "Tarde")]),
            "w002": _propuesta(cedidos=[("2026-09-12", "Tarde")]),
        }

        resultado = eval_parser.evaluar_corpus(
            entradas,
            contexto_base={"franjas": [], "tipos_validos": ["cambio"]},
            extraer=lambda texto, contexto, id_entrada: respuestas[id_entrada],
        )

        assert resultado["total"] == 2
        assert resultado["exact_match"] == 1
        assert resultado["exact_match_rate"] == pytest.approx(0.5)
        assert resultado["error_silencioso"] == 1
        assert resultado["error_silencioso_rate"] == pytest.approx(0.5)
        assert resultado["histograma_fallos"] == {"cedido_de_mas": 1, "cedido_de_menos": 1}

    def test_una_excepcion_al_extraer_no_interrumpe_la_evaluacion(self):
        entradas = [
            {
                "id": "w001",
                "texto": "texto invalido",
                "fecha_mensaje": "2026-08-01",
                "esperado": _esperado(cedidos=[["2026-09-11", "Tarde"]]),
            },
            {
                "id": "w002",
                "texto": "texto2",
                "fecha_mensaje": "2026-08-01",
                "esperado": _esperado(cedidos=[["2026-09-11", "Tarde"]]),
            },
        ]

        def extraer_falso(texto, contexto, id_entrada):
            if id_entrada == "w001":
                raise ValueError("fecha '' no tiene formato ISO")
            return _propuesta(cedidos=[("2026-09-11", "Tarde")])

        resultado = eval_parser.evaluar_corpus(
            entradas,
            contexto_base={"franjas": [], "tipos_validos": ["cambio"]},
            extraer=extraer_falso,
        )

        assert resultado["total"] == 2
        assert resultado["exact_match"] == 1
        assert resultado["error_silencioso"] == 0
        assert resultado["histograma_fallos"] == {"fallo_extraccion": 1}


class TestDetallarFallos:
    def test_solo_incluye_las_entradas_que_fallan(self):
        entradas = [
            {
                "id": "w001",
                "texto": "texto acertado",
                "fecha_mensaje": "2026-08-01",
                "esperado": _esperado(cedidos=[["2026-09-11", "Tarde"]]),
            },
            {
                "id": "w002",
                "texto": "texto fallido",
                "fecha_mensaje": "2026-08-01",
                "esperado": _esperado(tipo="cambio", cedidos=[["2026-09-11", "Tarde"]]),
            },
        ]
        respuestas = {
            "w001": _propuesta(cedidos=[("2026-09-11", "Tarde")]),
            "w002": _propuesta(tipo="peticion", cedidos=[]),
        }

        detalles = eval_parser.detallar_fallos(
            entradas,
            contexto_base={"franjas": [], "tipos_validos": ["cambio", "peticion"]},
            extraer=lambda texto, contexto, id_entrada: respuestas[id_entrada],
        )

        assert len(detalles) == 1
        assert detalles[0]["id"] == "w002"
        assert detalles[0]["texto"] == "texto fallido"
        assert "tipo" in detalles[0]["fallos"]
        assert detalles[0]["obtenido"]["tipo"] == "peticion"

    def test_registra_las_excepciones_de_extraccion(self):
        entradas = [
            {
                "id": "w001",
                "texto": "texto raro",
                "fecha_mensaje": "2026-08-01",
                "esperado": _esperado(cedidos=[["2026-09-11", "Tarde"]]),
            }
        ]

        def extraer_falso(texto, contexto, id_entrada):
            raise ValueError("fecha '' no tiene formato ISO")

        detalles = eval_parser.detallar_fallos(
            entradas, contexto_base={"franjas": [], "tipos_validos": ["cambio"]}, extraer=extraer_falso
        )

        assert len(detalles) == 1
        assert detalles[0]["id"] == "w001"
        assert "fecha '' no tiene formato ISO" in detalles[0]["error"]
