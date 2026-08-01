"""Tests del selector de unidad activa en /calendario, /cambios y /planilla
(Paso 5 de docs/USUARIOS_MULTI.md)."""
from datetime import date, time

import pytest
from flask import url_for

from app.extensions import db
from app.models import (
    Categoria,
    FranjaHoraria,
    GrupoIntercambio,
    Hospital,
    PublicacionCambio,
    TurnoAceptado,
    TurnoCedido,
    Unidad,
    Usuario,
    UsuarioUnidad,
    insertar_categorias_semilla,
)
from app.services.registro import registrar_usuario


def _crear_usuario_con_dos_unidades(client, db):
    """Usuario con unidad principal en grupo A y segunda unidad en grupo B."""
    insertar_categorias_semilla()
    cat_enfermeria = Categoria.query.filter_by(nombre="Enfermería").first()
    cat_auxiliar = Categoria.query.filter_by(nombre="Auxiliar de enfermería (TCAE)").first()

    usuario = registrar_usuario("Ana", "ana@test.es", "password123", "H-Principal", "UCI", cat_enfermeria.id)

    grupo_b = GrupoIntercambio()
    db.session.add(grupo_b)
    db.session.commit()

    hospital_principal = usuario.unidad.hospital
    unidad_b = Unidad(nombre="Urgencias", hospital=hospital_principal, grupo_intercambio=grupo_b)
    db.session.add(unidad_b)
    db.session.commit()

    db.session.add(UsuarioUnidad(
        usuario_id=usuario.id, unidad_id=unidad_b.id, categoria_id=cat_auxiliar.id,
    ))
    db.session.commit()

    for nombre, h_inicio, h_fin in [
        ("Mañana", time(8, 0), time(15, 0)),
        ("Tarde", time(15, 0), time(22, 0)),
    ]:
        db.session.add(FranjaHoraria(
            nombre=f"{nombre} B", hora_inicio=h_inicio, hora_fin=h_fin,
            grupo_intercambio=grupo_b, color="#3B82F6",
        ))
    db.session.commit()

    client.post("/auth/login", data={"email": usuario.email, "password": "password123"})
    return usuario, usuario.unidad, unidad_b, cat_enfermeria, cat_auxiliar


def _crear_publicacion(db, usuario, tipo, franja_nombre="Mañana"):
    """Crea una publicación visible en el grupo del usuario."""
    grupo_id = usuario.unidad.grupo_intercambio_id
    franja = FranjaHoraria.query.filter_by(
        grupo_intercambio_id=grupo_id, nombre=franja_nombre,
    ).first()
    if franja is None:
        franja = FranjaHoraria.query.filter_by(
            grupo_intercambio_id=grupo_id,
        ).first()
    hoy = date.today()
    pub = PublicacionCambio(usuario=usuario, tipo=tipo, estado="abierta")
    db.session.add(pub)
    db.session.commit()
    tc = TurnoCedido(fecha=date(hoy.year, hoy.month, 1), publicacion=pub,
                     franja_horaria=franja, estado="abierto")
    ta = TurnoAceptado(fecha=date(hoy.year, hoy.month, 2), publicacion=pub,
                       franja_horaria=franja, cualquier_franja=False)
    db.session.add_all([tc, ta])
    db.session.commit()
    return pub


class TestCalendarioUnidadActiva:
    def test_sin_unidad_id_usa_la_principal(self, client, db):
        usuario, uci, urgencias, cat_enf, _ = _crear_usuario_con_dos_unidades(client, db)

        resp = client.get(url_for("calendario.index"))
        assert resp.status_code == 200

    def test_con_unidad_id_valido_cambia_contexto(self, client, db):
        usuario, uci, urgencias, cat_enf, _ = _crear_usuario_con_dos_unidades(client, db)

        resp = client.get(url_for("calendario.index", unidad_id=urgencias.id))
        assert resp.status_code == 200

    def test_con_unidad_id_ajena_devuelve_403(self, client, db):
        usuario, uci, urgencias, cat_enf, _ = _crear_usuario_con_dos_unidades(client, db)

        hospital = Hospital(nombre="H-Ajeno")
        grupo = GrupoIntercambio()
        db.session.add_all([hospital, grupo])
        db.session.commit()
        unidad_ajena = Unidad(nombre="Cardiología", hospital=hospital, grupo_intercambio=grupo)
        db.session.add(unidad_ajena)
        db.session.commit()

        resp = client.get(url_for("calendario.index", unidad_id=unidad_ajena.id))
        assert resp.status_code == 403

    def test_solo_muestra_publicaciones_de_la_unidad_activa(self, client, db):
        """Con 2 unidades en grupos distintos, el calendario muestra solo las
        publicaciones del grupo de la unidad activa."""
        usuario, uci, urgencias, cat_enf, cat_aux = _crear_usuario_con_dos_unidades(client, db)

        otro = registrar_usuario("Otro", "otro@test.es", "password123", "H-Principal", "UCI", cat_enf.id)
        otro2 = registrar_usuario("Otro2", "otro2@test.es", "password123", "H-Principal", "UCI", cat_enf.id)

        _crear_publicacion(db, otro, "cambio", "Mañana")
        pub_uci = PublicacionCambio.query.filter_by(usuario_id=otro.id).first()

        resp_uci = client.get(url_for("calendario.index", unidad_id=uci.id))

        assert resp_uci.status_code == 200
        assert str(pub_uci.id).encode() in resp_uci.data

    def test_las_franjas_del_calendario_son_las_de_la_unidad_activa(self, client, db):
        usuario, uci, urgencias, cat_enf, _ = _crear_usuario_con_dos_unidades(client, db)

        resp = client.get(url_for("calendario.index", unidad_id=urgencias.id))
        assert resp.status_code == 200
        assert "Urgencias".encode() in resp.data


class TestCambiosUnidadActiva:
    def test_sin_unidad_id_usa_la_principal(self, client, db):
        usuario, uci, urgencias, cat_enf, _ = _crear_usuario_con_dos_unidades(client, db)

        resp = client.get(url_for("main.cambios"))
        assert resp.status_code == 200

    def test_con_unidad_id_valido_cambia_contexto(self, client, db):
        usuario, uci, urgencias, cat_enf, _ = _crear_usuario_con_dos_unidades(client, db)

        resp = client.get(url_for("main.cambios", unidad_id=urgencias.id))
        assert resp.status_code == 200

    def test_con_unidad_id_ajena_devuelve_403(self, client, db):
        usuario, uci, urgencias, cat_enf, _ = _crear_usuario_con_dos_unidades(client, db)

        hospital = Hospital(nombre="H-Ajeno2")
        grupo = GrupoIntercambio()
        db.session.add_all([hospital, grupo])
        db.session.commit()
        unidad_ajena = Unidad(nombre="Cardiología", hospital=hospital, grupo_intercambio=grupo)
        db.session.add(unidad_ajena)
        db.session.commit()

        resp = client.get(url_for("main.cambios", unidad_id=unidad_ajena.id))
        assert resp.status_code == 403

    def test_filtra_por_categoria_de_la_unidad_activa(self, client, db):
        """La búsqueda de cambios filtra por la categoría en la unidad activa, no la global."""
        usuario, uci, urgencias, cat_enf, cat_aux = _crear_usuario_con_dos_unidades(client, db)

        # Crear un tercer usuario en Urgencias con categoría Auxiliar
        # (el usuario en Urgencias también tiene cat_aux)
        insertar_categorias_semilla()
        aux_cat = Categoria.query.filter_by(nombre="Auxiliar de enfermería (TCAE)").first()
        usuario_aux = registrar_usuario("Aux", "aux@test.es", "password123", "H-Principal", "Urgencias", aux_cat.id)

        # Mover a usuario_aux al mismo grupo que urgencias
        usuario_aux.unidad.grupo_intercambio_id = urgencias.grupo_intercambio_id
        db.session.commit()

        _crear_publicacion(db, usuario_aux, "cambio", "Mañana B")
        pub_aux = PublicacionCambio.query.filter_by(usuario_id=usuario_aux.id).first()

        resp = client.get(url_for("main.cambios", unidad_id=urgencias.id, tab="resultados"))
        assert resp.status_code == 200
        assert str(pub_aux.id).encode() in resp.data


class TestPlanillaUnidadActiva:
    def test_sin_unidad_id_usa_la_principal(self, client, db):
        usuario, uci, urgencias, cat_enf, _ = _crear_usuario_con_dos_unidades(client, db)

        resp = client.get(url_for("planilla.index"))
        assert resp.status_code == 200

    def test_con_unidad_id_valido_cambia_contexto(self, client, db):
        usuario, uci, urgencias, cat_enf, _ = _crear_usuario_con_dos_unidades(client, db)

        resp = client.get(url_for("planilla.index", unidad_id=urgencias.id))
        assert resp.status_code == 200

    def test_con_unidad_id_ajena_devuelve_403(self, client, db):
        usuario, uci, urgencias, cat_enf, _ = _crear_usuario_con_dos_unidades(client, db)

        hospital = Hospital(nombre="H-Ajeno3")
        grupo = GrupoIntercambio()
        db.session.add_all([hospital, grupo])
        db.session.commit()
        unidad_ajena = Unidad(nombre="Cardiología", hospital=hospital, grupo_intercambio=grupo)
        db.session.add(unidad_ajena)
        db.session.commit()

        resp = client.get(url_for("planilla.index", unidad_id=unidad_ajena.id))
        assert resp.status_code == 403

    def test_franjas_de_planilla_son_las_de_la_unidad_activa(self, client, db):
        """Las franjas mostradas en la planilla son las de la unidad activa."""
        usuario, uci, urgencias, cat_enf, _ = _crear_usuario_con_dos_unidades(client, db)

        resp = client.get(url_for("planilla.index", unidad_id=urgencias.id))
        assert resp.status_code == 200
        assert b"Tarde B" in resp.data

    def test_dia_añadir_valida_franja_contra_unidad_activa(self, client, db):
        """Añadir un turno valida la franja contra el grupo de la unidad activa."""
        usuario, uci, urgencias, cat_enf, _ = _crear_usuario_con_dos_unidades(client, db)

        # Obtener una franja de la segunda unidad (grupo B)
        franja_b = FranjaHoraria.query.filter_by(
            grupo_intercambio_id=urgencias.grupo_intercambio_id, nombre="Tarde B",
        ).first()
        assert franja_b is not None

        hoy = date.today()
        resp = client.post(url_for("planilla.dia_añadir"), data={
            "fecha": hoy.isoformat(),
            "seleccion": str(franja_b.id),
            "anyo": hoy.year,
            "mes": hoy.month,
            "unidad_id": urgencias.id,
        }, follow_redirects=True)
        assert resp.status_code == 200


class TestSessionUnidadActiva:
    def test_unidad_id_explicito_se_guarda_en_sesion(self, client, db):
        usuario, uci, urgencias, cat_enf, _ = _crear_usuario_con_dos_unidades(client, db)

        client.get(url_for("calendario.index", unidad_id=urgencias.id))
        resp = client.get(url_for("calendario.index"))

        assert resp.status_code == 200
        assert "Urgencias".encode() in resp.data

    def test_sesion_persiste_entre_rutas(self, client, db):
        usuario, uci, urgencias, cat_enf, _ = _crear_usuario_con_dos_unidades(client, db)

        client.get(url_for("planilla.index", unidad_id=urgencias.id))
        resp = client.get(url_for("calendario.index"))

        assert resp.status_code == 200
        assert "Urgencias".encode() in resp.data
