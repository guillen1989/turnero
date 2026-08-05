# Fix: Internal Server Error al eliminar unidades/hospitales

## Contexto del bug

En producción, al intentar eliminar la unidad **UCI** (categoría TCAE, hospital de
demostración, `unidad.id = 27`) desde `/admin/unidades/27/eliminar`, la app devuelve
Internal Server Error.

**Traceback real (Railway, producción, 2026-08-05 07:00:35):**

```
AssertionError: Dependency rule on column 'unidad.id' tried to blank-out primary
key column 'usuario_unidad.unidad_id' on instance '<UsuarioUnidad at 0x7fb22821ad50>'
```

**Causa raíz:** `unidad_eliminar` (`app/routes/admin/geografia.py:251-262`) solo
comprueba `u.usuarios.count()` (relación *primaria* `Usuario.unidad_id`) antes de
borrar. No comprueba las membresías *secundarias* en `usuario_unidad`
(`UsuarioUnidad`, tabla con **primary key compuesta** `usuario_id + unidad_id`).

Cuando SQLAlchemy borra la `Unidad`, intenta desvincular las filas de
`usuario_unidad` poniendo `unidad_id = NULL` (comportamiento por defecto sin
`cascade`), pero como `unidad_id` es parte de la clave primaria compuesta, no se
puede poner a NULL → `AssertionError` → 500.

**Confirmado en la BD de producción:** `unidad.id = 27` tiene exactamente 1 fila en
`usuario_unidad` (`usuario_id=201, unidad_id=27, categoria_id=2`) y 0 filas en el
resto de tablas relacionadas con `unidad_id` (`unidad_supervisada`,
`feature_flag_unidad`, `publicacion_cambio`, `documento_cambio`, `notificacion`,
`estado_dia_planilla`, `turno_planilla`, `planilla_mes`, `saliente_dia`, `nota_dia`,
`mapeo_trabajador_planilla`). Esa única fila de `usuario_unidad` es la que rompe el
`commit()`.

**El mismo patrón de bug existe en `hospital_eliminar`** (línea 192-208): itera las
unidades del hospital, comprueba solo `u.usuarios.count()`, y borra cada unidad con
`db.session.delete(u)` — el mismo `AssertionError` puede saltar ahí si alguna unidad
del hospital tiene membresías secundarias, o cualquier otra fila huérfana en las
tablas listadas abajo.

## Inventario de todo lo que referencia `unidad.id`

Tablas con `unidad_id` como FK, agrupadas por cómo debe tratarse en un borrado:

**A. Composite PK — mismo `AssertionError` que ya vimos si hay filas (requieren
`cascade="all, delete-orphan"` en la relación desde `Unidad`, son solo metadatos de
asociación, no datos de negocio que se puedan "perder"):**
- `usuario_unidad` (`UsuarioUnidad`) — membresía secundaria de un usuario en otra unidad.
- `unidad_supervisada` (`UnidadSupervisada`) — unidades que supervisa una supervisora.
- `feature_flag_unidad` (`FeatureFlagUnidad`) — feature flags activados por unidad.

**B. FK nullable, sin relación ORM declarada — no rompen con `AssertionError`
(SQLAlchemy no las gestiona vía ORM), pero dejan `unidad_id` colgante apuntando a un
id borrado si no se limpian explícitamente:**
- `audit_eliminacion` (`AuditEliminacion.unidad_id`, `nullable=True`).

**C. FK `NOT NULL`, sin relación ORM declarada desde `Unidad` — son datos de negocio
reales (turnos, planillas, publicaciones, documentos, notificaciones). Si existen,
**no se deben borrar en cascada silenciosamente**: hay que bloquear el borrado de la
unidad y decírselo al admin, igual que ya se hace con `usuarios.count()`:**
- `documento_cambio` (`DocumentoCambio.unidad_id`)
- `notificacion` (`Notificacion.unidad_id`)
- `estado_dia_planilla` (`EstadoDiaPlanilla.unidad_id`)
- `turno_planilla` (`TurnoPlanilla.unidad_id`)
- `planilla_mes` (`PlanillaMes.unidad_id`)
- `saliente_dia` (`SalienteDia.unidad_id`)
- `nota_dia` (`NotaDia.unidad_id`)
- `mapeo_trabajador_planilla` (`MapeoTrabajadorPlanilla.unidad_id`)
- `publicacion_cambio` (`PublicacionCambio.unidad_id`)

**D. Ya cubierta hoy:**
- `usuario.unidad_id` (`nullable=False`) — cubierto por el guard existente
  `u.usuarios.count() > 0`.

## Plan de trabajo

Cada paso es independiente y termina en un commit (TDD: test rojo → implementación →
verde). Ejecutar en sesiones sucesivas, en orden.

- [ ] **Paso 1 — Test que reproduce el bug real.**
  Añade un test de integración (en el módulo de tests de `admin/geografia` o donde
  vivan los tests de borrado de unidades) que reproduzca exactamente el escenario de
  producción: una `Unidad` sin usuarios "primarios" (`Usuario.unidad_id`) pero con una
  fila en `usuario_unidad` (membresía secundaria). Llama a
  `POST /admin/unidades/<id>/eliminar` y comprueba que **no** lanza `AssertionError`
  ni devuelve 500 — de momento el test puede esperar simplemente "no debe reventar"
  (se decide en el paso 2 si el comportamiento correcto es bloquear o limpiar). Este
  test debe fallar en rojo contra el código actual, confirmando que reproduce el bug.

- [x] **Paso 2 — Extender el guard de `unidad_eliminar` a las membresías secundarias.**
  Decisión de negocio: una unidad con usuarios vinculados (aunque sea solo como
  membresía secundaria vía `usuario_unidad`, o como unidad supervisada vía
  `unidad_supervisada`) **no se debe poder eliminar sin más** — igual que ya ocurre
  con `usuarios.count()`. Añade a `unidad_eliminar`:
  ```python
  if u.membresias_unidad.count() > 0 or u.supervisoras.count() > 0:  # usar los nombres reales de las relaciones
      flash(_("No se puede eliminar: la unidad tiene usuarios asociados (membresía secundaria o supervisión)."), "danger")
      return redirect(url_for("admin.unidades"))
  ```
  Ajusta el test del paso 1 para que espere el `flash` de bloqueo y que la unidad
  siga existiendo tras el POST. Verifica los tests con `pytest --testmon`.

- [ ] **Paso 3 — Guard para el resto de datos de negocio (grupo C).**
  Añade comprobaciones equivalentes para `documento_cambio`, `notificacion`,
  `estado_dia_planilla`, `turno_planilla`, `planilla_mes`, `saliente_dia`,
  `nota_dia`, `mapeo_trabajador_planilla`, `publicacion_cambio` — todas con
  `unidad_id NOT NULL` y sin relación ORM desde `Unidad`, así que hay que consultarlas
  directamente (p. ej. `db.session.query(Modelo).filter_by(unidad_id=u.id).first()`).
  Si cualquiera tiene filas, bloquea el borrado con un mensaje claro (puede ser un
  único mensaje genérico "la unidad tiene historial asociado" en vez de listar cada
  tabla, para no complicar el UI). Escribe primero el test en rojo para al menos uno
  de estos casos (p. ej. `publicacion_cambio`), luego generaliza la implementación,
  luego cubre el resto con tests parametrizados si aporta claridad sin over-engineering.

- [ ] **Paso 4 — Limpiar `audit_eliminacion` (grupo B) al eliminar.**
  Como esta tabla es un log de auditoría con `unidad_id` nullable y sin relación ORM,
  al eliminar la unidad hay que poner `unidad_id = NULL` en sus filas relacionadas
  antes del `delete` (no bloquea el borrado, solo evita dejar una FK colgante).
  Ejemplo: `db.session.query(AuditEliminacion).filter_by(unidad_id=u.id).update({"unidad_id": None})`.
  Test: crea una fila de `AuditEliminacion` apuntando a la unidad, bórrala, comprueba
  que la fila sigue existiendo con `unidad_id IS NULL`.

- [ ] **Paso 5 — Cascade correcto para las tablas de solo-asociación (grupo A).**
  En `app/models/unidad.py`, añade `cascade="all, delete-orphan"` a las relaciones
  `membresias_unidad` y `supervisoras` (y crea la relación equivalente para
  `feature_flag_unidad` si no existe) para que, en los casos donde SÍ se permite el
  borrado (grupo A no bloquea nada per se — se bloquea en el paso 2 por la relación
  con usuarios reales, pero `feature_flag_unidad` es pura configuración y no debería
  bloquear), SQLAlchemy borre esas filas en cascada en vez de intentar poner a NULL
  una columna de la PK compuesta. Esto es lo que corrige el `AssertionError` de raíz
  a nivel de ORM (defensa en profundidad además del guard del paso 2/3).
  Test: unidad con solo una fila en `feature_flag_unidad` (sin usuarios, sin
  membresías) → el borrado debe tener éxito y la fila de `feature_flag_unidad` debe
  desaparecer.

- [ ] **Paso 6 — Aplicar el mismo fix a `hospital_eliminar`.**
  `hospital_eliminar` (`app/routes/admin/geografia.py:192-208`) tiene el mismo bug:
  itera las unidades del hospital comprobando solo `u.usuarios.count()`. Extrae los
  guards de los pasos 2-3 a una función auxiliar reutilizable (p. ej.
  `_unidad_tiene_datos_asociados(u)` en el mismo módulo o en `helpers.py`) y úsala
  tanto en `unidad_eliminar` como en el bucle de `hospital_eliminar`. Test: hospital
  con una única unidad que tiene una membresía secundaria → el borrado del hospital
  debe bloquearse con el mismo mensaje, y ni el hospital ni la unidad deben borrarse.

- [ ] **Paso 7 — Verificación completa y despliegue.**
  - Ejecuta la suite completa de tests del módulo admin (no solo `--testmon`) para
    confirmar que no hay regresiones en `pais_eliminar` / `provincia_eliminar` /
    `ciudad_eliminar` (mismo patrón de guard, no deberían verse afectados).
  - Crea el PR contra `staging` con estos commits.
  - Una vez fusionado y desplegado a producción: la unidad UCI/TCAE (`id=27`) seguirá
    bloqueada para borrado (por la membresía secundaria del usuario 201 en
    `usuario_unidad`), pero ahora con un mensaje claro en vez de un 500. Si de verdad
    se quiere eliminar esa unidad de demo, hay que decidir antes si esa membresía
    secundaria se quita a mano (vía UI de gestión de membresías, si existe) o se
    documenta como intencional.

## Notas / decisiones pendientes de confirmar con el usuario

- ¿Bloquear el borrado cuando hay membresía secundaria (paso 2) es el comportamiento
  deseado, o se prefiere que el borrado de la unidad limpie automáticamente esa
  membresía (cascade silencioso) sin bloquear? Se ha planteado el plan asumiendo
  "bloquear" por consistencia con el guard ya existente de `usuarios.count()`, pero
  conviene confirmarlo antes del paso 2.
- El mensaje de error de los pasos 2-3 se ha planteado como genérico ("la unidad
  tiene datos asociados") para no acoplar el UI a la lista interna de tablas; si se
  prefiere un mensaje más específico por tipo de dato, ajustar en el paso
  correspondiente.
