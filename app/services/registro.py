from datetime import time

from app.extensions import db
from app.models import (
    Pais, Provincia, Ciudad,
    Hospital, GrupoIntercambio, Unidad, Categoria, Usuario, FranjaHoraria,
    MatchCambio, MatchParticipacion, Notificacion, PublicacionCambio,
    BusquedaGuardada, SuscripcionPublicaciones,
)

_OPCION_NUEVA = 0

_FRANJAS_DEFAULT = [
    ("Mañana", time(8, 0), time(15, 0)),
    ("Tarde", time(15, 0), time(22, 0)),
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
    """Devuelve (unidad, is_new). is_new=True si la unidad acaba de crearse."""
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
        return unidad, True
    return unidad, False


def resolver_hospital(hospital_id, hospital_nuevo):
    if hospital_id == _OPCION_NUEVA or hospital_id is None:
        nombre = (hospital_nuevo or "").strip()
        return nombre if nombre else None
    h = db.session.get(Hospital, hospital_id)
    return h.nombre if h else None


def resolver_unidad(unidad_id, unidad_nuevo):
    if unidad_id == _OPCION_NUEVA or unidad_id is None:
        nombre = (unidad_nuevo or "").strip()
        return nombre if nombre else None
    u = db.session.get(Unidad, unidad_id)
    return u.nombre if u else None


def resolver_geo(pais_id, pais_nuevo, provincia_id, provincia_nueva, ciudad_id, ciudad_nueva):
    if pais_id and pais_id != _OPCION_NUEVA:
        pais = db.session.get(Pais, pais_id)
    else:
        nombre = (pais_nuevo or "").strip()
        pais = encontrar_o_crear_pais(nombre) if nombre else None
    if pais is None:
        return None

    if provincia_id and provincia_id != _OPCION_NUEVA:
        provincia = db.session.get(Provincia, provincia_id)
    else:
        nombre = (provincia_nueva or "").strip()
        provincia = encontrar_o_crear_provincia(nombre, pais) if nombre else None
    if provincia is None:
        return None

    if ciudad_id and ciudad_id != _OPCION_NUEVA:
        ciudad = db.session.get(Ciudad, ciudad_id)
    else:
        nombre = (ciudad_nueva or "").strip()
        ciudad = encontrar_o_crear_ciudad(nombre, provincia) if nombre else None
    return ciudad


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
    unidad, is_new = encontrar_o_crear_unidad(unidad_nombre, hospital, categoria)
    usuario.unidad = unidad
    usuario.categoria = categoria
    db.session.commit()
    usuario._es_nueva_unidad = is_new
    return usuario


def eliminar_usuario_admin(usuario):
    """
    Hard-delete a user and all their data (admin action).
    Order satisfies all FK constraints:
      BusquedaGuardada → SuscripcionPublicaciones → match notifications →
      matches → other-user notifications referencing user's pubs →
      user notifications → publications → feedback nullification → user row.
    """
    pub_ids = [p.id for p in usuario.publicaciones]

    BusquedaGuardada.query.filter_by(usuario_id=usuario.id).delete()
    SuscripcionPublicaciones.query.filter(
        db.or_(
            SuscripcionPublicaciones.suscriptor_id == usuario.id,
            SuscripcionPublicaciones.publicador_id == usuario.id,
        )
    ).delete()

    if pub_ids:
        matches = (
            MatchCambio.query
            .join(MatchParticipacion)
            .filter(MatchParticipacion.publicacion_id.in_(pub_ids))
            .all()
        )
        for match in matches:
            Notificacion.query.filter_by(match_id=match.id).delete()
            db.session.delete(match)
        db.session.flush()

        from app.models.notificacion import Notificacion as _N
        _N.query.filter(_N.publicacion_id.in_(pub_ids)).delete(synchronize_session=False)

    Notificacion.query.filter_by(usuario_id=usuario.id).delete()

    for pub in list(usuario.publicaciones):
        db.session.delete(pub)
    db.session.flush()

    # Feedback.usuario_id is nullable — nullify rather than delete
    db.session.execute(
        db.text("UPDATE feedback SET usuario_id = NULL WHERE usuario_id = :uid"),
        {"uid": usuario.id},
    )

    db.session.delete(usuario)
    db.session.commit()


def eliminar_cuenta(usuario):
    """
    Anonimiza la cuenta del usuario satisfaciendo el derecho al olvido:
    - Rechaza matches activos (notifica a contrapartes)
    - Cancela publicaciones activas
    - Borra búsquedas guardadas y suscripciones
    - Sobreescribe datos personales con marcadores anónimos
    La fila del usuario permanece en DB para preservar integridad referencial
    del historial de matches ya completados.
    """
    from app.services.matches import rechazar_match
    from app.services.publicaciones import cancelar_publicacion

    matches_activos = (
        MatchCambio.query
        .join(MatchParticipacion)
        .join(PublicacionCambio)
        .filter(
            PublicacionCambio.usuario_id == usuario.id,
            MatchCambio.estado.in_(["propuesto", "confirmado_parcial"]),
        )
        .distinct()
        .all()
    )
    for match in matches_activos:
        rechazar_match(match, usuario.id)

    pubs_activas = (
        PublicacionCambio.query
        .filter_by(usuario_id=usuario.id)
        .filter(PublicacionCambio.estado.in_(["abierta", "parcialmente_resuelta"]))
        .all()
    )
    for pub in pubs_activas:
        cancelar_publicacion(pub)

    BusquedaGuardada.query.filter_by(usuario_id=usuario.id).delete()
    SuscripcionPublicaciones.query.filter(
        db.or_(
            SuscripcionPublicaciones.suscriptor_id == usuario.id,
            SuscripcionPublicaciones.publicador_id == usuario.id,
        )
    ).delete()

    usuario.nombre = "Usuario eliminado"
    usuario.email = f"eliminado_{usuario.id}@eliminado.invalid"
    usuario.password_hash = "CUENTA_ELIMINADA"
    usuario.push_subscription = None
    usuario.push_activo = False
    db.session.commit()


def registrar_usuario(
    nombre, email, password, hospital_nombre, unidad_nombre, categoria_id,
    categoria_nueva_nombre=None,
    pais_nombre=None, provincia_nombre=None, ciudad_nombre=None,
):
    ciudad = _resolver_geografia(pais_nombre, provincia_nombre, ciudad_nombre)
    hospital = encontrar_o_crear_hospital(hospital_nombre, ciudad)
    categoria = encontrar_o_crear_categoria(categoria_id, categoria_nueva_nombre)
    unidad, is_new = encontrar_o_crear_unidad(unidad_nombre, hospital, categoria)

    usuario = Usuario(
        nombre=nombre.strip(),
        email=email.strip().lower(),
        unidad=unidad,
        categoria=categoria,
    )
    usuario.set_password(password)
    db.session.add(usuario)
    db.session.commit()
    usuario._es_nueva_unidad = is_new
    return usuario
