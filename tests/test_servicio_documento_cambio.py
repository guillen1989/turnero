from datetime import date, time
from app.models import Hospital, GrupoIntercambio, Unidad, Categoria, FranjaHoraria, Usuario
from app.services.documento_cambio import (
    crear_documento_cambio, firmar_documento, generar_notas_ilog,
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
