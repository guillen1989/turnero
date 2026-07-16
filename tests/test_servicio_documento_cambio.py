from datetime import date, time
from app.models import Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria, Usuario
from app.services.documento_cambio import (
    crear_documento_cambio, firmar_documento, generar_notas_ilog, generar_pdf_documento,
)

_FIRMA_PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAADklE"
    "QVR4nGNgGAWDEwAAAZoAAR2CVqgAAAAASUVORK5CYII="
)


def _setup(db, sufijo="a"):
    hospital = Hospital(nombre=f"Hospital {sufijo}")
    grupo = GrupoIntercambio()
    db.session.add_all([hospital, grupo])
    db.session.commit()

    categoria = Categoria(nombre=f"Enfermería {sufijo}")
    unidad = Unidad(nombre="Urgencias", hospital=hospital, grupo_intercambio=grupo)
    manyana = FranjaHoraria(nombre="Mañana", hora_inicio=time(7, 0), hora_fin=time(15, 0), grupo_intercambio=grupo)
    tarde = FranjaHoraria(nombre="Tarde", hora_inicio=time(15, 0), hora_fin=time(22, 0), grupo_intercambio=grupo)
    db.session.add_all([categoria, unidad, manyana, tarde])
    db.session.commit()

    def crear_usuario(nombre, email):
        u = Usuario(nombre=nombre, email=email, unidad=unidad, categoria=categoria)
        u.set_password("pass")
        db.session.add(u)
        db.session.commit()
        return u

    return crear_usuario, manyana, tarde


def test_crear_documento_cambio_genera_dos_participantes_espejo(db):
    crear_usuario, manyana, tarde = _setup(db, "a")
    claudia = crear_usuario("Claudia Pérez", "claudia@h.es")
    juan = crear_usuario("Juan Rodríguez", "juana@h.es")

    documento = crear_documento_cambio(
        creado_por=claudia,
        companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja_id=manyana.id,
    )

    assert documento.estado == "borrador"
    assert len(documento.participantes) == 2

    p_claudia = next(p for p in documento.participantes if p.usuario_id == claudia.id)
    p_juan = next(p for p in documento.participantes if p.usuario_id == juan.id)

    assert p_claudia.turno_cede_fecha == date(2026, 7, 7)
    assert p_claudia.turno_recibe_fecha == date(2026, 7, 28)
    # El compañero es el espejo exacto: cede lo que Claudia recibe y viceversa.
    assert p_juan.turno_cede_fecha == date(2026, 7, 28)
    assert p_juan.turno_recibe_fecha == date(2026, 7, 7)
    assert p_juan.turno_cede_franja_id == manyana.id


def test_firmar_documento_primera_firma_deja_pendiente(db):
    crear_usuario, manyana, tarde = _setup(db, "b")
    claudia = crear_usuario("Claudia Pérez", "claudiab@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanb@h.es")
    documento = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja_id=manyana.id,
    )

    firmar_documento(documento, claudia, "data:image/png;base64,firmaclaudia")

    assert documento.estado == "pendiente_firmas"
    assert documento.todos_han_firmado() is False


def test_firmar_documento_segunda_firma_completa(db):
    crear_usuario, manyana, tarde = _setup(db, "c")
    claudia = crear_usuario("Claudia Pérez", "claudiac@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanc@h.es")
    documento = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja_id=manyana.id,
    )

    firmar_documento(documento, claudia, "data:image/png;base64,firmaclaudia")
    firmar_documento(documento, juan, "data:image/png;base64,firmajuan")

    assert documento.estado == "completo"
    assert documento.todos_han_firmado() is True
    assert len(documento.firmas) == 2


def test_firmar_documento_guarda_mismo_hash_para_contenido_identico(db):
    crear_usuario, manyana, tarde = _setup(db, "d")
    claudia = crear_usuario("Claudia Pérez", "claudiad@h.es")
    juan = crear_usuario("Juan Rodríguez", "juand@h.es")
    documento = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja_id=manyana.id,
    )

    f1 = firmar_documento(documento, claudia, "x")
    f2 = firmar_documento(documento, juan, "y")

    assert len(f1.hash_documento) == 64
    assert f1.hash_documento == f2.hash_documento


def test_generar_notas_ilog_contenido_para_ejemplo_del_usuario(db):
    crear_usuario, manyana, tarde = _setup(db, "e")
    claudia = crear_usuario("Claudia Pérez", "claudiae@h.es")
    juan = crear_usuario("Juan Rodríguez", "juane@h.es")
    documento = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja_id=manyana.id,
    )

    notas = generar_notas_ilog(documento)

    assert len(notas) == 4

    nota_claudia_7 = next(
        n for n in notas if n["usuario"].id == claudia.id and n["fecha"] == date(2026, 7, 7)
    )
    assert nota_claudia_7["texto"] == (
        "Libra el turno de mañana a cambio de trabajarle a Juan Rodríguez "
        "el turno de mañana del 28 de julio."
    )

    nota_juan_7 = next(
        n for n in notas if n["usuario"].id == juan.id and n["fecha"] == date(2026, 7, 7)
    )
    assert nota_juan_7["texto"] == (
        "Trabaja el turno de mañana a Claudia Pérez a cambio de que "
        "Claudia Pérez le trabaje el turno de mañana del 28 de julio."
    )

    nota_juan_28 = next(
        n for n in notas if n["usuario"].id == juan.id and n["fecha"] == date(2026, 7, 28)
    )
    assert nota_juan_28["texto"] == (
        "Libra el turno de mañana a cambio de trabajarle a Claudia Pérez "
        "el turno de mañana del 7 de julio."
    )

    nota_claudia_28 = next(
        n for n in notas if n["usuario"].id == claudia.id and n["fecha"] == date(2026, 7, 28)
    )
    assert nota_claudia_28["texto"] == (
        "Trabaja el turno de mañana a Juan Rodríguez a cambio de que "
        "Juan Rodríguez le trabaje el turno de mañana del 7 de julio."
    )


def test_generar_pdf_documento_completo(db):
    crear_usuario, manyana, tarde = _setup(db, "f")
    claudia = crear_usuario("Claudia Pérez", "claudiaf@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanf@h.es")
    documento = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja_id=manyana.id,
    )
    firmar_documento(documento, claudia, _FIRMA_PNG)
    firmar_documento(documento, juan, _FIRMA_PNG)

    pdf_bytes = generar_pdf_documento(documento)

    assert pdf_bytes[:5] == b"%PDF-"
    assert len(pdf_bytes) > 1000


def test_crear_documento_cambio_calcula_factibilidad_no_verificado_por_defecto(db):
    crear_usuario, manyana, tarde = _setup(db, "g")
    claudia = crear_usuario("Claudia Pérez", "claudiag2@h.es")
    juan = crear_usuario("Juan Rodríguez", "juang2@h.es")

    documento = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja_id=manyana.id,
    )

    # Sin planillas publicadas de por medio, no se puede verificar.
    assert documento.factibilidad_estado == "no_verificado"


def test_firmar_documento_recalcula_factibilidad_al_completarse(db):
    from app.models import TurnoPlanilla, PlanillaMes

    crear_usuario, manyana, tarde = _setup(db, "h")
    claudia = crear_usuario("Claudia Pérez", "claudiah@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanh@h.es")

    documento = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja_id=manyana.id,
    )
    assert documento.factibilidad_estado == "no_verificado"

    # Entre la creación y la firma, ambos publican su planilla y cuadra todo.
    db.session.add(PlanillaMes(usuario=claudia, anyo=2026, mes=7, publicada=True))
    db.session.add(PlanillaMes(usuario=juan, anyo=2026, mes=7, publicada=True))
    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 7), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 28), franja_horaria=manyana))
    db.session.commit()

    firmar_documento(documento, claudia, "data:image/png;base64,AAA")
    # Tras la primera firma (documento aún no completo) no hace falta que ya
    # esté recalculado, pero no debe romper nada si lo está.
    firmar_documento(documento, juan, "data:image/png;base64,BBB")

    assert documento.estado == "completo"
    assert documento.factibilidad_estado == "factible"


def test_crear_documento_cambio_notifica_al_companero(db):
    from app.models import Notificacion

    crear_usuario, manyana, tarde = _setup(db, "i")
    claudia = crear_usuario("Claudia Pérez", "claudiai@h.es")
    juan = crear_usuario("Juan Rodríguez", "juani@h.es")

    documento = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja_id=manyana.id,
    )

    notifs_juan = Notificacion.query.filter_by(usuario_id=juan.id, documento_cambio_id=documento.id).all()
    assert len(notifs_juan) == 1
    assert notifs_juan[0].tipo == "documento_cambio_pendiente_firma"

    # A quien lo crea no le hace falta que le avisen de su propio documento.
    notifs_claudia = Notificacion.query.filter_by(usuario_id=claudia.id, documento_cambio_id=documento.id).all()
    assert notifs_claudia == []


def test_firmar_documento_notifica_a_quien_falta_firmar(db):
    from app.models import Notificacion

    crear_usuario, manyana, tarde = _setup(db, "j")
    claudia = crear_usuario("Claudia Pérez", "claudiaj@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanj@h.es")

    documento = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja_id=manyana.id,
    )

    firmar_documento(documento, claudia, "data:image/png;base64,AAA")

    notifs_juan = Notificacion.query.filter_by(
        usuario_id=juan.id, documento_cambio_id=documento.id, tipo="documento_cambio_pendiente_firma"
    ).all()
    # Una al crear + otra al firmar Claudia (avisando de que ya solo falta él).
    assert len(notifs_juan) == 2


def test_firmar_documento_notifica_completo_a_ambos(db):
    from app.models import Notificacion

    crear_usuario, manyana, tarde = _setup(db, "k")
    claudia = crear_usuario("Claudia Pérez", "claudiak@h.es")
    juan = crear_usuario("Juan Rodríguez", "juank@h.es")

    documento = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja_id=manyana.id,
    )
    firmar_documento(documento, claudia, "data:image/png;base64,AAA")
    firmar_documento(documento, juan, "data:image/png;base64,BBB")

    for usuario in (claudia, juan):
        notifs = Notificacion.query.filter_by(
            usuario_id=usuario.id, documento_cambio_id=documento.id, tipo="documento_cambio_completo"
        ).all()
        assert len(notifs) == 1
