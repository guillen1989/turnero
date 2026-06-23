"""
Tests del servicio de registro: lógica de negocio pura, sin HTTP.
Cubre UAT-1.1 a UAT-1.4.
"""
import pytest
from app.models import Hospital, GrupoIntercambio, Unidad, Categoria, Usuario, FranjaHoraria
from app.services.registro import (
    encontrar_o_crear_hospital,
    encontrar_o_crear_unidad,
    encontrar_o_crear_categoria,
    registrar_usuario,
)


# --- Hospital ---

def test_crea_hospital_si_no_existe(db):
    hospital = encontrar_o_crear_hospital("Hospital La Paz")
    db.session.commit()
    assert Hospital.query.filter_by(nombre="Hospital La Paz").count() == 1


def test_reutiliza_hospital_existente(db):
    db.session.add(Hospital(nombre="Hospital La Paz"))
    db.session.commit()

    hospital = encontrar_o_crear_hospital("Hospital La Paz")
    db.session.commit()

    assert Hospital.query.filter_by(nombre="Hospital La Paz").count() == 1
    assert hospital.id is not None


def test_hospital_coincide_ignorando_mayusculas(db):
    db.session.add(Hospital(nombre="Hospital La Paz"))
    db.session.commit()

    hospital = encontrar_o_crear_hospital("hospital la paz")
    db.session.commit()

    assert Hospital.query.count() == 1
    assert hospital.nombre == "Hospital La Paz"


# --- Unidad ---

def test_crea_unidad_y_grupo_si_no_existe(db):
    hospital = encontrar_o_crear_hospital("Hospital Norte")
    db.session.commit()

    unidad, is_new = encontrar_o_crear_unidad("Urgencias", hospital)
    db.session.commit()

    assert is_new is True
    assert Unidad.query.filter_by(nombre="Urgencias").count() == 1
    assert GrupoIntercambio.query.count() == 1
    assert unidad.grupo_intercambio is not None


def test_reutiliza_unidad_existente_en_mismo_hospital(db):
    hospital = Hospital(nombre="Hospital Sur")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.flush()
    db.session.add(Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo))
    db.session.commit()

    unidad, is_new = encontrar_o_crear_unidad("Urgencias", hospital)
    db.session.commit()

    assert is_new is False
    assert Unidad.query.filter_by(nombre="Urgencias").count() == 1


def test_misma_unidad_distinto_hospital_se_crea_separada(db):
    h1 = Hospital(nombre="Hospital A")
    h2 = Hospital(nombre="Hospital B")
    grupo = GrupoIntercambio()
    db.session.add_all([h1, h2, grupo])
    db.session.flush()
    db.session.add(Unidad(nombre="Urgencias", hospital=h1, grupo_intercambio=grupo))
    db.session.commit()

    _, _ = encontrar_o_crear_unidad("Urgencias", h2)
    db.session.commit()

    assert Unidad.query.filter_by(nombre="Urgencias").count() == 2


# --- Categoría ---

def test_devuelve_categoria_por_id(db):
    cat = Categoria(nombre="Enfermería")
    db.session.add(cat)
    db.session.commit()

    resultado = encontrar_o_crear_categoria(cat.id, None)
    assert resultado.id == cat.id


def test_crea_categoria_nueva_si_no_existe(db):
    resultado = encontrar_o_crear_categoria(None, "Óptico/a")
    db.session.commit()
    assert Categoria.query.filter_by(nombre="Óptico/a").count() == 1


def test_categoria_nueva_evita_duplicado_obvio(db):
    """UAT-1.4: no duplica categorías que difieren solo en mayúsculas/espacios."""
    db.session.add(Categoria(nombre="Enfermería"))
    db.session.commit()

    resultado = encontrar_o_crear_categoria(None, "enfermería")
    db.session.commit()

    assert Categoria.query.count() == 1
    assert resultado.nombre == "Enfermería"


# --- Registro completo ---

def test_registrar_usuario_crea_todo(db):
    """UAT-1.1: registro con entidades nuevas crea usuario asociado."""
    from app.models.categoria import CATEGORIAS_SEMILLA
    from app.models import insertar_categorias_semilla
    insertar_categorias_semilla()

    cat = Categoria.query.filter_by(nombre="Enfermería").first()

    usuario = registrar_usuario(
        nombre="Ana García",
        email="ana@hospital.es",
        password="contraseña123",
        hospital_nombre="Hospital La Paz",
        unidad_nombre="Urgencias",
        categoria_id=cat.id,
        categoria_nueva_nombre=None,
    )

    assert usuario.id is not None
    assert usuario.email == "ana@hospital.es"
    assert usuario.unidad.nombre == "Urgencias"
    assert usuario.unidad.hospital.nombre == "Hospital La Paz"
    assert usuario.categoria.nombre == "Enfermería"
    assert usuario.check_password("contraseña123")


def test_registro_crea_franjas_horarias_por_defecto(db):
    from app.models import insertar_categorias_semilla
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    usuario = registrar_usuario("Test", "t@t.es", "pass1234", "H1", "Urgencias", cat.id)
    franjas = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=usuario.unidad.grupo_intercambio_id
    ).all()
    nombres = {f.nombre for f in franjas}
    assert nombres == {"Mañana", "Tarde", "Noche", "Diurno 12h", "Nocturno 12h"}


def test_registro_no_duplica_franjas_si_unidad_existe(db):
    from app.models import insertar_categorias_semilla
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()
    registrar_usuario("Ana", "ana@t.es", "pass1234", "H1", "Urgencias", cat.id)
    registrar_usuario("Pedro", "pedro@t.es", "pass1234", "H1", "Urgencias", cat.id)
    assert FranjaHoraria.query.filter_by(nombre="Mañana").count() == 1


def test_registrar_usuario_email_duplicado_lanza_error(db):
    from app.models import insertar_categorias_semilla
    insertar_categorias_semilla()
    cat = Categoria.query.filter_by(nombre="Enfermería").first()

    registrar_usuario("Ana", "ana@dup.es", "pass1234", "H1", "U1", cat.id)

    with pytest.raises(Exception):
        registrar_usuario("Ana Otra", "ana@dup.es", "pass5678", "H1", "U1", cat.id)
