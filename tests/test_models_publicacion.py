from datetime import date, time
from app.models import (
    Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria,
    Usuario, PublicacionCambio, TurnoCedido, TurnoAceptado,
)


def _crear_usuario(db, email="ana@hospital.es"):
    hospital = Hospital(nombre=f"Hospital {email}")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    unidad = Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo)
    categoria = Categoria(nombre=f"Enfermería {email}")
    franja = FranjaHoraria(nombre="Mañana", hora_inicio=time(7, 0), hora_fin=time(15, 0), grupo_intercambio=grupo)
    db.session.add_all([unidad, categoria, franja])
    db.session.commit()

    usuario = Usuario(nombre="Ana García", email=email, unidad=unidad, categoria=categoria)
    usuario.set_password("pass")
    db.session.add(usuario)
    db.session.commit()

    return usuario, franja


def test_crear_publicacion_simple(db):
    usuario, franja = _crear_usuario(db)

    pub = PublicacionCambio(usuario=usuario)
    cedido = TurnoCedido(fecha=date(2026, 6, 25), franja_horaria=franja, publicacion=pub)
    aceptado = TurnoAceptado(fecha=date(2026, 6, 26), franja_horaria=franja, publicacion=pub)
    db.session.add(pub)
    db.session.commit()

    recuperada = db.session.get(PublicacionCambio, pub.id)
    assert recuperada.estado == "abierta"
    assert len(recuperada.turnos_cedidos) == 1
    assert len(recuperada.turnos_aceptados) == 1
    assert recuperada.turnos_cedidos[0].fecha == date(2026, 6, 25)


def test_publicacion_multi_turno(db):
    """Una publicación puede ceder varios turnos (resolución parcial)."""
    usuario, franja = _crear_usuario(db, "multi@hospital.es")

    pub = PublicacionCambio(usuario=usuario)
    db.session.add(pub)

    pub.turnos_cedidos.append(TurnoCedido(fecha=date(2026, 6, 25), franja_horaria=franja))
    pub.turnos_cedidos.append(TurnoCedido(fecha=date(2026, 6, 27), franja_horaria=franja))
    pub.turnos_aceptados.append(TurnoAceptado(fecha=date(2026, 6, 26), franja_horaria=franja))
    db.session.commit()

    assert len(pub.turnos_cedidos) == 2
    assert all(t.estado == "abierto" for t in pub.turnos_cedidos)


def test_estado_parcialmente_resuelta(db):
    """Cuando un turno cedido se resuelve pero queda otro abierto, el estado es parcialmente_resuelta."""
    usuario, franja = _crear_usuario(db, "parcial@hospital.es")

    pub = PublicacionCambio(usuario=usuario)
    t1 = TurnoCedido(fecha=date(2026, 6, 25), franja_horaria=franja)
    t2 = TurnoCedido(fecha=date(2026, 6, 27), franja_horaria=franja)
    pub.turnos_cedidos.extend([t1, t2])
    db.session.add(pub)
    db.session.commit()

    t1.estado = "resuelto"
    pub.actualizar_estado()
    db.session.commit()

    assert pub.estado == "parcialmente_resuelta"


def test_estado_confirmada_cuando_todos_resueltos(db):
    usuario, franja = _crear_usuario(db, "total@hospital.es")

    pub = PublicacionCambio(usuario=usuario)
    t1 = TurnoCedido(fecha=date(2026, 6, 25), franja_horaria=franja)
    pub.turnos_cedidos.append(t1)
    db.session.add(pub)
    db.session.commit()

    t1.estado = "resuelto"
    pub.actualizar_estado()
    db.session.commit()

    assert pub.estado == "confirmada"


def test_publicacion_activa_solo_en_estados_abiertos(db):
    usuario, franja = _crear_usuario(db, "activa@hospital.es")

    pub = PublicacionCambio(usuario=usuario, estado="abierta")
    db.session.add(pub)
    db.session.commit()

    assert pub.esta_activa() is True

    pub.estado = "confirmada"
    assert pub.esta_activa() is False

    pub.estado = "parcialmente_resuelta"
    assert pub.esta_activa() is True

    pub.estado = "cancelada"
    assert pub.esta_activa() is False
