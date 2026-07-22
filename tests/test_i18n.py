import ast
from pathlib import Path

from flask_babel import get_locale

RUTAS_DIR = Path(__file__).resolve().parent.parent / "app" / "routes"
FUNCIONES_TRADUCTORAS = {"_", "gettext", "lazy_gettext", "ngettext"}


def test_default_locale_is_spanish(app):
    with app.test_request_context("/"):
        locale = get_locale()
        assert str(locale) == "es"


def _es_llamada_traductora(nodo):
    return (
        isinstance(nodo, ast.Call)
        and isinstance(nodo.func, ast.Name)
        and nodo.func.id in FUNCIONES_TRADUCTORAS
    )


def _mensajes_flash_sin_traducir(archivo):
    """Líneas de un archivo de rutas donde flash() recibe un literal (str o
    f-string) en lugar de pasar por _()/gettext(); ese texto queda fijo en
    español y nunca se traduce (ver CLAUDE.md, sección de i18n)."""
    arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
    hallazgos = []
    for nodo in ast.walk(arbol):
        if not (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and nodo.func.id == "flash"):
            continue
        if not nodo.args:
            continue
        mensaje = nodo.args[0]
        if _es_llamada_traductora(mensaje):
            continue
        if isinstance(mensaje, (ast.Constant, ast.JoinedStr)):
            hallazgos.append(nodo.lineno)
    return hallazgos


def test_flash_no_usa_literales_sin_traducir():
    problemas = {}
    for archivo in sorted(RUTAS_DIR.glob("*.py")):
        hallazgos = _mensajes_flash_sin_traducir(archivo)
        if hallazgos:
            problemas[archivo.name] = hallazgos
    assert not problemas, (
        "flash() con mensaje literal sin envolver en _()/gettext() (i18n "
        f"obligatorio, ver CLAUDE.md): {problemas}"
    )


def _importa_gettext_como_guion_bajo(arbol):
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module == "flask_babel":
            for alias in nodo.names:
                if (alias.asname or alias.name) == "_":
                    return True
    return False


def _nombres_de(objetivo):
    return {n.id for n in ast.walk(objetivo) if isinstance(n, ast.Name)}


def _reasigna_guion_bajo(func_def):
    """True si el cuerpo de la función reasigna '_' (p.ej. desempaquetar una
    tupla con '_, resto = ...'), lo que la convierte en variable local y
    oculta el _() de gettext importado a nivel de módulo para el resto de
    la función (ver CLAUDE.md, sección de i18n)."""
    encontrado = False

    def visitar(nodo):
        nonlocal encontrado
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            return
        if isinstance(nodo, ast.Assign):
            for objetivo in nodo.targets:
                if "_" in _nombres_de(objetivo):
                    encontrado = True
        elif isinstance(nodo, (ast.For, ast.AsyncFor)):
            if "_" in _nombres_de(nodo.target):
                encontrado = True
        elif isinstance(nodo, (ast.With, ast.AsyncWith)):
            for item in nodo.items:
                if item.optional_vars and "_" in _nombres_de(item.optional_vars):
                    encontrado = True
        for hijo in ast.iter_child_nodes(nodo):
            visitar(hijo)

    for stmt in func_def.body:
        visitar(stmt)
    return encontrado


def _funciones_que_reasignan_guion_bajo(archivo):
    arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
    if not _importa_gettext_como_guion_bajo(arbol):
        return []
    return [
        (nodo.name, nodo.lineno)
        for nodo in ast.walk(arbol)
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)) and _reasigna_guion_bajo(nodo)
    ]


def test_no_se_reasigna_guion_bajo_en_archivos_con_gettext():
    problemas = {}
    for archivo in sorted(RUTAS_DIR.glob("*.py")):
        hallazgos = _funciones_que_reasignan_guion_bajo(archivo)
        if hallazgos:
            problemas[archivo.name] = hallazgos
    assert not problemas, (
        "Una función reasigna '_' (p.ej. '_, resto = calendar.monthrange(...)') "
        "en un archivo que importa '_' de flask_babel para gettext; eso la "
        "convierte en variable local y rompe la traducción en esa función. "
        f"Usa un nombre descriptivo para la variable descartada: {problemas}"
    )
