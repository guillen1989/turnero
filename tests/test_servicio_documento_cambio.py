import pytest
from datetime import date, time
from app.extensions import db
from app.models import (
    Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria, Usuario, TurnoPlanilla,
    NotaDia, DocumentoCambio, ParticipanteDocumentoCambio, PlanillaMes,
)
from app.services.documento_cambio import (
    crear_documento_cambio, crear_documento_cambio_junte, crear_documento_cambio_cadena_3, firmar_documento,
    generar_notas_ilog, generar_pdf_documento,
    autorizar_documento, denegar_documento, anular_documento,
    registrar_documento_cambio_papel, CambioNoFactibleError,
    _usuario_que_recibe,
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


def test_firmar_documento_no_congela_nombres_tras_la_primera_firma(db):
    """Con una sola firma el documento sigue en borrador/pendiente_firmas:
    todavía puede pasar tiempo hasta la segunda, así que el nombre no debe
    congelarse antes de que el documento esté realmente completo."""
    crear_usuario, manyana, tarde = _setup(db, "n1")
    claudia = crear_usuario("Claudia Pérez", "claudian1@h.es")
    juan = crear_usuario("Juan Rodríguez", "juann1@h.es")
    documento = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja_id=manyana.id,
    )

    firmar_documento(documento, claudia, "data:image/png;base64,firmaclaudia")

    for p in documento.participantes:
        assert p.nombre_congelado is None


def test_firmar_documento_congela_nombres_al_completarse(db):
    """Al completarse (última firma) se congela el nombre de cada
    participante, para que sobreviva aunque más adelante se elimine
    alguna de las cuentas."""
    crear_usuario, manyana, tarde = _setup(db, "n2")
    claudia = crear_usuario("Claudia Pérez", "claudian2@h.es")
    juan = crear_usuario("Juan Rodríguez", "juann2@h.es")
    documento = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja_id=manyana.id,
    )

    firmar_documento(documento, claudia, "data:image/png;base64,firmaclaudia")
    firmar_documento(documento, juan, "data:image/png;base64,firmajuan")

    p_claudia = next(p for p in documento.participantes if p.usuario_id == claudia.id)
    p_juan = next(p for p in documento.participantes if p.usuario_id == juan.id)
    assert p_claudia.nombre_congelado == "Claudia Pérez"
    assert p_juan.nombre_congelado == "Juan Rodríguez"


def test_firmar_documento_conserva_nombre_congelado_si_se_elimina_la_cuenta(db):
    """El nombre congelado debe sobrevivir a eliminar_cuenta: es el motivo
    por el que existe."""
    from app.services.registro import eliminar_cuenta

    crear_usuario, manyana, tarde = _setup(db, "n3")
    claudia = crear_usuario("Claudia Pérez", "claudian3@h.es")
    juan = crear_usuario("Juan Rodríguez", "juann3@h.es")
    documento = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja_id=manyana.id,
    )
    firmar_documento(documento, claudia, "data:image/png;base64,firmaclaudia")
    firmar_documento(documento, juan, "data:image/png;base64,firmajuan")

    eliminar_cuenta(claudia)

    p_claudia = next(p for p in documento.participantes if p.usuario_id == claudia.id)
    assert p_claudia.nombre_mostrar == "Claudia Pérez"


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


def _crear_documento_cadena_3(db, crear_usuario, manyana, a_nombre, b_nombre, c_nombre):
    a = crear_usuario(a_nombre, f"{a_nombre.lower().replace(' ', '')}@h.es")
    b = crear_usuario(b_nombre, f"{b_nombre.lower().replace(' ', '')}@h.es")
    c = crear_usuario(c_nombre, f"{c_nombre.lower().replace(' ', '')}@h.es")

    doc = DocumentoCambio(
        creado_por=a, unidad_id=a.unidad_id, numero_unidad=1, tipo="cadena_3",
    )
    db.session.add(doc)
    db.session.flush()

    pa = ParticipanteDocumentoCambio(
        usuario=a, documento=doc,
        turno_cede_fecha=date(2026, 7, 1), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 3), turno_recibe_franja_id=manyana.id,
    )
    pb = ParticipanteDocumentoCambio(
        usuario=b, documento=doc,
        turno_cede_fecha=date(2026, 7, 2), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 1), turno_recibe_franja_id=manyana.id,
    )
    pc = ParticipanteDocumentoCambio(
        usuario=c, documento=doc,
        turno_cede_fecha=date(2026, 7, 3), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 2), turno_recibe_franja_id=manyana.id,
    )
    db.session.add_all([pa, pb, pc])
    db.session.commit()
    return doc, a, b, c, pa, pb, pc


def test_generar_notas_ilog_cadena_3_referencia_a_usuarios_correctos(db):
    crear_usuario, manyana, tarde = _setup(db, "gilc3")
    doc, a, b, c, pa, pb, pc = _crear_documento_cadena_3(
        db, crear_usuario, manyana, "Ana gilc3", "Berta gilc3", "Carmen gilc3",
    )

    notas = generar_notas_ilog(doc)

    assert len(notas) == 6

    nota_a_cede = next(
        n for n in notas if n["usuario"].id == a.id and n["fecha"] == date(2026, 7, 1)
    )
    assert b.nombre in nota_a_cede["texto"]
    assert a.nombre not in nota_a_cede["texto"]

    nota_b_cede = next(
        n for n in notas if n["usuario"].id == b.id and n["fecha"] == date(2026, 7, 2)
    )
    assert c.nombre in nota_b_cede["texto"]
    assert a.nombre not in nota_b_cede["texto"]

    nota_c_cede = next(
        n for n in notas if n["usuario"].id == c.id and n["fecha"] == date(2026, 7, 3)
    )
    assert a.nombre in nota_c_cede["texto"]
    assert b.nombre not in nota_c_cede["texto"]


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


def test_generar_pdf_documento_conserva_nombre_tras_eliminar_cuenta(db):
    """El PDF es el equivalente descargable de la hoja firmada: debe seguir
    mostrando quién firmó de verdad aunque luego elimine su cuenta."""
    from app.services.registro import eliminar_cuenta

    crear_usuario, manyana, tarde = _setup(db, "f2")
    claudia = crear_usuario("Claudia Pérez", "claudiaf2@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanf2@h.es")
    documento = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja_id=manyana.id,
    )
    firmar_documento(documento, claudia, _FIRMA_PNG)
    firmar_documento(documento, juan, _FIRMA_PNG)

    eliminar_cuenta(juan)

    pdf_bytes = generar_pdf_documento(documento)

    import pypdf
    import io as _io
    texto = pypdf.PdfReader(_io.BytesIO(pdf_bytes)).pages[0].extract_text()
    assert "Claudia Pérez" in texto
    assert "Juan Rodríguez" in texto
    assert "Usuario eliminado" not in texto


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


def test_generar_pdf_documento_incluye_motivo_de_denegacion(db):
    crear_usuario, manyana, tarde = _setup(db, "h")
    claudia = crear_usuario("Claudia Pérez", "claudiah@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanh@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martah@h.es")
    documento = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja_id=manyana.id,
    )
    firmar_documento(documento, claudia, _FIRMA_PNG)
    firmar_documento(documento, juan, _FIRMA_PNG)
    denegar_documento(documento, supervisora, motivo="No coincide con la planilla real.")

    pdf_bytes = generar_pdf_documento(documento)

    import pypdf
    import io as _io
    texto = pypdf.PdfReader(_io.BytesIO(pdf_bytes)).pages[0].extract_text()
    assert "No coincide con la planilla real." in texto


def test_generar_pdf_documento_pendiente_no_muestra_informe_de_la_supervisora(db):
    """Mientras no haya decisión, el hueco del informe de la supervisora
    debe quedar igual de vacío que en el impreso de papel."""
    crear_usuario, manyana, tarde = _setup(db, "i")
    claudia = crear_usuario("Claudia Pérez", "claudiai@h.es")
    juan = crear_usuario("Juan Rodríguez", "juani@h.es")
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
    # Ningún dato dinámico de este documento contiene "X": si aparece, es la
    # marca de favorable/desfavorable renderizada de más.
    assert "X" not in texto


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


def test_firmar_documento_cadena_3_envia_email_con_usuario_correcto(db, monkeypatch):
    enviados = []

    def _fake_enviar_email(destinatario, asunto, cuerpo_html):
        enviados.append((destinatario, asunto))
        return True

    monkeypatch.setattr("app.services.documento_cambio.enviar_email", _fake_enviar_email)

    crear_usuario, manyana, tarde = _setup(db, "fdc3e")
    doc, a, b, c, pa, pb, pc = _crear_documento_cadena_3(
        db, crear_usuario, manyana, "Ana fdc3e", "Berta fdc3e", "Carmen fdc3e",
    )

    firmar_documento(doc, a, _FIRMA_PNG)
    assert enviados == []

    firmar_documento(doc, b, _FIRMA_PNG)
    assert enviados == []

    firmar_documento(doc, c, _FIRMA_PNG)

    destinatarios = {d for d, _ in enviados}
    assert destinatarios == {a.email, b.email, c.email}


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


def test_autorizar_documento_guarda_la_firma_de_la_supervisora(db):
    documento, claudia, juan, supervisora, manyana = _crear_documento_completo(db, "r")

    autorizar_documento(documento, supervisora, imagen_firma=_FIRMA_PNG)

    assert documento.firma_supervisora == _FIRMA_PNG


def test_denegar_documento_guarda_la_firma_de_la_supervisora(db):
    documento, claudia, juan, supervisora, manyana = _crear_documento_completo(db, "s")

    denegar_documento(documento, supervisora, motivo="No cuadra.", imagen_firma=_FIRMA_PNG)

    assert documento.firma_supervisora == _FIRMA_PNG


def test_registrar_documento_cambio_papel_queda_completo_y_autorizado(db):
    """El cambio ya se firmó a mano en papel: no tiene sentido pedir firmas
    digitales, así que queda directamente completo y autorizado, aplicado a
    las planillas de los dos implicados."""
    crear_usuario, manyana, tarde = _setup(db, "u")
    claudia = crear_usuario("Claudia Pérez", "claudiau@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanu@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martau@h.es")

    documento = registrar_documento_cambio_papel(
        supervisora=supervisora, usuario1=claudia, usuario2=juan,
        turno1_cede_fecha=date(2026, 7, 7), turno1_cede_franja_id=manyana.id,
        turno1_recibe_fecha=date(2026, 7, 28), turno1_recibe_franja_id=manyana.id,
    )

    assert documento.origen_papel is True
    assert documento.estado == "completo"
    assert documento.decision_supervisora == "autorizado"
    assert documento.supervisora_id == supervisora.id
    assert documento.numero_unidad >= 1
    assert len(documento.firmas) == 0  # no hay firma digital, se firmó en papel

    assert TurnoPlanilla.query.filter_by(
        usuario_id=claudia.id, fecha=date(2026, 7, 28), franja_horaria_id=manyana.id
    ).first() is not None
    assert TurnoPlanilla.query.filter_by(
        usuario_id=claudia.id, fecha=date(2026, 7, 7), franja_horaria_id=manyana.id
    ).first() is None
    assert TurnoPlanilla.query.filter_by(
        usuario_id=juan.id, fecha=date(2026, 7, 7), franja_horaria_id=manyana.id
    ).first() is not None


def test_registrar_documento_cambio_papel_congela_los_nombres(db):
    """El documento queda completo desde el momento en que se registra, así
    que el nombre debe congelarse ya en el registro, no esperar a un evento
    posterior que en este flujo nunca llega (no hay firmas digitales)."""
    crear_usuario, manyana, tarde = _setup(db, "w")
    claudia = crear_usuario("Claudia Pérez", "claudiaw@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanw@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martaw@h.es")

    documento = registrar_documento_cambio_papel(
        supervisora=supervisora, usuario1=claudia, usuario2=juan,
        turno1_cede_fecha=date(2026, 7, 7), turno1_cede_franja_id=manyana.id,
        turno1_recibe_fecha=date(2026, 7, 28), turno1_recibe_franja_id=manyana.id,
    )

    p_claudia = next(p for p in documento.participantes if p.usuario_id == claudia.id)
    p_juan = next(p for p in documento.participantes if p.usuario_id == juan.id)
    assert p_claudia.nombre_congelado == "Claudia Pérez"
    assert p_juan.nombre_congelado == "Juan Rodríguez"


def test_registrar_documento_cambio_papel_no_factible_no_se_aplica(db):
    """Si la comprobación descubre que el cambio no es factible (p.ej. quien
    dice ceder un turno en realidad no lo trabaja según su planilla
    publicada), no se debe crear ni aplicar el documento."""
    crear_usuario, manyana, tarde = _setup(db, "v")
    claudia = crear_usuario("Claudia Pérez", "claudiav@h.es")
    juan = crear_usuario("Juan Rodríguez", "juanv@h.es")
    supervisora = crear_usuario("Marta Supervisora", "martav@h.es")
    db.session.add_all([
        PlanillaMes(usuario=claudia, anyo=2026, mes=7, publicada=True),
        PlanillaMes(usuario=juan, anyo=2026, mes=7, publicada=True),
    ])
    db.session.commit()
    # Ninguno tiene turnos reales en planilla: Claudia no puede ceder el
    # turno de mañana del 7/7 que dice ceder.

    numero_antes = DocumentoCambio.query.count()
    with pytest.raises(CambioNoFactibleError):
        registrar_documento_cambio_papel(
            supervisora=supervisora, usuario1=claudia, usuario2=juan,
            turno1_cede_fecha=date(2026, 7, 7), turno1_cede_franja_id=manyana.id,
            turno1_recibe_fecha=date(2026, 7, 28), turno1_recibe_franja_id=manyana.id,
        )

    assert DocumentoCambio.query.count() == numero_antes
    assert TurnoPlanilla.query.filter_by(usuario_id=claudia.id).count() == 0


def test_autorizar_documento_sin_firma_no_la_rellena(db):
    """La firma es opcional a nivel de servicio (los tests/flujos internos
    que no pasan por HTTP no tienen por qué firmar); es la ruta la que la
    exige antes de llamar aquí."""
    documento, claudia, juan, supervisora, manyana = _crear_documento_completo(db, "t")

    autorizar_documento(documento, supervisora)

    assert documento.firma_supervisora is None


# ── Tests nuevos: recálculo de factibilidad de dependientes ─────────────────


def test_al_autorizar_recalcula_factibilidad_dependientes(db):
    """Al autorizar un documento, los documentos que dependen de él recalculan
    su factibilidad (ya sin overlay, contra el nuevo estado real de planilla).
    Si el estado real tras el volcado sigue siendo factible, el dependiente
    sigue factible -- pero el recálculo debe haberse ejecutado."""
    from app.models import DocumentoCambio, ParticipanteDocumentoCambio, PlanillaMes

    crear_usuario, manyana, tarde = _setup(db, "rd1")
    claudia = crear_usuario("Claudiard1", "claudiard1@h.es")
    juan = crear_usuario("Juanrd1", "juanrd1@h.es")
    ana = crear_usuario("Anard1", "anard1@h.es")
    supervisora = crear_usuario("Martard1", "martard1@h.es")

    for u in (claudia, juan, ana):
        db.session.add(PlanillaMes(usuario=u, anyo=2026, mes=7, publicada=True))
    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 7), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 14), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=ana, fecha=date(2026, 7, 21), franja_horaria=manyana))
    db.session.commit()

    # Doc A (predecesor): Claudia(7/7) ↔ Juan(14/7)
    doc_a = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 14), turno_recibe_franja_id=manyana.id,
    )
    firmar_documento(doc_a, claudia, "x")
    firmar_documento(doc_a, juan, "y")

    # Doc B: Juan(14/7, que perderá al autorizar A) ↔ Ana(21/7)
    # Sin overlay: Juan tiene 14/7 → B es factible.
    # Con overlay (A pendiente): Juan pierde 14/7 → B no_factible.
    # Para que B sea factible con overlay usamos: Juan(7/7) ↔ Ana(21/7)
    # Juan gana 7/7 en overlay de A.
    doc_b = DocumentoCambio(
        creado_por=juan, unidad_id=juan.unidad_id, numero_unidad=99,
        depende_de_id=doc_a.id,
    )
    db.session.add(doc_b)
    db.session.flush()
    doc_b.participantes.append(ParticipanteDocumentoCambio(
        usuario=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja=manyana,
        turno_recibe_fecha=date(2026, 7, 21), turno_recibe_franja=manyana,
    ))
    doc_b.participantes.append(ParticipanteDocumentoCambio(
        usuario=ana,
        turno_cede_fecha=date(2026, 7, 21), turno_cede_franja=manyana,
        turno_recibe_fecha=date(2026, 7, 7), turno_recibe_franja=manyana,
    ))
    db.session.commit()

    from app.services.factibilidad_documento_cambio import comprobar_factibilidad
    estado_b, _ = comprobar_factibilidad(doc_b)
    assert estado_b == "factible", f"Esperaba factible con overlay, obtuve {estado_b}"

    # Forzar B a un estado conocido (no_verificado) para detectar recálculo
    doc_b.factibilidad_estado = "no_verificado"
    db.session.commit()

    # Autorizar A → recálculo de B: Juan ahora tiene 7/7 en planilla real
    # (A volcó), así que B sigue siendo factible.
    autorizar_documento(doc_a, supervisora)
    db.session.refresh(doc_b)
    # El recálculo debe haber ocurrido: B ya no está en no_verificado
    assert doc_b.factibilidad_estado == "factible"


def test_al_denegar_documento_dependientes_pasan_a_no_factible(db):
    """Denegar un predecesor invalida el overlay: el dependiente ya no puede
    contar con esos turnos."""
    from app.models import DocumentoCambio, ParticipanteDocumentoCambio, PlanillaMes

    crear_usuario, manyana, tarde = _setup(db, "rd2")
    claudia = crear_usuario("Claudiard2", "claudiard2@h.es")
    juan = crear_usuario("Juanrd2", "juanrd2@h.es")
    ana = crear_usuario("Anard2", "anard2@h.es")
    supervisora = crear_usuario("Martard2", "martard2@h.es")

    for u in (claudia, juan, ana):
        db.session.add(PlanillaMes(usuario=u, anyo=2026, mes=7, publicada=True))
    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 7), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 14), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=ana, fecha=date(2026, 7, 21), franja_horaria=manyana))
    db.session.commit()

    doc_a = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 14), turno_recibe_franja_id=manyana.id,
    )
    firmar_documento(doc_a, claudia, "x")
    firmar_documento(doc_a, juan, "y")

    doc_b = DocumentoCambio(
        creado_por=juan, unidad_id=juan.unidad_id, numero_unidad=99,
        depende_de_id=doc_a.id,
    )
    db.session.add(doc_b)
    db.session.flush()
    doc_b.participantes.append(ParticipanteDocumentoCambio(
        usuario=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja=manyana,
        turno_recibe_fecha=date(2026, 7, 21), turno_recibe_franja=manyana,
    ))
    doc_b.participantes.append(ParticipanteDocumentoCambio(
        usuario=ana,
        turno_cede_fecha=date(2026, 7, 21), turno_cede_franja=manyana,
        turno_recibe_fecha=date(2026, 7, 7), turno_recibe_franja=manyana,
    ))
    db.session.commit()
    from app.services.factibilidad_documento_cambio import comprobar_factibilidad
    estado_b, _ = comprobar_factibilidad(doc_b)
    assert estado_b == "factible"

    # Denegar A → B ya no puede contar con overlay → no_factible
    denegar_documento(doc_a, supervisora, motivo="No válido")
    db.session.refresh(doc_b)
    assert doc_b.factibilidad_estado == "no_factible"


def test_al_anular_documento_autorizado_dependientes_pasan_a_no_factible(db):
    """Anular un documento ya autorizado revierte las planillas; los
    dependientes pierden el estado real que ganaron y pasan a no_factible."""
    from app.models import DocumentoCambio, ParticipanteDocumentoCambio, PlanillaMes

    crear_usuario, manyana, tarde = _setup(db, "rd3")
    claudia = crear_usuario("Claudiard3", "claudiard3@h.es")
    juan = crear_usuario("Juanrd3", "juanrd3@h.es")
    ana = crear_usuario("Anard3", "anard3@h.es")
    supervisora = crear_usuario("Martard3", "martard3@h.es")

    for u in (claudia, juan, ana):
        db.session.add(PlanillaMes(usuario=u, anyo=2026, mes=7, publicada=True))
    db.session.add(TurnoPlanilla(usuario=claudia, fecha=date(2026, 7, 7), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=juan, fecha=date(2026, 7, 14), franja_horaria=manyana))
    db.session.add(TurnoPlanilla(usuario=ana, fecha=date(2026, 7, 21), franja_horaria=manyana))
    db.session.commit()

    # Doc A: Claudia(7/7) ↔ Juan(14/7) — lo autorizamos (vuelca a planilla)
    doc_a = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 14), turno_recibe_franja_id=manyana.id,
    )
    firmar_documento(doc_a, claudia, "x")
    firmar_documento(doc_a, juan, "y")
    autorizar_documento(doc_a, supervisora)
    # Después de autorizar: Juan gana 7/7 en planilla real, Claudia gana 14/7

    # Doc B: Juan(cede 7/7, ganado de A) ↔ Ana(cede 21/7)
    doc_b = DocumentoCambio(
        creado_por=juan, unidad_id=juan.unidad_id, numero_unidad=99,
    )
    db.session.add(doc_b)
    db.session.flush()
    doc_b.participantes.append(ParticipanteDocumentoCambio(
        usuario=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja=manyana,
        turno_recibe_fecha=date(2026, 7, 21), turno_recibe_franja=manyana,
    ))
    doc_b.participantes.append(ParticipanteDocumentoCambio(
        usuario=ana,
        turno_cede_fecha=date(2026, 7, 21), turno_cede_franja=manyana,
        turno_recibe_fecha=date(2026, 7, 7), turno_recibe_franja=manyana,
    ))
    db.session.commit()

    # Hacer que B dependa de A para que se recalcule al anular A
    doc_b.depende_de_id = doc_a.id
    db.session.commit()

    # B es factible porque Juan tiene 7/7 en planilla real (gracias a A)
    from app.services.factibilidad_documento_cambio import comprobar_factibilidad
    estado_b, motivos = comprobar_factibilidad(doc_b)
    assert estado_b == "factible", f"Esperaba factible, obtuve {estado_b}: {motivos}"

    # Anular A → revierte planillas: Juan pierde 7/7
    # B ya no puede contar con que Juan tenga 7/7 → no_factible
    anular_documento(doc_a, supervisora, motivo="Error")
    db.session.refresh(doc_b)
    assert doc_b.factibilidad_estado == "no_factible"


def test_usuario_que_recibe_cadena_3_identifica_recibidor_en_ciclo_A_B_C_A(db):
    crear_usuario, manyana, tarde = _setup(db, "uqrc3")
    a = crear_usuario("Ana", "anauqrc3@h.es")
    b = crear_usuario("Berta", "bertauqrc3@h.es")
    c = crear_usuario("Carmen", "carmenuqrc3@h.es")

    documento = DocumentoCambio(
        creado_por=a,
        unidad_id=a.unidad_id,
        numero_unidad=1,
        tipo="cadena_3",
    )
    db.session.add(documento)
    db.session.flush()

    pa = ParticipanteDocumentoCambio(
        usuario=a, documento=documento,
        turno_cede_fecha=date(2026, 7, 1), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 3), turno_recibe_franja_id=manyana.id,
    )
    pb = ParticipanteDocumentoCambio(
        usuario=b, documento=documento,
        turno_cede_fecha=date(2026, 7, 2), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 1), turno_recibe_franja_id=manyana.id,
    )
    pc = ParticipanteDocumentoCambio(
        usuario=c, documento=documento,
        turno_cede_fecha=date(2026, 7, 3), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 2), turno_recibe_franja_id=manyana.id,
    )
    db.session.add_all([pa, pb, pc])
    db.session.commit()

    assert _usuario_que_recibe(documento, pa) == b
    assert _usuario_que_recibe(documento, pb) == c
    assert _usuario_que_recibe(documento, pc) == a


def test_usuario_que_recibe_funciona_con_2_participantes_igual_que_exclusion(db):
    crear_usuario, manyana, tarde = _setup(db, "uqr2")
    claudia = crear_usuario("Claudia UQR2", "claudiauqr2@h.es")
    juan = crear_usuario("Juan UQR2", "juanuqr2@h.es")

    documento = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja_id=manyana.id,
    )

    p_claudia = next(p for p in documento.participantes if p.usuario_id == claudia.id)
    p_juan = next(p for p in documento.participantes if p.usuario_id == juan.id)

    assert _usuario_que_recibe(documento, p_claudia) == juan
    assert _usuario_que_recibe(documento, p_juan) == claudia


def test_crear_documento_cambio_junte_genera_filas_espejo_por_noche(db):
    from app.models import Notificacion

    crear_usuario, manyana, tarde = _setup(db, "junte1")
    claudia = crear_usuario("Claudia Junte", "claudiajunte1@h.es")
    juan = crear_usuario("Juan Junte", "juanjunte1@h.es")

    cedidos = [
        (date(2026, 7, 6), manyana.id),
        (date(2026, 7, 7), manyana.id),
        (date(2026, 7, 8), manyana.id),
    ]
    aceptados = [
        (date(2026, 7, 20), manyana.id),
        (date(2026, 7, 21), manyana.id),
        (date(2026, 7, 22), manyana.id),
    ]

    documento = crear_documento_cambio_junte(
        creado_por=claudia, companero=juan, cedidos=cedidos, aceptados=aceptados,
    )

    assert documento.tipo == "junte"
    assert documento.estado == "borrador"
    assert len(documento.participantes) == 6

    filas_claudia = sorted(
        (p for p in documento.participantes if p.usuario_id == claudia.id),
        key=lambda p: p.turno_cede_fecha,
    )
    filas_juan = sorted(
        (p for p in documento.participantes if p.usuario_id == juan.id),
        key=lambda p: p.turno_cede_fecha,
    )
    assert len(filas_claudia) == 3
    assert len(filas_juan) == 3

    for i, (fecha_cede, franja_id) in enumerate(cedidos):
        assert filas_claudia[i].turno_cede_fecha == fecha_cede
        assert filas_claudia[i].turno_cede_franja_id == franja_id
        assert filas_claudia[i].turno_recibe_fecha == aceptados[i][0]
        # El compañero es el espejo exacto de cada fila.
        assert filas_juan[i].turno_cede_fecha == aceptados[i][0]
        assert filas_juan[i].turno_recibe_fecha == fecha_cede

    notifs_juan = Notificacion.query.filter_by(usuario_id=juan.id, documento_cambio_id=documento.id).all()
    assert len(notifs_juan) == 1
    assert notifs_juan[0].tipo == "documento_cambio_pendiente_firma"
    notifs_claudia = Notificacion.query.filter_by(usuario_id=claudia.id, documento_cambio_id=documento.id).all()
    assert notifs_claudia == []


def test_crear_documento_cambio_junte_calcula_factibilidad_no_verificado_por_defecto(db):
    crear_usuario, manyana, tarde = _setup(db, "junte2")
    claudia = crear_usuario("Claudia Junte2", "claudiajunte2@h.es")
    juan = crear_usuario("Juan Junte2", "juanjunte2@h.es")

    cedidos = [(date(2026, 7, 6), manyana.id)]
    aceptados = [(date(2026, 7, 20), manyana.id)]

    # Ninguna planilla publicada -> no se puede verificar todavía.
    documento = crear_documento_cambio_junte(
        creado_por=claudia, companero=juan, cedidos=cedidos, aceptados=aceptados,
    )

    assert documento.factibilidad_estado == "no_verificado"


def test_generar_pdf_documento_junte_muestra_las_dos_distribuciones(db):
    """documento.tipo == 'junte': generar_pdf_documento agrupa las filas por
    usuario, calcula su distribución semanal (Paso 2) y pasa mostrar_junte +
    las variables junte_* que espera pdf.html (Paso 5 de docs/PLAN_JUNTE.md)."""
    import pypdf
    import io as _io

    crear_usuario, manyana, tarde = _setup(db, "junte3")
    claudia = crear_usuario("Claudia Junte3", "claudiajunte3@h.es")
    juan = crear_usuario("Juan Junte3", "juanjunte3@h.es")

    # Semana de referencia: lunes 6/7/2026. LMVD = lunes,miércoles,viernes,domingo
    # (weekday 0,2,4,6); MJS = martes,jueves,sábado (weekday 1,3,5).
    # Claudia (LMVD) cede lunes/miércoles/viernes (se queda el domingo) y
    # acepta martes/jueves/sábado de Juan (MJS, los cede todos).
    cedidos = [
        (date(2026, 7, 6), manyana.id),   # lunes
        (date(2026, 7, 8), manyana.id),   # miércoles
        (date(2026, 7, 10), manyana.id),  # viernes
    ]
    aceptados = [
        (date(2026, 7, 7), manyana.id),   # martes
        (date(2026, 7, 9), manyana.id),   # jueves
        (date(2026, 7, 11), manyana.id),  # sábado
    ]

    documento = crear_documento_cambio_junte(
        creado_por=claudia, companero=juan, cedidos=cedidos, aceptados=aceptados,
    )
    firmar_documento(documento, claudia, _FIRMA_PNG)
    firmar_documento(documento, juan, _FIRMA_PNG)

    pdf_bytes = generar_pdf_documento(documento)

    assert pdf_bytes[:5] == b"%PDF-"
    texto = pypdf.PdfReader(_io.BytesIO(pdf_bytes)).pages[0].extract_text()
    # Claudia aparece en la cabecera común (solicitante) + en las dos tablas
    # del junte (corresponde/cambio) de su propia distribución -- 3 veces.
    assert texto.count("Claudia Junte3") == 3
    # Juan solo aparece en las tablas del junte: el bloque de turno único
    # (companero_c) está oculto en un junte.
    assert texto.count("Juan Junte3") == 2
    # No debe aparecer el bloque de turno único (cede_franja_c/etc.), que en
    # un junte no representa bien la relación (varias filas por persona).
    assert "Mañana" not in texto


def test_contexto_pdf_cadena_3_para_documento_tipo_cadena_3_devuelve_variables(db):
    from app.services.documento_cambio import _contexto_pdf_cadena_3

    crear_usuario, manyana, tarde = _setup(db, "ctxc3")
    a = crear_usuario("Ana", "anactxc3@h.es")
    b = crear_usuario("Berta", "bertactxc3@h.es")
    c = crear_usuario("Carmen", "carmenctxc3@h.es")

    documento = DocumentoCambio(
        creado_por=a, unidad_id=a.unidad_id, numero_unidad=1, tipo="cadena_3",
    )
    db.session.add(documento)
    db.session.flush()

    pa = ParticipanteDocumentoCambio(
        usuario=a, documento=documento,
        turno_cede_fecha=date(2026, 7, 1), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 3), turno_recibe_franja_id=manyana.id,
    )
    pb = ParticipanteDocumentoCambio(
        usuario=b, documento=documento,
        turno_cede_fecha=date(2026, 7, 2), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 1), turno_recibe_franja_id=manyana.id,
    )
    pc = ParticipanteDocumentoCambio(
        usuario=c, documento=documento,
        turno_cede_fecha=date(2026, 7, 3), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 2), turno_recibe_franja_id=manyana.id,
    )
    db.session.add_all([pa, pb, pc])

    firmar_documento(documento, a, _FIRMA_PNG)
    firmar_documento(documento, b, _FIRMA_PNG)
    firmar_documento(documento, c, _FIRMA_PNG)

    resultado = _contexto_pdf_cadena_3(documento)

    assert resultado["mostrar_cadena_3"] is True
    assert resultado["cede_tercer_franja_c"] == "Mañana"
    assert "Carmen" in resultado["tercer_companero_c"]
    # Carmen (tercero) pasa a trabajar lo que cede Berta (02/07), no lo que
    # ella misma cede (03/07) -- eso ya está en cede_franja_c/cede_fecha_c.
    assert resultado["cede_tercer_fecha_c"] == "02/07/2026"
    assert resultado["firma_tercero"] is not None


def test_contexto_pdf_cadena_3_para_documento_no_cadena_3_devuelve_mostrar_false(db):
    from app.services.documento_cambio import _contexto_pdf_cadena_3

    crear_usuario, manyana, tarde = _setup(db, "ctxnc3")
    claudia = crear_usuario("Claudia", "claudiagtxnc3@h.es")
    juan = crear_usuario("Juan", "juangtxnc3@h.es")

    documento = crear_documento_cambio(
        creado_por=claudia, companero=juan,
        turno_cede_fecha=date(2026, 7, 7), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 28), turno_recibe_franja_id=manyana.id,
    )

    resultado = _contexto_pdf_cadena_3(documento)

    assert resultado == {"mostrar_cadena_3": False}


def test_generar_pdf_documento_cadena_3_muestra_los_tres_participantes(db):
    import pypdf
    import io as _io

    crear_usuario, manyana, tarde = _setup(db, "pdfc3")
    a = crear_usuario("Ana", "anapdfc3@h.es")
    b = crear_usuario("Berta", "bertapdfc3@h.es")
    c = crear_usuario("Carmen", "carmenpdfc3@h.es")

    documento = DocumentoCambio(
        creado_por=a, unidad_id=a.unidad_id, numero_unidad=1, tipo="cadena_3",
    )
    db.session.add(documento)
    db.session.flush()

    pa = ParticipanteDocumentoCambio(
        usuario=a, documento=documento,
        turno_cede_fecha=date(2026, 7, 1), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 3), turno_recibe_franja_id=manyana.id,
    )
    pb = ParticipanteDocumentoCambio(
        usuario=b, documento=documento,
        turno_cede_fecha=date(2026, 7, 2), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 1), turno_recibe_franja_id=manyana.id,
    )
    pc = ParticipanteDocumentoCambio(
        usuario=c, documento=documento,
        turno_cede_fecha=date(2026, 7, 3), turno_cede_franja_id=manyana.id,
        turno_recibe_fecha=date(2026, 7, 2), turno_recibe_franja_id=manyana.id,
    )
    db.session.add_all([pa, pb, pc])
    db.session.commit()

    firmar_documento(documento, a, _FIRMA_PNG)
    firmar_documento(documento, b, _FIRMA_PNG)
    firmar_documento(documento, c, _FIRMA_PNG)

    pdf_bytes = generar_pdf_documento(documento)

    assert pdf_bytes[:5] == b"%PDF-"
    texto = pypdf.PdfReader(_io.BytesIO(pdf_bytes)).pages[0].extract_text()
    assert "Ana" in texto
    assert "Berta" in texto
    assert "Carmen" in texto
    assert "01/07/2026" in texto
    assert "03/07/2026" in texto
    assert "lo trabaja" in texto


def test_crear_documento_cambio_cadena_3_crea_documento_con_ciclo_abc(db):
    from app.models import Notificacion

    crear_usuario, manyana, tarde = _setup(db, "cadena3_1")
    ana = crear_usuario("Ana Cadena3_1", "anacadena3_1@h.es")
    berta = crear_usuario("Berta Cadena3_1", "bertacadena3_1@h.es")
    carmen = crear_usuario("Carmen Cadena3_1", "carmencadena3_1@h.es")

    turno_ana_cede = (date(2026, 7, 1), manyana.id)
    turno_berta_cede = (date(2026, 7, 2), manyana.id)
    turno_carmen_cede = (date(2026, 7, 3), manyana.id)

    documento = crear_documento_cambio_cadena_3(
        creado_por=ana, companero=berta, tercero=carmen,
        turno_creado_por_cede=turno_ana_cede,
        turno_companero_cede=turno_berta_cede,
        turno_tercero_cede=turno_carmen_cede,
    )

    assert documento.tipo == "cadena_3"
    assert documento.estado == "borrador"
    assert len(documento.participantes) == 3

    p_ana = next(p for p in documento.participantes if p.usuario_id == ana.id)
    p_berta = next(p for p in documento.participantes if p.usuario_id == berta.id)
    p_carmen = next(p for p in documento.participantes if p.usuario_id == carmen.id)

    assert p_ana.turno_cede_fecha == turno_ana_cede[0]
    assert p_ana.turno_cede_franja_id == turno_ana_cede[1]
    assert p_ana.turno_recibe_fecha == turno_carmen_cede[0]
    assert p_ana.turno_recibe_franja_id == turno_carmen_cede[1]

    assert p_berta.turno_cede_fecha == turno_berta_cede[0]
    assert p_berta.turno_recibe_fecha == turno_ana_cede[0]

    assert p_carmen.turno_cede_fecha == turno_carmen_cede[0]
    assert p_carmen.turno_recibe_fecha == turno_berta_cede[0]

    assert _usuario_que_recibe(documento, p_ana) == berta
    assert _usuario_que_recibe(documento, p_berta) == carmen
    assert _usuario_que_recibe(documento, p_carmen) == ana

    notifs_berta = Notificacion.query.filter_by(usuario_id=berta.id, documento_cambio_id=documento.id).all()
    assert len(notifs_berta) == 1
    assert notifs_berta[0].tipo == "documento_cambio_pendiente_firma"
    notifs_carmen = Notificacion.query.filter_by(usuario_id=carmen.id, documento_cambio_id=documento.id).all()
    assert len(notifs_carmen) == 1
    notifs_ana = Notificacion.query.filter_by(usuario_id=ana.id, documento_cambio_id=documento.id).all()
    assert notifs_ana == []


def test_crear_documento_cambio_cadena_3_calcula_factibilidad_no_verificado_por_defecto(db):
    crear_usuario, manyana, tarde = _setup(db, "cadena3_2")
    ana = crear_usuario("Ana Cadena3_2", "anacadena3_2@h.es")
    berta = crear_usuario("Berta Cadena3_2", "bertacadena3_2@h.es")
    carmen = crear_usuario("Carmen Cadena3_2", "carmencadena3_2@h.es")

    documento = crear_documento_cambio_cadena_3(
        creado_por=ana, companero=berta, tercero=carmen,
        turno_creado_por_cede=(date(2026, 7, 1), manyana.id),
        turno_companero_cede=(date(2026, 7, 2), manyana.id),
        turno_tercero_cede=(date(2026, 7, 3), manyana.id),
    )

    assert documento.factibilidad_estado == "no_verificado"
