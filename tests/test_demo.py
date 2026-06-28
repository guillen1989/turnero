"""Tests para el servicio y los endpoints de la unidad de demostración."""
import os

from app.extensions import db as _db
from app.models import Categoria, PublicacionCambio, Usuario, insertar_categorias_semilla
from app.services.demo import (
    DEMO_ACCOUNTS,
    DEMO_PASSWORD,
    DEMO_PAIS,
    DEMO_UNIDAD,
    reset_demo,
    ya_sembrado,
)
from app.services.registro import registrar_usuario


def _login_admin(client):
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    u = registrar_usuario("Admin", "admin@test.es", "pass1234", "H", "U", cat.id)
    u.es_admin = True
    _db.session.commit()
    client.post("/auth/login", data={"email": "admin@test.es", "password": "pass1234"})
    return u


# ─── servicio ────────────────────────────────────────────────────────────────

def test_reset_demo_crea_usuarios_demo(db):
    reset_demo()
    for _, email in DEMO_ACCOUNTS:
        assert Usuario.query.filter_by(email=email).first() is not None


def test_reset_demo_password_correcta(db):
    reset_demo()
    _, email = DEMO_ACCOUNTS[0]
    u = Usuario.query.filter_by(email=email).first()
    assert u.check_password(DEMO_PASSWORD)


def test_reset_demo_crea_publicaciones(db):
    reset_demo()
    assert PublicacionCambio.query.count() > 0


def test_ya_sembrado_false_antes_de_seed(db):
    assert ya_sembrado() is False


def test_ya_sembrado_true_despues_de_seed(db):
    reset_demo()
    assert ya_sembrado() is True


def test_reset_idempotente(db):
    reset_demo()
    usuarios_1 = Usuario.query.count()
    pubs_1 = PublicacionCambio.query.count()

    reset_demo()
    assert Usuario.query.count() == usuarios_1
    assert PublicacionCambio.query.count() == pubs_1


# ─── endpoint admin ───────────────────────────────────────────────────────────

def test_admin_demo_reset_requiere_login(client, db):
    resp = client.post("/admin/demo/reset", follow_redirects=False)
    assert resp.status_code in (302, 401, 403)


def test_admin_demo_reset_funciona(client, db):
    _login_admin(client)
    resp = client.post("/admin/demo/reset", follow_redirects=True)
    assert resp.status_code == 200
    assert Usuario.query.filter_by(email=DEMO_ACCOUNTS[0][1]).first() is not None


# ─── endpoint cron ────────────────────────────────────────────────────────────

def test_cron_reset_sin_token_env_devuelve_404(client, db):
    os.environ.pop("DEMO_RESET_TOKEN", None)
    resp = client.post("/admin/demo/reset-cron",
                       headers={"Authorization": "Bearer cualquiercosa"})
    assert resp.status_code == 404


def test_cron_reset_token_incorrecto_devuelve_403(client, db):
    os.environ["DEMO_RESET_TOKEN"] = "token-secreto"
    try:
        resp = client.post("/admin/demo/reset-cron",
                           headers={"Authorization": "Bearer token-malo"})
        assert resp.status_code == 403
    finally:
        os.environ.pop("DEMO_RESET_TOKEN", None)


def test_cron_reset_token_correcto_regenera(client, db):
    os.environ["DEMO_RESET_TOKEN"] = "token-secreto"
    try:
        resp = client.post("/admin/demo/reset-cron",
                           headers={"Authorization": "Bearer token-secreto"})
        assert resp.status_code == 200
        assert Usuario.query.filter_by(email=DEMO_ACCOUNTS[0][1]).first() is not None
    finally:
        os.environ.pop("DEMO_RESET_TOKEN", None)


# ─── planillas demo ───────────────────────────────────────────────────────────

def test_reset_demo_crea_planillas_mes(db):
    from app.models import PlanillaMes
    reset_demo()
    count = PlanillaMes.query.count()
    assert count >= 16  # 8 usuarios × 2 meses


def test_reset_demo_planillas_publicadas(db):
    from app.models import PlanillaMes
    reset_demo()
    sin_publicar = PlanillaMes.query.filter_by(publicada=False).count()
    assert sin_publicar == 0


def test_reset_demo_crea_turnos_planilla(db):
    from app.models import TurnoPlanilla
    reset_demo()
    assert TurnoPlanilla.query.count() > 0


# ─── onboarding demo ──────────────────────────────────────────────────────────

def test_demo_usuario_onboarding_visto_false(db):
    reset_demo()
    _, email = DEMO_ACCOUNTS[0]
    u = Usuario.query.filter_by(email=email).first()
    assert u.onboarding_visto is False


def test_es_demo_property_demo_accounts(db):
    reset_demo()
    for _, email in DEMO_ACCOUNTS:
        u = Usuario.query.filter_by(email=email).first()
        assert u.es_demo is True


def test_es_demo_property_bot_accounts(db):
    reset_demo()
    u = Usuario.query.filter_by(email="bot.maria@demo.turnero.com").first()
    assert u.es_demo is True


def test_como_funciona_no_marca_onboarding_demo(client, db):
    """Visitar Cómo funciona con cuenta demo no pone onboarding_visto=True."""
    reset_demo()
    _, email = DEMO_ACCOUNTS[0]
    client.post("/auth/login", data={"email": email, "password": DEMO_PASSWORD},
                follow_redirects=True)
    client.get("/como-funciona")
    u = Usuario.query.filter_by(email=email).first()
    assert u.onboarding_visto is False
