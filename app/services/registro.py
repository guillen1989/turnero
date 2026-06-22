from datetime import time

from app.extensions import db
from app.models import (
    Pais, Provincia, Ciudad,
    Hospital, GrupoIntercambio, Unidad, Categoria, Usuario, FranjaHoraria,
)

_FRANJAS_DEFAULT = [
    ("Mañana", time(7, 0), time(15, 0)),
    ("Tarde", time(15, 0), time(23, 0)),
    ("Noche", time(22, 0), time(8, 0)),
    ("Diurno 12h", time(8, 0), time(20, 0)),
    ("Nocturno 12h", time(20, 0), time(8, 0)),
]


def crear_franjas_default(grupo):
    existentes = {
        f.nombre for f in FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo.id).all()
    }
    for nombre, inicio, fin in _FRANJAS_DEFAULT:
        if nombre not in existentes:
            db.session.add(FranjaHoraria(
                nombre=nombre,
                hora_inicio=inicio,
                hora_fin=fin,
                grupo_intercambio=grupo,
            ))


def _normalizar(texto):
    return texto.strip().lower()


def encontrar_o_crear_pais(nombre):
    nombre_norm = _normalizar(nombre)
    pais = Pais.query.filter(db.func.lower(Pais.nombre) == nombre_norm).first()
    if not pais:
        pais = Pais(nombre=nombre.strip())
        db.session.add(pais)
        db.session.flush()
    return pais


def encontrar_o_crear_provincia(nombre, pais):
    nombre_norm = _normalizar(nombre)
    provincia = Provincia.query.filter(
        Provincia.pais_id == pais.id,
        db.func.lower(Provincia.nombre) == nombre_norm,
    ).first()
    if not provincia:
        provincia = Provincia(nombre=nombre.strip(), pais=pais)
        db.session.add(provincia)
        db.session.flush()
    return provincia


def encontrar_o_crear_ciudad(nombre, provincia):
    nombre_norm = _normalizar(nombre)
    ciudad = Ciudad.query.filter(
        Ciudad.provincia_id == provincia.id,
        db.func.lower(Ciudad.nombre) == nombre_norm,
    ).first()
    if not ciudad:
        ciudad = Ciudad(nombre=nombre.strip(), provincia=provincia)
        db.session.add(ciudad)
        db.session.flush()
    return ciudad


def encontrar_o_crear_hospital(nombre, ciudad=None):
    nombre_norm = _normalizar(nombre)
    q = Hospital.query.filter(db.func.lower(Hospital.nombre) == nombre_norm)
    if ciudad is not None:
        q = q.filter(Hospital.ciudad_id == ciudad.id)
    hospital = q.first()
    if not hospital:
        hospital = Hospital(nombre=nombre.strip(), ciudad=ciudad)
        db.session.add(hospital)
        db.session.flush()
    return hospital


def encontrar_o_crear_unidad(nombre, hospital, categoria=None):
    nombre_norm = _normalizar(nombre)
    q = Unidad.query.filter(
        Unidad.hospital_id == hospital.id,
        db.func.lower(Unidad.nombre) == nombre_norm,
    )
    if categoria is not None:
        q = q.filter(Unidad.categoria_id == categoria.id)
    unidad = q.first()
    if not unidad:
        grupo = GrupoIntercambio()
        db.session.add(grupo)
        db.session.flush()
        crear_franjas_default(grupo)
        unidad = Unidad(
            nombre=nombre.strip(),
            hospital=hospital,
            grupo_intercambio=grupo,
            categoria=categoria,
        )
        db.session.add(unidad)
        db.session.flush()
    return unidad


def encontrar_o_crear_categoria(categoria_id, nombre_nueva):
    if categoria_id:
        return db.session.get(Categoria, categoria_id)

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


def _resolver_geografia(pais_nombre, provincia_nombre, ciudad_nombre):
    """Devuelve un objeto Ciudad o None si falta algún nivel de la jerarquía."""
    if not pais_nombre:
        return None
    pais = encontrar_o_crear_pais(pais_nombre)
    if not provincia_nombre:
        return None
    provincia = encontrar_o_crear_provincia(provincia_nombre, pais)
    if not ciudad_nombre:
        return None
    return encontrar_o_crear_ciudad(ciudad_nombre, provincia)


def actualizar_perfil(
    usuario, hospital_nombre, unidad_nombre, categoria_id, categoria_nueva_nombre=None,
    pais_nombre=None, provincia_nombre=None, ciudad_nombre=None,
):
    ciudad = _resolver_geografia(pais_nombre, provincia_nombre, ciudad_nombre)
    hospital = encontrar_o_crear_hospital(hospital_nombre, ciudad)
    categoria = encontrar_o_crear_categoria(categoria_id, categoria_nueva_nombre)
    unidad = encontrar_o_crear_unidad(unidad_nombre, hospital, categoria)
    usuario.unidad = unidad
    usuario.categoria = categoria
    db.session.commit()
    return usuario


def registrar_usuario(
    nombre, email, password, hospital_nombre, unidad_nombre, categoria_id,
    categoria_nueva_nombre=None,
    pais_nombre=None, provincia_nombre=None, ciudad_nombre=None,
):
    ciudad = _resolver_geografia(pais_nombre, provincia_nombre, ciudad_nombre)
    hospital = encontrar_o_crear_hospital(hospital_nombre, ciudad)
    categoria = encontrar_o_crear_categoria(categoria_id, categoria_nueva_nombre)
    unidad = encontrar_o_crear_unidad(unidad_nombre, hospital, categoria)

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
