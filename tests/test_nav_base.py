from datetime import time
from app.models import Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria, Usuario


def _crear_usuario(db, es_supervisora, email):
    hospital = Hospital(nombre=f"H-{email}")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    unidad = Unidad(nombre="UCI", hospital=hospital, grupo_intercambio=grupo)
    categoria = Categoria(nombre=f"Cat-{email}")
    db.session.add_all([unidad, categoria])
    db.session.commit()

    usuario = Usuario(
        nombre="Ana", email=email, unidad=unidad, categoria=categoria,
        es_supervisora=es_supervisora,
    )
    usuario.set_password("pass")
    db.session.add(usuario)
    db.session.commit()
    return usuario


def _login(client, email):
    client.post("/auth/login", data={"email": email, "password": "pass"})


def test_enlaces_solo_de_supervisora_van_en_su_propia_fila(client, db):
    """Los enlaces exclusivos de supervisora deben ir agrupados en una fila
    aparte, para no apretar el resto de botones del menú principal."""
    _crear_usuario(db, es_supervisora=True, email="sup@test.es")
    _login(client, "sup@test.es")

    resp = client.get("/planilla/")
    html = resp.data.decode("utf-8")

    assert 'class="nav-supervisora-row"' in html
    inicio = html.index('class="nav-supervisora-row"')
    fin = html.index("</div>", inicio)
    fila = html[inicio:fin]

    assert "Supervisión de cambios" in fila
    assert "Supervisión de planilla" in fila
    assert "Importar planilla" in fila
    assert "Calendario" not in fila


def test_usuario_normal_no_ve_la_fila_de_supervisora(client, db):
    _crear_usuario(db, es_supervisora=False, email="normal@test.es")
    _login(client, "normal@test.es")

    resp = client.get("/planilla/")
    html = resp.data.decode("utf-8")

    assert 'class="nav-supervisora-row"' not in html
    assert "Supervisión de cambios" not in html
