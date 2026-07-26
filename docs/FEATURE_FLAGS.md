# Feature flags — plan de trabajo

## Contexto y decisión

`main` está actualmente ~50 commits por detrás de `staging` (167 archivos,
+24.700/−6.500 líneas). El objetivo es que `main` incorpore todo el
histórico de `staging` sin que eso obligue a exponer a los usuarios
funcionalidades que ya están desarrolladas pero aún no listas para
mostrarse (p. ej. por falta de prueba en producción, por decisión de
negocio de lanzarlas más adelante, o por rollout gradual a algunas
unidades antes que a todas).

**Decisión: feature flags**, en vez de:
- **Cherry-pick selectivo a `main`** — con 50 commits ya divergentes,
  mantener dos ramas con historiales parcialmente distintos solo acumula
  deuda de conflictos cada vez mayor; no resuelve el problema, lo pospone.
- **Ramas de feature de larga duración hasta completarse** — es
  básicamente el patrón que ya ha producido esta brecha de 50 commits; no
  escala y contradice el flujo de commits atómicos frecuentes que ya usa
  el proyecto (ver `CLAUDE.md`).
- **Feature flags** — desacoplan "código mergeado/desplegado" de
  "funcionalidad visible para el usuario". Permiten mergear con
  seguridad todo el código y decidir la visibilidad en runtime, sin
  bloquear la integración continua. Es el estándar de facto para este
  problema (trunk-based development / dark launches).

**Granularidad por unidad, además de global**: tiene sentido y además hay
un precedente idéntico ya en el código — `UnidadSupervisada` (tabla N:M
`usuario_id`+`unidad_id`, PK compuesta, ver `app/models/unidad_supervisada.py`)
resuelve exactamente el mismo problema de forma ("¿esta entidad tiene
acceso a esta unidad concreta?") para supervisoras multiunidad. Un
`FeatureFlagUnidad` (N:M `feature_flag_id`+`unidad_id`) sigue el mismo
patrón, ya idiomático en esta base de código. Se descarta guardar la
configuración como JSON en `Unidad`: no compone bien con un "global
on/off + lista de excepciones" y complica añadir una unidad nueva sin
tocar cada fila.

## Diseño

### Modelo de datos

```python
# app/models/feature_flag.py
class FeatureFlag(db.Model):
    __tablename__ = "feature_flag"

    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(80), unique=True, nullable=False)  # slug, p.ej. "hoja_cambio_papel"
    descripcion = db.Column(db.String(255), nullable=True)
    activo_global = db.Column(db.Boolean, nullable=False, default=False)

    unidades_habilitadas = db.relationship(
        "Unidad", secondary="feature_flag_unidad", backref="feature_flags_habilitados"
    )


# app/models/feature_flag_unidad.py
class FeatureFlagUnidad(db.Model):
    """N:M entre un flag y las unidades donde está habilitado aunque
    activo_global sea False. Mismo patrón que UnidadSupervisada."""

    __tablename__ = "feature_flag_unidad"

    feature_flag_id = db.Column(db.Integer, db.ForeignKey("feature_flag.id"), primary_key=True)
    unidad_id = db.Column(db.Integer, db.ForeignKey("unidad.id"), primary_key=True)
```

Ambas tablas son nuevas (sin filas previas), así que la migración es de
un solo paso — no aplica el patrón de tres pasos de `NOT NULL` de
`CLAUDE.md` (ese patrón es para columnas nuevas en tablas *existentes*
con filas).

### Servicio: `app/services/feature_flags.py`

Módulo puro, sin acoplarse a rutas ni plantillas (mismo principio de
separación de responsabilidades que el motor de matching):

```python
def feature_activa(clave: str, unidad: Unidad | None = None) -> bool:
    """True si el flag está activo globalmente, o si `unidad` está en su
    lista de unidades habilitadas. Si el flag no existe, False (fail
    closed: una funcionalidad sin flag registrado nunca se asume activa)."""

def crear_flag(clave: str, descripcion: str = "") -> FeatureFlag: ...
def activar_global(clave: str) -> None: ...
def desactivar_global(clave: str) -> None: ...
def habilitar_para_unidad(clave: str, unidad: Unidad) -> None: ...
def deshabilitar_para_unidad(clave: str, unidad: Unidad) -> None: ...
```

Sin capa de caché inicialmente (simplicidad de MVP): son consultas por
PK/índice único, baratas. Si en el futuro el volumen de comprobaciones
por request lo justifica, añadir caché entonces — no antes.

### Uso en rutas y plantillas

- Decorador para ocultar una ruta entera (404 si no está activa, no un
  mensaje "próximamente" que confirmaría que la funcionalidad existe):

  ```python
  @requiere_feature("hoja_cambio_papel")  # usa current_user.unidad implícitamente
  def registrar_papel():
      ...
  ```

- Context processor Jinja (`feature_activa` disponible directamente en
  plantillas) para ocultar condicionalmente enlaces de navegación,
  botones, secciones:

  ```jinja
  {% if feature_activa('hoja_cambio_papel') %}
    <a href="{{ url_for('documento_cambio.registrar_papel') }}">...</a>
  {% endif %}
  ```

### Administración

Nueva página `/admin/feature-flags` (blueprint `admin`, reutilizando
`admin_required` ya existente en `app/routes/admin/__init__.py`):
- Listado de flags con su `clave`, `descripcion` y toggle de
  `activo_global`.
- Por cada flag, un `<select multiple>` de unidades habilitadas —mismo
  patrón visual y de formulario que `unidades_supervisadas` en
  `usuario_form.html` (Paso 5 de la fase de supervisoras multiunidad,
  ver `PROGRESS.md`)—, respaldado por
  `sincronizar_unidades_habilitadas(flag, unidad_ids)` (mismo patrón que
  `sincronizar_unidades_supervisadas`).

No hace falta UI para *crear* flags nuevos desde el admin en esta fase —
se crean vía migración/seed cuando se introduce cada funcionalidad
encadenada a un flag (ver Fase B). Añadir un formulario de alta es
trabajo futuro si hace falta, no ahora.

## Convención de nombres de flag

Un flag por área funcional visible para el usuario, no un flag por PR ni
por commit. Slug en `snake_case`, descriptivo del área
(`hoja_cambio_papel`, `planilla_supervision_multiunidad`, etc.), nunca
del número de ticket o de la fecha.

## Plan de trabajo (pasos, TDD, un commit por paso)

### Fase A — Infraestructura de feature flags (agnóstica de features concretas)

1. Modelo `FeatureFlag` + test (`tests/test_models_feature_flag.py`).
2. Modelo `FeatureFlagUnidad` (N:M) + test.
3. Migración Alembic (`flask db migrate`, nunca a mano) — un solo head,
   verificar con `flask db heads`.
4. Servicio `app/services/feature_flags.py` con `feature_activa` +
   funciones de gestión + tests (incluyendo el caso "flag inexistente →
   False", "activo_global=True gana aunque la unidad no esté en la
   lista", "unidad en la lista gana aunque activo_global sea False").
5. Decorador `requiere_feature` (rutas) + context processor
   `feature_activa` (plantillas) + tests de integración (404 en ruta
   oculta, enlace ausente en plantilla).
6. UI admin `/admin/feature-flags` (listado + toggle global + multi-select
   de unidades) + tests de ruta, reusando `_choices_unidades()` ya
   existente en `app/routes/admin/helpers.py`.

Al terminar la Fase A, la infraestructura de flags está lista pero no
oculta nada todavía (ninguna ruta existente la usa aún).

### Fase B — Aplicar flags a las funcionalidades de `staging` pendientes de exponer

**Requiere decisión explícita del usuario**: esta fase no se puede
planificar del todo de antemano porque implica decidir *qué*
funcionalidades concretas de las últimas semanas de `staging` deben
quedar ocultas al mergear a `main`. Candidatas visibles en `PROGRESS.md`
a validar con el usuario antes de tocar código (lista no vinculante,
solo punto de partida de la conversación):
- Hoja de cambios digital / registro en papel (`documento_cambio`).
- Planilla de supervisión multiunidad.
- Importación de planillas.
- Cadenas de intercambio a 3/4 bandas.

Por cada funcionalidad que el usuario confirme que debe quedar oculta:
un paso = crear su flag (con `activo_global=False` por defecto) +
envolver sus rutas de entrada y enlaces de navegación con
`requiere_feature`/`feature_activa`. Un commit por funcionalidad, no un
commit gigante para todas.

### Fase C — Merge `staging` → `main`

Una vez las funcionalidades sensibles están detrás de flags apagados por
defecto, el merge de `staging` a `main` deja de tener riesgo de exponer
nada no deseado: todo lo nuevo aparece apagado hasta que alguien lo active
desde `/admin/feature-flags`, global o unidad a unidad.

## Instrucciones de ejecución (obligatorias)

Este trabajo se hace en un **worktree aparte, creado a partir de la rama
`staging`** (no de `main`) — `staging` es la rama de integración activa
del proyecto, y es contra la que se abren todos los PRs según
`CLAUDE.md`/`PROGRESS.md`. El resultado se entrega como **pull request
contra `staging`**, nunca contra `main` ni directamente empujado a
ninguna de las dos.

Pasos:
1. Crear el worktree desde `staging` (no desde `main`, que va por detrás):
   ```bash
   git fetch origin staging
   git worktree add ../turnero-feature-flags -b feature/feature-flags origin/staging
   ```
2. Desarrollar la Fase A completa siguiendo TDD y el ciclo de un commit
   por paso descrito en `CLAUDE.md` (test → implementación mínima →
   refactor → `PROGRESS.md` actualizado → commit).
3. Antes de cada commit que toque migraciones: `flask db heads` debe dar
   exactamente `1 (head)`.
4. Ejecutar tests con `pytest --testmon` en el día a día; antes de abrir
   el PR, una pasada completa de la suite para confianza total.
5. Push de la rama y apertura de PR **contra `staging`**:
   ```bash
   git push -u origin feature/feature-flags
   gh pr create --base staging --draft \
     --title "feat: infraestructura de feature flags (global + por unidad)" \
     --body "..."
   ```
6. La Fase B (aplicar flags a funcionalidades concretas) se aborda en
   PR(s) separados, posteriores, uno por cada funcionalidad que el
   usuario confirme — no se mezcla con el PR de infraestructura de la
   Fase A.
7. La Fase C (merge `staging` → `main`) es una decisión y una acción del
   usuario, no algo que se automatice como parte de este plan.
