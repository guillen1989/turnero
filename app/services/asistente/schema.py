import re

from pydantic import BaseModel, field_validator

from app.models.publicacion import TIPOS_PUBLICACION

_PATRON_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class TurnoPropuesto(BaseModel):
    fecha: str | None = None
    franja: str | None = None

    @field_validator("fecha")
    @classmethod
    def _fecha_iso(cls, valor):
        if valor is None:
            return valor
        if not _PATRON_FECHA.match(valor):
            raise ValueError(f"fecha '{valor}' no tiene formato ISO (YYYY-MM-DD)")
        return valor


class PropuestaPublicacion(BaseModel):
    tipo: str
    cedidos: list[TurnoPropuesto] = []
    aceptados: list[TurnoPropuesto] = []
    campos_faltantes: list[str] = []

    @field_validator("tipo")
    @classmethod
    def _tipo_valido(cls, valor):
        if valor not in TIPOS_PUBLICACION:
            raise ValueError(f"tipo '{valor}' no está en TIPOS_PUBLICACION")
        return valor
