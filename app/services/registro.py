import secrets
from datetime import time

from flask import render_template
from flask_babel import gettext as _

from app.extensions import db
from app.models import (
    Pais, Provincia, Ciudad,
    Hospital, GrupoIntercambio, Unidad, Categoria, Usuario, FranjaHoraria,
    MatchCambio, MatchParticipacion, Notificacion, PublicacionCambio,
    BusquedaGuardada, SuscripcionPublicaciones,
    PasswordResetToken, EstadoDiaPlanilla, CompatibilidadPlanilla, TurnoPlanilla,
    PlanillaMes, SalienteDia, NotaDia, AjustePlanillaSupervisora,
    MapeoTrabajadorPlanilla, DocumentoCambio, ParticipanteDocumentoCambio,
    FirmaDocumentoCambio, UsuarioUnidad,
)
from app.services.email import enviar_email, url_absoluta
from app.services.password_reset import TOKEN_TTL_MINUTOS, generar_token_reset
from app.services.unidad_usuario import sincronizar_unidades

_OPCION_NUEVA = 0

_FRANJAS_DEFAULT = [
    ("Mañana",      time(8, 0),  time(15, 0)),
    ("Tarde",       time(15, 0), time(22, 0)),
    ("Noche",       time(22, 0), time(8, 0)),
    ("Diurno 12h",  time(8, 0),  time(20, 0)),
    ("Nocturno 12h",time(20, 0), time(8, 0)),
]

# Paleta general (se cicla cuando se crean franjas personalizadas)
_PALETA_COLORES = [
    "#3B82F6",  # blue-500     → Mañana
    "#F97316",  # orange-500   → Tarde
    "#14B8A6",  # teal-500     → Diurno 12h
    "#8B5CF6",  # violet-500
    "#EC4899",  # pink-500
    "#22C55E",  # green-500
    "#EAB308",  # yellow-500
    "#6366F1",  # indigo-500
    "#F43F5E",  # rose-500
    "#06B6D4",  # cyan-500
]
# Paleta oscura para "noche" / "nocturno"
_PALETA_NOCHE = ["#1E3A8A", "#1E40AF", "#1D4ED8"]


def asignar_color_franja(nombre: str, grupo_intercambio_id: int) -> str:
    """Devuelve el color hex a asignar a una franja nueva."""
    nombre_lower = nombre.lower()
    es_nocturna = "noche" in nombre_lower or "nocturno" in nombre_lower
    paleta = _PALETA_NOCHE if es_nocturna else _PALETA_COLORES
    usados = {
        f.color for f in
        FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo_intercambio_id).all()
        if f.color
    }
    for color in paleta:
        if color not in usados:
            return color
    # Todos usados: ciclar desde el principio
    n_usados = len(usados)
    return paleta[n_usados % len(paleta)]


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
                color=asignar_color_franja(nombre, grupo.id),
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

    PasswordResetToken.query.filter_by(usuario_id=usuario.id).delete()
    EstadoDiaPlanilla.query.filter_by(usuario_id=usuario.id).delete()
    CompatibilidadPlanilla.query.filter_by(usuario_id=usuario.id).delete()
    TurnoPlanilla.query.filter_by(usuario_id=usuario.id).delete()
    PlanillaMes.query.filter_by(usuario_id=usuario.id).delete()
    SalienteDia.query.filter_by(usuario_id=usuario.id).delete()
    NotaDia.query.filter_by(usuario_id=usuario.id).delete()
    AjustePlanillaSupervisora.query.filter(
        db.or_(
            AjustePlanillaSupervisora.usuario_id == usuario.id,
            AjustePlanillaSupervisora.realizado_por_id == usuario.id,
        )
    ).delete()
    MapeoTrabajadorPlanilla.query.filter_by(usuario_id=usuario.id).update({"usuario_id": None})

    # Documentos que el usuario creó (creado_por_id es NOT NULL): se borran
    # enteros, incluyendo participantes/firmas de OTROS usuarios en ellos.
    doc_ids_a_borrar = [
        d.id for d in DocumentoCambio.query.filter_by(creado_por_id=usuario.id).all()
    ]
    if doc_ids_a_borrar:
        DocumentoCambio.query.filter(
            DocumentoCambio.depende_de_id.in_(doc_ids_a_borrar)
        ).update({"depende_de_id": None}, synchronize_session=False)
        FirmaDocumentoCambio.query.filter(
            FirmaDocumentoCambio.documento_id.in_(doc_ids_a_borrar)
        ).delete(synchronize_session=False)
        ParticipanteDocumentoCambio.query.filter(
            ParticipanteDocumentoCambio.documento_id.in_(doc_ids_a_borrar)
        ).delete(synchronize_session=False)
        DocumentoCambio.query.filter(
            DocumentoCambio.id.in_(doc_ids_a_borrar)
        ).delete(synchronize_session=False)

    # Participación/firma del usuario en documentos ajenos (no se borra el documento)
    FirmaDocumentoCambio.query.filter_by(usuario_id=usuario.id).delete()
    ParticipanteDocumentoCambio.query.filter_by(usuario_id=usuario.id).delete()
    DocumentoCambio.query.filter_by(supervisora_id=usuario.id).update({"supervisora_id": None})
    DocumentoCambio.query.filter_by(anulado_por_id=usuario.id).update({"anulado_por_id": None})

    UsuarioUnidad.query.filter_by(usuario_id=usuario.id).delete()

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
    unidades_extra=None,
):
    """Crea el usuario con su unidad principal de siempre y, opcionalmente,
    se une a unidades adicionales en el mismo alta (`unidades_extra`: lista
    de dicts con `hospital_nombre`, `unidad_nombre`, `categoria_id`,
    `categoria_nueva_nombre`, `pais_nombre`, `provincia_nombre`,
    `ciudad_nombre`). Cada membresía conserva su propia categoría."""
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
    db.session.flush()

    membresias = {unidad.id: categoria.id}
    for extra in unidades_extra or []:
        extra_ciudad = _resolver_geografia(
            extra.get("pais_nombre"), extra.get("provincia_nombre"), extra.get("ciudad_nombre")
        )
        extra_hospital = encontrar_o_crear_hospital(extra["hospital_nombre"], extra_ciudad)
        extra_categoria = encontrar_o_crear_categoria(
            extra.get("categoria_id"), extra.get("categoria_nueva_nombre")
        )
        extra_unidad, _ = encontrar_o_crear_unidad(
            extra["unidad_nombre"], extra_hospital, extra_categoria
        )
        membresias[extra_unidad.id] = extra_categoria.id

    sincronizar_unidades(usuario, membresias)
    db.session.commit()
    usuario._es_nueva_unidad = is_new
    return usuario


def crear_usuario_con_invitacion(usuario):
    """Da de alta la contraseña de `usuario` con un valor aleatorio desconocido
    y le envía un email para que establezca la suya propia (mismo flujo que
    "recuperar contraseña", con texto adaptado a una invitación).

    Devuelve si el email se ha enviado correctamente, para que quien llame
    pueda avisar al admin si el envío falla en vez de dejarlo pasar en
    silencio (solo queda un warning en los logs)."""
    usuario.set_password(secrets.token_urlsafe(32))
    db.session.commit()

    token = generar_token_reset(usuario)
    enlace = url_absoluta("auth.restablecer_password", token=token)
    cuerpo_html = render_template(
        "email/invitacion_usuario.html",
        usuario=usuario, enlace=enlace, ttl_minutos=TOKEN_TTL_MINUTOS,
    )
    return enviar_email(usuario.email, _("Se ha creado tu cuenta en Turnero"), cuerpo_html)
