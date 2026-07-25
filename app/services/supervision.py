def unidades_supervisadas_de(usuario):
    return sorted(usuario.unidades_supervisadas, key=lambda unidad: unidad.nombre)


def puede_supervisar(usuario, unidad):
    return unidad in usuario.unidades_supervisadas
