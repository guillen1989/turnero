from datetime import date, time, datetime, timezone
from app.models import (
    Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria,
    Usuario, PublicacionCambio, TurnoCedido, TurnoAceptado,
    MatchCambio, MatchParticipacion, Notificacion,
)


def _setup(db, sufijo="a"):
    hospital = Hospital(nombre=f"Hospital {sufijo}")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    categoria = Categoria(nombre=f"Enfermería {sufijo}")
    unidad = Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo)
    franja = FranjaHoraria(nombre="Mañana", hora_inicio=time(7, 0), hora_fin=time(15, 0), grupo_intercambio=grupo)
    db.session.add_all([categoria, unidad, franja])
    db.session.commit()

    def crear_usuario(email):
        u = Usuario(nombre="Usuario Test", email=email, unidad=unidad, categoria=categoria)
        u.set_password("pass")
        db.session.add(u)
        db.session.commit()
        return u

    def crear_publicacion(usuario):
        pub = PublicacionCambio(usuario=usuario)
        cedido = TurnoCedido(fecha=date(2026, 6, 25), franja_horaria=franja)
        aceptado = TurnoAceptado(fecha=date(2026, 6, 26), franja_horaria=franja)
        pub.turnos_cedidos.append(cedido)
        pub.turnos_aceptados.append(aceptado)
        db.session.add(pub)
        db.session.commit()
        return pub, cedido

    return crear_usuario, crear_publicacion


def test_crear_match_directo(db):
    crear_usuario, crear_pub = _setup(db)

    ana = crear_usuario("ana@h.es")
    pedro = crear_usuario("pedro@h.es")
    pub_ana, cedido_ana = crear_pub(ana)
    pub_pedro, cedido_pedro = crear_pub(pedro)

    match = MatchCambio(tipo="directo_2", estado="propuesto")
    db.session.add(match)
    db.session.flush()

    match.participaciones.append(
        MatchParticipacion(publicacion=pub_ana, turno_cedido=cedido_ana)
    )
    match.participaciones.append(
        MatchParticipacion(publicacion=pub_pedro, turno_cedido=cedido_pedro)
    )
    db.session.commit()

    recuperado = db.session.get(MatchCambio, match.id)
    assert len(recuperado.participaciones) == 2
    assert recuperado.tipo == "directo_2"
    assert recuperado.estado == "propuesto"


def test_todas_confirmadas_falso_si_ninguna(db):
    crear_usuario, crear_pub = _setup(db, "b")

    ana = crear_usuario("ana2@h.es")
    pedro = crear_usuario("pedro2@h.es")
    pub_ana, cedido_ana = crear_pub(ana)
    pub_pedro, cedido_pedro = crear_pub(pedro)

    match = MatchCambio()
    match.participaciones.extend([
        MatchParticipacion(publicacion=pub_ana, turno_cedido=cedido_ana),
        MatchParticipacion(publicacion=pub_pedro, turno_cedido=cedido_pedro),
    ])
    db.session.add(match)
    db.session.commit()

    assert match.todas_confirmadas() is False


def test_todas_confirmadas_verdadero_si_ambas(db):
    crear_usuario, crear_pub = _setup(db, "c")

    ana = crear_usuario("ana3@h.es")
    pedro = crear_usuario("pedro3@h.es")
    pub_ana, cedido_ana = crear_pub(ana)
    pub_pedro, cedido_pedro = crear_pub(pedro)

    match = MatchCambio()
    p1 = MatchParticipacion(publicacion=pub_ana, turno_cedido=cedido_ana, confirmado=True)
    p2 = MatchParticipacion(publicacion=pub_pedro, turno_cedido=cedido_pedro, confirmado=True)
    match.participaciones.extend([p1, p2])
    db.session.add(match)
    db.session.commit()

    assert match.todas_confirmadas() is True


def test_crear_notificacion(db):
    crear_usuario, crear_pub = _setup(db, "d")

    ana = crear_usuario("ana4@h.es")
    pub_ana, cedido_ana = crear_pub(ana)

    match = MatchCambio()
    match.participaciones.append(MatchParticipacion(publicacion=pub_ana, turno_cedido=cedido_ana))
    db.session.add(match)
    db.session.commit()

    notif = Notificacion(usuario=ana, match=match, tipo="nuevo_match")
    db.session.add(notif)
    db.session.commit()

    assert notif.leida is False
    assert notif.tipo == "nuevo_match"
    assert notif.usuario_id == ana.id
