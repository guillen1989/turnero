from flask_babel import _

from app.models import Categoria, Ciudad, Hospital, Pais, Provincia, Unidad

_OPCION_NUEVA_CATEGORIA = 0


def _choices_cats():
    cats = Categoria.query.order_by(Categoria.nombre).all()
    choices = [(c.id, c.nombre) for c in cats]
    choices.append((_OPCION_NUEVA_CATEGORIA, _("— Añadir nueva categoría —")))
    return choices


def _choices_cats_unidad():
    cats = Categoria.query.order_by(Categoria.nombre).all()
    return [(0, _("— Sin categoría —"))] + [(c.id, c.nombre) for c in cats]


def _choices_hospitales():
    return [(h.id, h.nombre) for h in Hospital.query.order_by(Hospital.nombre).all()]


def _choices_paises():
    return [(p.id, p.nombre) for p in Pais.query.order_by(Pais.nombre).all()]


def _choices_provincias():
    return [(p.id, f"{p.nombre} ({p.pais.nombre})") for p in
            Provincia.query.join(Pais).order_by(Pais.nombre, Provincia.nombre).all()]


def _choices_ciudades():
    return [(c.id, f"{c.nombre} — {c.provincia.nombre}, {c.provincia.pais.nombre}") for c in
            Ciudad.query.join(Provincia).join(Pais).order_by(Pais.nombre, Provincia.nombre, Ciudad.nombre).all()]


def _choices_unidades():
    return [(u.id, f"{u.nombre} — {u.hospital.nombre}") for u in
            Unidad.query.join(Hospital).order_by(Hospital.nombre, Unidad.nombre).all()]
