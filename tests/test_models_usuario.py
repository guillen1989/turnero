import pytest
from app.models import Usuario, Hospital, GrupoIntercambio, Unidad, Categoria


def _crear_contexto(db):
    """Crea hospital, grupo, unidad y categoría base para los tests de usuario."""
    hospital = Hospital(nombre="Hospital Test")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    unidad = Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo)
    categoria = Categoria(nombre="Enfermería")
    db.session.add_all([unidad, categoria])
    db.session.commit()

    return unidad, categoria


def test_crear_usuario(db):
    unidad, categoria = _crear_contexto(db)

    usuario = Usuario(nombre="Ana García", email="ana@hospital.es", unidad=unidad, categoria=categoria)
    usuario.set_password("contraseña-segura")
    db.session.add(usuario)
    db.session.commit()

    recuperado = db.session.get(Usuario, usuario.id)
    assert recuperado.email == "ana@hospital.es"
    assert recuperado.nombre == "Ana García"
    assert recuperado.locale == "es"


def test_password_no_se_guarda_en_claro(db):
    unidad, categoria = _crear_contexto(db)

    usuario = Usuario(nombre="Pedro López", email="pedro@hospital.es", unidad=unidad, categoria=categoria)
    usuario.set_password("mi-contraseña")
    db.session.add(usuario)
    db.session.commit()

    assert usuario.password_hash != "mi-contraseña"
    assert usuario.check_password("mi-contraseña") is True
    assert usuario.check_password("contraseña-incorrecta") is False


def test_email_unico(db):
    unidad, categoria = _crear_contexto(db)

    u1 = Usuario(nombre="Ana García", email="repetido@hospital.es", unidad=unidad, categoria=categoria)
    u1.set_password("pass1")
    db.session.add(u1)
    db.session.commit()

    u2 = Usuario(nombre="Ana Otra", email="repetido@hospital.es", unidad=unidad, categoria=categoria)
    u2.set_password("pass2")
    db.session.add(u2)
    with pytest.raises(Exception):
        db.session.commit()


def test_grupo_intercambio_accesible_desde_usuario(db):
    hospital = Hospital(nombre="Hospital GI")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    unidad = Unidad(nombre="Planta 3", hospital=hospital, grupo_intercambio=grupo)
    categoria = Categoria(nombre="Celador/a")
    db.session.add_all([unidad, categoria])
    db.session.commit()

    usuario = Usuario(nombre="Luis Ruiz", email="luis@hospital.es", unidad=unidad, categoria=categoria)
    usuario.set_password("pass")
    db.session.add(usuario)
    db.session.commit()

    assert usuario.grupo_intercambio.id == grupo.id


def test_usuario_es_flask_login_compatible(db):
    unidad, categoria = _crear_contexto(db)

    usuario = Usuario(nombre="María Sanz", email="maria@hospital.es", unidad=unidad, categoria=categoria)
    usuario.set_password("pass")
    db.session.add(usuario)
    db.session.commit()

    assert usuario.is_authenticated is True
    assert usuario.is_active is True
    assert usuario.get_id() == str(usuario.id)


def test_firma_guardada_es_opcional_y_persiste(db):
    unidad, categoria = _crear_contexto(db)

    usuario = Usuario(nombre="Rosa Díaz", email="rosa@hospital.es", unidad=unidad, categoria=categoria)
    usuario.set_password("pass")
    db.session.add(usuario)
    db.session.commit()

    recuperado = db.session.get(Usuario, usuario.id)
    assert recuperado.firma_guardada is None

    recuperado.firma_guardada = "data:image/png;base64,AAA"
    db.session.commit()

    recuperado2 = db.session.get(Usuario, usuario.id)
    assert recuperado2.firma_guardada == "data:image/png;base64,AAA"
