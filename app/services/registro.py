from datetime import time

from app.extensions import db
from app.models import Hospital, GrupoIntercambio, Unidad, Categoria, Usuario, FranjaHoraria

_FRANJAS_DEFAULT = [
    ("Mañana", time(7, 0), time(15, 0)),
    ("Tarde", time(15, 0), time(23, 0)),
    ("Noche", time(23, 0), time(7, 0)),
]


def crear_franjas_default(grupo):
    for nombre, inicio, fin in _FRANJAS_DEFAULT:
        db.session.add(FranjaHoraria(
            nombre=nombre,
            hora_inicio=inicio,
            hora_fin=fin,
            grupo_intercambio=grupo,
        ))


def _normalizar(texto):
    return texto.strip().lower()


def encontrar_o_crear_hospital(nombre):
    nombre_norm = _normalizar(nombre)
    hospital = Hospital.query.filter(
        db.func.lower(Hospital.nombre) == nombre_norm
    ).first()
    if not hospital:
        hospital = Hospital(nombre=nombre.strip())
        db.session.add(hospital)
        db.session.flush()
    return hospital


def encontrar_o_crear_unidad(nombre, hospital):
    nombre_norm = _normalizar(nombre)
    unidad = Unidad.query.filter(
        Unidad.hospital_id == hospital.id,
        db.func.lower(Unidad.nombre) == nombre_norm,
    ).first()
    if not unidad:
        grupo = GrupoIntercambio()
        db.session.add(grupo)
        db.session.flush()
        crear_franjas_default(grupo)
        unidad = Unidad(nombre=nombre.strip(), hospital=hospital, grupo_intercambio=grupo)
        db.session.add(unidad)
        db.session.flush()
    return unidad


def encontrar_o_crear_categoria(categoria_id, nombre_nueva):
    if categoria_id:
        return db.session.get(Categoria, categoria_id)

    # Comprobación ligera de duplicado: ignora mayúsculas y espacios
    nombre_norm = _normalizar(nombre_nueva).replace(" ", "")
    existente = Categoria.query.filter(
        db.func.lower(db.func.replace(Categoria.nombre, " ", "")) == nombre_norm
    ).first()
    if existente:
        return existente

    categoria = Categoria(nombre=nombre_nueva.strip())
    db.session.add(categoria)
    db.session.flush()
    return categoria


def actualizar_perfil(usuario, hospital_nombre, unidad_nombre, categoria_id, categoria_nueva_nombre=None):
    hospital = encontrar_o_crear_hospital(hospital_nombre)
    unidad = encontrar_o_crear_unidad(unidad_nombre, hospital)
    categoria = encontrar_o_crear_categoria(categoria_id, categoria_nueva_nombre)
    usuario.unidad = unidad
    usuario.categoria = categoria
    db.session.commit()
    return usuario


def registrar_usuario(nombre, email, password, hospital_nombre, unidad_nombre, categoria_id, categoria_nueva_nombre=None):
    hospital = encontrar_o_crear_hospital(hospital_nombre)
    unidad = encontrar_o_crear_unidad(unidad_nombre, hospital)
    categoria = encontrar_o_crear_categoria(categoria_id, categoria_nueva_nombre)

    usuario = Usuario(
        nombre=nombre.strip(),
        email=email.strip().lower(),
        unidad=unidad,
        categoria=categoria,
    )
    usuario.set_password(password)
    db.session.add(usuario)
    db.session.commit()
    return usuario
