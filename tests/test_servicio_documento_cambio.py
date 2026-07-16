from datetime import date, time
from app.extensions import db
from app.models import Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria, Usuario, TurnoPlanilla, NotaDia
from app.services.documento_cambio import (
    crear_documento_cambio, firmar_documento, generar_notas_ilog, generar_pdf_documento,
    autorizar_documento, denegar_documento,
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


def test_numero_unidad_es_secuencial_por_unidad_y_no_por_id_global(db):
    """
    El número que ve la ayudante tiene que ser el mismo tipo de numeración
    que llevaba en papel: una secuencia propia de su unidad, empezando en 1,
    sin huecos ni saltos por cambios de otras unidades. No puede depender
    del id autoincremental de Postgres, que es compartido por toda la app.
    """
    crear_usuario_n, manyana_n, tarde_n = _setup(db, "n")
    claudia_n = crear_usuario_n("Claudia Pérez", "claudian@h.es")
    juan_n = crear_usuario_n("Juan Rodríguez", "juann@h.es")

    doc_n1 = crear_documento_cambio(
        creado_por=claudia_n, companero=juan_n,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana_n.id,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja_id=manyana_n.id,
    )
    assert doc_n1.numero_unidad == 1

    crear_usuario_o, manyana_o, tarde_o = _setup(db, "o")
    claudia_o = crear_usuario_o("Ana García", "anao@h.es")
    juan_o = crear_usuario_o("Bruno López", "brunoo@h.es")

    doc_o1 = crear_documento_cambio(
        creado_por=claudia_o, companero=juan_o,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana_o.id,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja_id=manyana_o.id,
    )
    # Nueva unidad -> su propia secuencia, aunque el id global siga creciendo.
    assert doc_o1.numero_unidad == 1
    assert doc_o1.id > doc_n1.id

    doc_n2 = crear_documento_cambio(
        creado_por=claudia_n, companero=juan_n,
        turno_cede_fecha=date(2026, 8, 7), turno_cede_franja_id=manyana_n.id,
        turno_recibe_fecha=date(2026, 8, 28), turno_recibe_franja_id=manyana_n.id,
    )
    assert doc_n2.numero_unidad == 2


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

    import pypdf
    import io as _io
    texto = pypdf.PdfReader(_io.BytesIO(pdf_bytes)).pages[0].extract_text()
    assert "Claudia Pérez" in texto
    assert "Juan Rodríguez" in texto
    assert "Mañana" in texto
    assert "07/07/2026" in texto
    assert "28/07/2026" in texto


def test_generar_pdf_documento_no_pierde_campos_con_nombres_largos(db):
    """
    Regresión: xhtml2pdf/reportlab descartan en silencio (sin error) el
    contenido de un @frame estático si no cabe en su altura -- ver
    PROGRESS.md, Fase 10. Un nombre de unidad u hospital largo no debe
    desaparecer del PDF.
    """
    crear_usuario, manyana, tarde = _setup(db, "g")
    hospital = manyana.grupo_intercambio.unidades[0].hospital
    hospital.nombre = "Hospital Universitario La Paz"
    unidad = manyana.grupo_intercambio.unidades[0]
    unidad.nombre = "Urgencias de Demostración"
    db.session.commit()

    claudia = crear_usuario("Claudia Pérez", "claudiag@h.es")
    juan = crear_usuario("Juan Rodríguez", "juang@h.es")
    documento = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja_id=manyana.id,
    )
    firmar_documento(documento, claudia, _FIRMA_PNG)
    firmar_documento(documento, juan, _FIRMA_PNG)

    pdf_bytes = generar_pdf_documento(documento)

    import pypdf
    import io as _io
    texto = pypdf.PdfReader(_io.BytesIO(pdf_bytes)).pages[0].extract_text()
    assert hospital.nombre in texto
    assert unidad.nombre in texto


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


def test_firmar_documento_envia_email_a_ambos_al_completarse(db, monkeypatch):
    enviados = []

    def _fake_enviar_email(destinatario, asunto, cuerpo_html):
        enviados.append((destinatario, asunto))
        return True

    monkeypatch.setattr("app.services.documento_cambio.enviar_email", _fake_enviar_email)

    crear_usuario, manyana, tarde = _setup(db, "l")
    claudia = crear_usuario("Claudia Pérez", "claudial@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanl@h.es")

    documento = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja_id=manyana.id,
    )
    assert enviados == []  # no se envía email solo por crear el documento

    firmar_documento(documento, claudia, "data:image/png;base64,AAA")
    assert enviados == []  # tampoco con una sola firma

    firmar_documento(documento, juan, "data:image/png;base64,BBB")

    destinatarios = {d for d, _ in enviados}
    assert destinatarios == {"claudial@h.es", "juanl@h.es"}


def test_firmar_documento_no_envia_email_si_usuario_lo_desactivo(db, monkeypatch):
    enviados = []

    def _fake_enviar_email(destinatario, asunto, cuerpo_html):
        enviados.append((destinatario, asunto))
        return True

    monkeypatch.setattr("app.services.documento_cambio.enviar_email", _fake_enviar_email)

    crear_usuario, manyana, tarde = _setup(db, "p")
    claudia = crear_usuario("Claudia Pérez", "claudiap@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanp@h.es")
    juan.notif_email_documento_cambio = False
    db.session.commit()

    documento = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja_id=manyana.id,
    )
    firmar_documento(documento, claudia, "data:image/png;base64,AAA")
    firmar_documento(documento, juan, "data:image/png;base64,BBB")

    destinatarios = {d for d, _ in enviados}
    assert destinatarios == {"claudiap@h.es"}  # Claudia sí, Juan lo desactivó


def _crear_documento_completo(db, sufijo):
    crear_usuario, manyana, tarde = _setup(db, sufijo)
    claudia = crear_usuario(f"Claudia{sufijo}", f"claudia{sufijo}@h.es")
    juan = crear_usuario(f"Juan{sufijo}", f"juan{sufijo}@h.es")
    supervisora = crear_usuario(f"Marta{sufijo}", f"marta{sufijo}@h.es")

    documento = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja_id=manyana.id,
    )
    firmar_documento(documento, claudia, "data:image/png;base64,AAA")
    firmar_documento(documento, juan, "data:image/png;base64,BBB")
    return documento, claudia, juan, supervisora, manyana


def test_autorizar_documento_vuelca_a_planillas(db):
    documento, claudia, juan, supervisora, manyana = _crear_documento_completo(db, "m")

    autorizar_documento(documento, supervisora)

    assert documento.decision_supervisora == "autorizado"
    assert documento.supervisora_id == supervisora.id
    assert documento.fecha_decision_supervisora is not None

    # Claudia ya no tiene el turno que cedió, y sí el que recibió.
    assert TurnoPlanilla.query.filter_by(
        usuario_id=claudia.id, fecha=date(2026, 7, 7), franja_horaria_id=manyana.id
    ).first() is None
    assert TurnoPlanilla.query.filter_by(
        usuario_id=claudia.id, fecha=date(2026, 7, 28), franja_horaria_id=manyana.id
    ).first() is not None

    # Juan al revés.
    assert TurnoPlanilla.query.filter_by(
        usuario_id=juan.id, fecha=date(2026, 7, 28), franja_horaria_id=manyana.id
    ).first() is None
    assert TurnoPlanilla.query.filter_by(
        usuario_id=juan.id, fecha=date(2026, 7, 7), franja_horaria_id=manyana.id
    ).first() is not None

    # Notas añadidas a la planilla de cada uno.
    assert NotaDia.query.filter_by(usuario_id=claudia.id, fecha=date(2026, 7, 7)).first() is not None
    assert NotaDia.query.filter_by(usuario_id=juan.id, fecha=date(2026, 7, 28)).first() is not None


def test_denegar_documento_no_toca_planillas(db):
    documento, claudia, juan, supervisora, manyana = _crear_documento_completo(db, "n")

    denegar_documento(documento, supervisora, motivo="Los turnos no cuadran con la planilla real.")

    assert documento.decision_supervisora == "denegado"
    assert documento.supervisora_id == supervisora.id
    assert documento.motivo_denegacion == "Los turnos no cuadran con la planilla real."

    # Nada cambia en las planillas.
    assert TurnoPlanilla.query.filter_by(usuario_id=claudia.id).count() == 0
    assert TurnoPlanilla.query.filter_by(usuario_id=juan.id).count() == 0


def test_denegar_documento_incluye_motivo_en_la_notificacion(db):
    from app.models import Notificacion

    documento, claudia, juan, supervisora, manyana = _crear_documento_completo(db, "o")

    denegar_documento(documento, supervisora, motivo="Falta el visto bueno de RRHH.")

    notif = Notificacion.query.filter_by(usuario_id=claudia.id, tipo="documento_cambio_denegado").first()
    assert "Falta el visto bueno de RRHH." in notif.mensaje


def test_autorizar_documento_incluye_datos_del_cambio_en_la_notificacion(db):
    """El aviso de autorización debe incluir quiénes hacen el cambio y qué
    día/turno libra y trabaja cada uno, no solo el número de hoja."""
    from app.models import Notificacion

    documento, claudia, juan, supervisora, manyana = _crear_documento_completo(db, "p")

    autorizar_documento(documento, supervisora)

    notif = Notificacion.query.filter_by(usuario_id=claudia.id, tipo="documento_cambio_autorizado").first()
    assert notif is not None
    assert claudia.nombre in notif.mensaje
    assert juan.nombre in notif.mensaje
    assert "07/07/2026" in notif.mensaje
    assert "28/07/2026" in notif.mensaje
    assert "Mañana" in notif.mensaje


def test_denegar_documento_incluye_datos_del_cambio_en_la_notificacion(db):
    """El aviso de denegación debe incluir quiénes hacen el cambio y qué
    día/turno libra y trabaja cada uno, no solo el motivo."""
    from app.models import Notificacion

    documento, claudia, juan, supervisora, manyana = _crear_documento_completo(db, "q")

    denegar_documento(documento, supervisora, motivo="Los turnos no cuadran.")

    notif = Notificacion.query.filter_by(usuario_id=juan.id, tipo="documento_cambio_denegado").first()
    assert notif is not None
    assert claudia.nombre in notif.mensaje
    assert juan.nombre in notif.mensaje
    assert "07/07/2026" in notif.mensaje
    assert "28/07/2026" in notif.mensaje
    assert "Mañana" in notif.mensaje
