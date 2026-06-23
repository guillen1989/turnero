from datetime import time

from app.extensions import db
from app.models import FranjaHoraria, TurnoCedido, TurnoAceptado

PLANTILLAS = {
    "tres_turnos": {
        "nombre": "Sistema de 3 turnos",
        "descripcion": "Mañana (8-15 h), Tarde (15-22 h), Noche (22-8 h)",
        "franjas": [
            ("Mañana", time(8, 0), time(15, 0)),
            ("Tarde", time(15, 0), time(22, 0)),
            ("Noche", time(22, 0), time(8, 0)),
        ],
    },
    "doce_horas": {
        "nombre": "Sistema de 12 horas",
        "descripcion": "Diurno (8-20 h), Nocturno (20-8 h)",
        "franjas": [
            ("Diurno", time(8, 0), time(20, 0)),
            ("Nocturno", time(20, 0), time(8, 0)),
        ],
    },
    "mixto": {
        "nombre": "Mixto (3 turnos + 12 horas)",
        "descripcion": "Mañana, Tarde, Noche, Diurno y Nocturno",
        "franjas": [
            ("Mañana", time(8, 0), time(15, 0)),
            ("Tarde", time(15, 0), time(22, 0)),
            ("Noche", time(22, 0), time(8, 0)),
            ("Diurno", time(8, 0), time(20, 0)),
            ("Nocturno", time(20, 0), time(8, 0)),
        ],
    },
}


def _franja_en_uso(franja_id):
    return (
        TurnoCedido.query.filter_by(franja_horaria_id=franja_id).count() > 0
        or TurnoAceptado.query.filter_by(franja_horaria_id=franja_id).count() > 0
    )


def aplicar_plantilla(grupo, plantilla_id):
    if plantilla_id not in PLANTILLAS:
        raise ValueError(f"Plantilla no válida: {plantilla_id}")

    franjas_info = {
        nombre: (inicio, fin)
        for nombre, inicio, fin in PLANTILLAS[plantilla_id]["franjas"]
    }

    existentes = FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo.id).all()
    for franja in existentes:
        if franja.nombre in franjas_info:
            franja.hora_inicio, franja.hora_fin = franjas_info[franja.nombre]
        elif not _franja_en_uso(franja.id):
            db.session.delete(franja)

    db.session.flush()

    existentes_nombres = {
        f.nombre
        for f in FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo.id).all()
    }
    for nombre, inicio, fin in PLANTILLAS[plantilla_id]["franjas"]:
        if nombre not in existentes_nombres:
            db.session.add(FranjaHoraria(
                nombre=nombre,
                hora_inicio=inicio,
                hora_fin=fin,
                grupo_intercambio_id=grupo.id,
            ))


def agregar_franja(grupo, nombre, hora_inicio, hora_fin):
    nombre = nombre.strip()
    if FranjaHoraria.query.filter_by(grupo_intercambio_id=grupo.id, nombre=nombre).first():
        raise ValueError(f"Ya existe un turno con el nombre «{nombre}».")
    franja = FranjaHoraria(
        nombre=nombre,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
        grupo_intercambio_id=grupo.id,
    )
    db.session.add(franja)
    return franja


def eliminar_franja(franja_id, grupo_id):
    franja = FranjaHoraria.query.filter_by(id=franja_id, grupo_intercambio_id=grupo_id).first_or_404()
    if _franja_en_uso(franja.id):
        raise ValueError("Este turno tiene publicaciones asociadas y no se puede eliminar.")
    db.session.delete(franja)
    return franja
