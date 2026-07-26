"""Helpers compartidos por los tests de tests/test_documento_cambio_*.py
(divididos a partir del antiguo test_rutas_documento_cambio.py)."""
from datetime import date, time, timedelta

from app.extensions import db
from app.models import Categoria, FranjaHoraria, GrupoIntercambio, Hospital, Unidad, Usuario



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

    def crear_usuario(nombre, email, password="password123"):
        u = Usuario(nombre=nombre, email=email, unidad=unidad, categoria=categoria)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        return u

    return crear_usuario, manyana, tarde


def _login(client, email, password="password123"):
    return client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=True)


def _mes_actual_y_siguiente():
    hoy = date.today()
    fecha_este_mes = date(hoy.year, hoy.month, 1)
    anyo_sig, mes_sig = (hoy.year + 1, 1) if hoy.month == 12 else (hoy.year, hoy.month + 1)
    fecha_mes_siguiente = date(anyo_sig, mes_sig, 1)
    return fecha_este_mes, fecha_mes_siguiente


def _crear_documento_completo(db, creado_por, companero, franja_cede, franja_recibe, fecha_cede, fecha_recibe):
    """Crea y firma (con las dos partes) un documento directamente vía
    servicio, sin pasar por el cliente HTTP -- útil cuando se necesitan
    fechas/franjas concretas para probar filtros."""
    from app.services.documento_cambio import crear_documento_cambio, firmar_documento

    documento = crear_documento_cambio(
        creado_por, companero, fecha_cede, franja_cede.id, fecha_recibe, franja_recibe.id,
    )
    firmar_documento(documento, creado_por, _FIRMA_PNG)
    firmar_documento(documento, companero, _FIRMA_PNG)
    return documento


def _crear_documento_completo_via_client(client, claudia, juan, manyana):
    resp = client.post("/documentos-cambio/nuevo", data={
        "companero_id": juan.id,
        "turno_cede_fecha": "2026-07-07",
        "turno_cede_franja_id": manyana.id,
        "turno_recibe_fecha": "2026-07-28",
        "turno_recibe_franja_id": manyana.id,
    })
    documento_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])
    from app.models import DocumentoCambio
    p1, p2 = db.session.get(DocumentoCambio, documento_id).participantes

    client.post(f"/documentos-cambio/{documento_id}/firmar/{p1.id}", data={"imagen_firma": _FIRMA_PNG})
    client.get("/auth/logout")
    _login(client, juan.email)
    client.post(f"/documentos-cambio/{documento_id}/firmar/{p2.id}", data={"imagen_firma": _FIRMA_PNG})
    return documento_id


def _fecha_futura(dias=10):
    return date.today() + timedelta(days=dias)


def _crear_y_autorizar(db, client, claudia, juan, supervisora, manyana):
    from app.services.documento_cambio import autorizar_documento

    doc = _crear_documento_completo(
        db, claudia, juan, manyana, manyana,
        _fecha_futura(10), _fecha_futura(20),
    )
    autorizar_documento(doc, supervisora)
    return doc


def _crear_documento_pendiente(db, claudia, juan, manyana, tarde, fecha_cede, fecha_recibe):
    """Crea y completa (dos firmas) un documento, dejándolo pendiente de
    decisión de la supervisora."""
    from app.services.documento_cambio import crear_documento_cambio, firmar_documento
    doc = crear_documento_cambio(
        claudia, juan, fecha_cede, manyana.id, fecha_recibe, tarde.id,
    )
    firmar_documento(doc, claudia, _FIRMA_PNG)
    firmar_documento(doc, juan, _FIRMA_PNG)
    return doc
