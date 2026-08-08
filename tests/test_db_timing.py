import logging
import time

from flask import Flask

from app.db_timing import init_db_timing


class _FakeConn:
    pass


class _FakePool:
    def __init__(self):
        self.calls = 0
        self._creator = self._crear_conexion

    def _crear_conexion(self):
        self.calls += 1
        time.sleep(0.01)
        return _FakeConn()


class _FakeEngine:
    def __init__(self):
        self.pool = _FakePool()


def test_no_envuelve_el_creator_si_esta_deshabilitado():
    app = Flask(__name__)
    app.config["DB_TIMING_ENABLED"] = False
    engine = _FakeEngine()
    original_creator = engine.pool._creator

    init_db_timing(app, engine)

    assert engine.pool._creator is original_creator


def test_envuelve_el_creator_si_esta_habilitado():
    app = Flask(__name__)
    app.config["DB_TIMING_ENABLED"] = True
    engine = _FakeEngine()
    original_creator = engine.pool._creator

    init_db_timing(app, engine)

    assert engine.pool._creator is not original_creator
    conn = engine.pool._creator()
    assert isinstance(conn, _FakeConn)
    assert engine.pool.calls == 1


def test_registra_connect_ms_y_rest_ms_por_peticion(caplog):
    app = Flask(__name__)
    app.config["DB_TIMING_ENABLED"] = True
    engine = _FakeEngine()
    init_db_timing(app, engine)

    @app.route("/ping")
    def ping():
        engine.pool._creator()
        return "ok"

    caplog.set_level(logging.INFO, logger="db_timing")
    resp = app.test_client().get("/ping")

    assert resp.status_code == 200
    resumenes = [
        r.message for r in caplog.records
        if r.name == "db_timing" and r.message.startswith("db_timing endpoint=")
    ]
    assert len(resumenes) == 1
    resumen = resumenes[0]
    assert "endpoint=ping" in resumen
    assert "connect_ms=" in resumen
    assert "rest_ms=" in resumen


def test_no_registra_nada_si_esta_deshabilitado(caplog):
    app = Flask(__name__)
    app.config["DB_TIMING_ENABLED"] = False
    engine = _FakeEngine()
    init_db_timing(app, engine)

    @app.route("/ping")
    def ping():
        return "ok"

    caplog.set_level(logging.INFO, logger="db_timing")
    app.test_client().get("/ping")

    assert not [r for r in caplog.records if r.name == "db_timing"]
