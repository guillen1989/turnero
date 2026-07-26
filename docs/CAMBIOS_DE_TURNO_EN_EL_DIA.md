# Cambios de Turno en el Día — Plan de Trabajo

## Descripción general

Este documento describe el plan de desarrollo para extender el sistema de cambios de turno actual, permitiendo que los usuarios intercambien turnos **dentro del mismo día laboral** (misma fecha, pero entre franjas horarias diferentes).

**Ejemplo:** Ana tiene turno de mañana el 25/06 y quiere cambiar a turno de tarde del mismo día. Pedro tiene turno de tarde el 25/06 y quiere cambiar a turno de mañana del mismo día. El sistema detecta la coincidencia y cierra el match.

### Contexto de arquitectura

El sistema actual ya está preparado para esto:
- El modelo `PublicacionCambio` tiene un campo `tipo` que incluye el valor `"cambio_dia"` (junto a `"cambio"`, `"regalo"`, `"peticion"`, `"junte"`).
- La infraestructura de matching, hojas de cambio digital, volcado a planilla y supervisión funciona de forma agnóstica al tipo de cambio.
- No hay restricciones en la BD que impidan que un usuario publique turnos del mismo día.

### Diferencias con cambios normales

Un cambio de turno en el día es técnicamente idéntico a un cambio ordinario, con las siguientes particularidades:

1. **Validación adicional:** antes de permitir crear una publicación de tipo `cambio_dia`, verificar que todos los turnos cedidos y aceptados sean de **la misma fecha** (violaría la definición de "cambio en el día").
2. **UI diferenciada:** la interfaz para publicar un cambio en el día debe ser distinta (visual + flujo), para que sea intuitivo que "estoy cambiando de turno dentro del mismo día".
3. **Motivos:** es un flujo común en hospitales (alguien necesita librar un turno y piensa en sus compañeros de ese mismo día), justificando un tipo distinto con tratamiento específico en la app.

### Diseño

No requiere cambios en el modelo de datos. Requiere cambios en:

1. **Rutas (`app/routes/`):** nuevas rutas para crear publicaciones de tipo `cambio_dia`, o modificar las existentes para soportar este tipo.
2. **Servicios (`app/services/`):** validación adicional al crear publicaciones de tipo `cambio_dia`.
3. **Templates y frontend:** interfaz específica para crear cambios en el día.
4. **Tests:** cobertura del nuevo tipo de publicación y su flujo completo (matching, confirmación, volcado a planilla).

---

## Plan de trabajo por fases

### Fase 1: Preparación y validación

#### Paso 1.1: Actualizar la especificación
- **Archivo:** `especificacion-app-cambio-turnos.md`
- **Cambios:**
  - Añadir una sección en "Reglas de negocio" describiendo cambios de turno en el día.
  - Actualizar el modelo de dominio para incluir que `PublicacionDeCambio` puede ser de tipo `cambio_dia`.
  - Añadir un nuevo CU (p. ej., CU7bis) describiendo el flujo de crear un cambio en el día.
- **Tests:** ninguno (actualización de documentación).
- **Commit:** `chore: documenta cambios de turno en el día en la especificación`

#### Paso 1.2: Tests TDD del validador de cambio_dia
- **Archivo:** `tests/test_cambio_dia_validacion.py` (nuevo)
- **Contenido:**
  - Test que verifica que al crear una publicación de tipo `cambio_dia` con turnos de diferentes fechas, falla la validación.
  - Test que verifica que al crear una publicación de tipo `cambio_dia` con turnos de la misma fecha, pasa la validación.
  - Tests de edge cases (fecha en el pasado, franja_horaria no existe, usuario no pertenece al grupo de intercambio, etc.).
- **Código de producción:** stub del servicio que será completado en Paso 1.3.
- **Tests:** todos los tests del paso 1.2 pasan (verde).
- **Commit:** `test: añade tests de validación para cambio_dia`

#### Paso 1.3: Implementar validador de cambio_dia
- **Archivo:** `app/services/publicaciones.py` (modificar) o crear `app/services/validacion_cambio_dia.py` si es más de 50 líneas.
- **Contenido:**
  - Función `validar_publicacion_cambio_dia(publicacion)` que asegura que todos los turnos cedidos y aceptados sean de la misma fecha.
  - Integración con la creación de publicaciones en `app/routes/publicaciones.py` o `app/routes/documento_cambio.py`.
- **Tests:** todos los tests del paso 1.2 pasan.
- **Commit:** `feat: implementa validación de cambio_dia en publicaciones`

---

### Fase 2: Interfaz para crear cambios en el día

#### Paso 2.1: Tests de flujo en la UI
- **Archivo:** `tests/test_ruta_crear_cambio_dia.py` (nuevo)
- **Contenido:**
  - Test POST a una nueva ruta `POST /cambio-dia/nueva` con datos válidos (usuario, fecha, franja_cedida, franja_aceptada).
  - Test que verifica que se crea una `PublicacionCambio` de tipo `cambio_dia`.
  - Test que verifica validación de entrada (campos requeridos, fechas válidas, etc.).
  - Test que verifica que solo usuarios autenticados pueden crear.
  - Test que la publicación se puede ver en el listado de publicaciones del usuario.
- **Código de producción:** stubs de las rutas.
- **Tests:** tests fallan (rojo).
- **Commit:** `test: tests para ruta POST /cambio-dia/nueva`

#### Paso 2.2: Implementar ruta de creación
- **Archivo:** `app/routes/documento_cambio.py` (modificar) o crear `app/routes/cambio_dia.py`.
- **Contenido:**
  - GET `/cambio-dia/nueva`: renderiza formulario para crear un cambio en el día (selector de fecha, selección de turno a ceder, selección de turno a aceptar).
  - POST `/cambio-dia/nueva`: procesa el formulario, crea la `PublicacionCambio` de tipo `cambio_dia` y redirige al listado.
  - Verificaciones: validación con `validar_publicacion_cambio_dia()`, pertenencia del usuario a la unidad, compatibilidad de franjas (no puede ceder y aceptar la misma franja).
- **Tests:** tests del paso 2.1 pasan (verde).
- **Commit:** `feat: ruta POST /cambio-dia/nueva para crear cambios en el día`

#### Paso 2.3: Template para formulario de cambio_dia
- **Archivo:** `app/templates/cambio_dia/nueva.html` (nuevo)
- **Contenido:**
  - Formulario similar a `documento_cambio/nuevo.html` pero simplificado: fecha única, dos selectores de franja (cede/acepta).
  - Mensaje explicativo: "Cambiar de turno dentro del mismo día".
  - Selector de fecha (solo fechas futuras).
  - Dos dropdowns de franjas (rellenados dinámicamente al cambiar la fecha — JavaScript).
  - Botón "Crear cambio en el día".
- **Tests:** ninguno (template estático).
- **Commit:** `feat: template para crear cambio_dia`

---

### Fase 3: Matching y lógica de negocio

#### Paso 3.1: Tests de matching con cambio_dia
- **Archivo:** `tests/test_matching_cambio_dia.py` (nuevo)
- **Contenido:**
  - Test que al crear dos publicaciones de tipo `cambio_dia` que se encajan (Ana cede mañana acepta tarde, Pedro cede tarde acepta mañana, mismo día), el motor de matching las detecta y crea un `MatchCambio` de tipo `directo_2`.
  - Test que verifica que las publicaciones implicadas quedan en estado `parcialmente_resuelta` o `confirmada` según la regla 2bis.
  - Test que el rechazo de un match vuelve las publicaciones a estado `abierta`.
  - Test de confirmación de match (ambas partes confirman).
  - Test de edge cases: ¿qué pasa si alguien publica un cambio en el día de una fecha que ya pasó? (debe caducar inmediatamente).
- **Código de producción:** el servicio de matching se asume ya funciona (no requiere cambios, es agnóstico al tipo de cambio).
- **Tests:** algunos fallan si la caducidad no revisa tipo cambio_dia, otros pasan.
- **Commit:** `test: tests de matching para cambio_dia`

#### Paso 3.2: Tests de volcado a planilla con cambio_dia
- **Archivo:** `tests/test_volcado_cambio_dia.py` (nuevo)
- **Contenido:**
  - Test que al confirmar un match de tipo `cambio_dia` y luego volcarlo, la planilla del usuario refleja ambos cambios en la misma fecha.
  - Test que las notas en la planilla (`NotaDia.texto`) registran correctamente ambos cambios.
  - Test de reversa (si el documento es anulado por la supervisora, el volcado se deshace).
- **Código de producción:** el servicio `volcar_cambios.py` se asume ya funciona (agnóstico al tipo).
- **Tests:** pasan sin cambios en el código de producción (la lógica es la misma).
- **Commit:** `test: tests de volcado a planilla para cambio_dia`

#### Paso 3.3: Tests de hoja de cambio digital (documento_cambio) con cambio_dia
- **Archivo:** `tests/test_documento_cambio_dia.py` (nuevo)
- **Contenido:**
  - Test que se puede crear un `DocumentoCambio` manual para un cambio en el día (sin relación con match).
  - Test que la factibilidad se verifica correctamente (ambos implicados trabajan sus turnos cedidos y están libres para los aceptados).
  - Test que la supervisora puede autorizar/denegar el documento.
  - Test que al autorizar, el volcado a planilla es correcto.
- **Código de producción:** el servicio `documento_cambio.py` se asume funciona (agnóstico).
- **Tests:** pasan sin cambios en el código de producción.
- **Commit:** `test: tests de DocumentoCambio para cambio_dia`

---

### Fase 4: Integración con hojas de cambio digital

#### Paso 4.1: Permitir crear DocumentoCambio desde match cambio_dia
- **Archivo:** `app/services/documento_cambio.py` (modificar)
- **Contenido:**
  - La función `crear_documento_cambio_desde_match(match)` ya debería funcionar para matches de tipo `cambio_dia` sin cambios.
  - Verificar que los tests de Paso 3.3 lo confirmen.
- **Tests:** tests de Paso 3.3.
- **Commit:** no hay nuevo commit si no hay cambios; sino `feat: DocumentoCambio soporta cambio_dia`

#### Paso 4.2: Tests de supervisión multiunidad con cambio_dia
- **Archivo:** `tests/test_supervision_cambio_dia.py` (nuevo)
- **Contenido:**
  - Test que una supervisora ve cambios_dia creados en su unidad (o unidades de su alcance si supervisa varias).
  - Test que solo la supervisora de la unidad puede autorizar/denegar.
  - Test de anulación (supervisora anula un cambio ya autorizado).
  - Test de flujo completo: crear → firmas → supervisora autoriza → volcado.
- **Código de producción:** el servicio `supervision.py` ya debe funcionar (agnóstico).
- **Tests:** pasan sin cambios en el código de producción.
- **Commit:** `test: tests de supervisión para cambio_dia`

---

### Fase 5: Controles de factibilidad

#### Paso 5.1: Tests de factibilidad con cambio_dia
- **Archivo:** `tests/test_factibilidad_cambio_dia.py` (nuevo)
- **Contenido:**
  - Test que al crear un `DocumentoCambio` de tipo `cambio_dia`, la factibilidad se verifica correctamente (usuario trabaja el turno que cede y está libre para el que acepta, **el mismo día**).
  - Test que si un usuario cede un turno que no tiene en la planilla, la factibilidad es `no_factible`.
  - Test que si un usuario acepta un turno en el que ya trabaja, la factibilidad es `no_factible`.
- **Código de producción:** el servicio `factibilidad_documento_cambio.py` ya debería funcionar (agnóstico).
- **Tests:** pasan sin cambios en el código de producción.
- **Commit:** `test: tests de factibilidad para cambio_dia`

---

### Fase 6: Caducidad y limpiar automático

#### Paso 6.1: Tests de caducidad con cambio_dia
- **Archivo:** `tests/test_caducidad_cambio_dia.py` (nuevo)
- **Contenido:**
  - Test que una publicación de tipo `cambio_dia` para una fecha pasada se marca como `caducada` automáticamente (incluso si se acaba de crear).
  - Test que el volcado de cambios caducados no ocurre (o se evita).
  - Test de limpieza automática de sintéticas caducadas (si existen).
- **Código de producción:** el servicio `caducidad.py` ya debería funcionar (agnóstico).
- **Tests:** pasan sin cambios en el código de producción.
- **Commit:** `test: tests de caducidad para cambio_dia`

---

### Fase 7: Integración en UI y panel de usuario

#### Paso 7.1: Tests de visibilidad en el dashboard
- **Archivo:** `tests/test_dashboard_cambio_dia.py` (nuevo)
- **Contenido:**
  - Test que un usuario ve sus propias publicaciones de tipo `cambio_dia` en su dashboard.
  - Test que un usuario ve potenciales matches de tipo `cambio_dia` de otros usuarios compatibles en el buscador.
  - Test que al confirmar un match, desaparece del buscador de ambos usuarios.
- **Código de producción:** templates/rutas del dashboard ya deben funcionar (agnósticos).
- **Tests:** pasan sin cambios en el código de producción.
- **Commit:** `test: tests de visibilidad en dashboard para cambio_dia`

#### Paso 7.2: Actualizar template de listado de cambios
- **Archivo:** `app/templates/documento_cambio/lista.html` o similar (modificar).
- **Contenido:**
  - Mostrar los cambios_dia en un listado distinto (o con un badge visual indicando "cambio en el día").
  - Incluir link a crear nuevo cambio_dia.
- **Tests:** ninguno (template estático).
- **Commit:** `feat: actualiza listado para mostrar cambios_dia`

---

### Fase 8: Tests de integración y UAT

#### Paso 8.1: Test de flujo completo (e2e)
- **Archivo:** `tests/test_e2e_cambio_dia.py` (nuevo)
- **Contenido:**
  - Test que simula el flujo completo:
    1. Usuario A crea publicación cambio_dia (cede mañana 25/06, acepta tarde 25/06).
    2. Usuario B (misma unidad, categoría) crea publicación cambio_dia (cede tarde 25/06, acepta mañana 25/06).
    3. Motor de matching detecta y crea un match.
    4. A y B reciben notificación.
    5. A confirma match.
    6. B confirma match.
    7. Match pasa a `confirmado_total`.
    8. A y B volcados a sus planillas.
    9. Ambos ven sus cambios reflejados en la planilla.
- **Código de producción:** ya debería estar todo en su lugar.
- **Tests:** pasan.
- **Commit:** `test: test e2e para flujo completo de cambio_dia`

#### Paso 8.2: Test de documento_cambio con cambio_dia (flujo alternativo sin matching)
- **Archivo:** `tests/test_e2e_documento_cambio_dia.py` (nuevo)
- **Contenido:**
  - Test que dos usuarios pueden crear manualmente un `DocumentoCambio` de cambio_dia (sin publicaciones ni matching automático):
    1. Usuario A inicia un documento_cambio para cambio_dia con usuario B.
    2. A rellena los datos (fecha, turno_cede, turno_recibe).
    3. A firma.
    4. B firma (desde la app o desde la link enviada por email).
    5. Supervisora autoriza.
    6. Cambio se vuelca a ambas planillas.
- **Código de producción:** ya debería estar todo en su lugar.
- **Tests:** pasan.
- **Commit:** `test: test e2e para documento_cambio de cambio_dia`

#### Paso 8.3: Test de incompatibilidades (casos de rechazo)
- **Archivo:** `tests/test_incompatibilidades_cambio_dia.py` (nuevo)
- **Contenido:**
  - Test que dos usuarios de categorías diferentes NO pueden cerrar un cambio_dia.
  - Test que dos usuarios de unidades que no están en el mismo grupo de intercambio NO pueden cerrar.
  - Test que un usuario NO puede ceder y aceptar la misma franja.
  - Test que un usuario NO puede crear un cambio_dia para una fecha que ya pasó.
- **Código de producción:** validaciones ya existentes deberían cubrir esto.
- **Tests:** pasan.
- **Commit:** `test: tests de incompatibilidades para cambio_dia`

---

## Estructura de commits

Resumen de commits esperados (en orden de desarrollo):

1. ✅ `chore: documenta cambios de turno en el día en la especificación`
2. ✅ `test: añade tests de validación para cambio_dia`
3. ✅ `feat: implementa validación de cambio_dia en publicaciones`
4. ✅ `test: tests para ruta POST /cambio-dia/nueva`
5. ✅ `feat: ruta POST /cambio-dia/nueva para crear cambios en el día`
6. ✅ `feat: template para crear cambio_dia`
7. ✅ `test: tests de matching para cambio_dia`
8. ✅ `test: tests de volcado a planilla para cambio_dia`
9. ✅ `test: tests de DocumentoCambio para cambio_dia`
10. ✅ `test: tests de supervisión para cambio_dia`
11. ✅ `test: tests de factibilidad para cambio_dia`
12. ✅ `test: tests de caducidad para cambio_dia`
13. ✅ `test: tests de visibilidad en dashboard para cambio_dia`
14. ✅ `feat: actualiza listado para mostrar cambios_dia`
15. ✅ `test: test e2e para flujo completo de cambio_dia`
16. ✅ `test: test e2e para documento_cambio de cambio_dia`
17. ✅ `test: tests de incompatibilidades para cambio_dia`

---

## Consideraciones técnicas

### Reusabilidad de código existente

La mayoría del código existente **ya funciona** para `cambio_dia` porque:
- El motor de matching es agnóstico al tipo de cambio.
- El volcado a planilla es agnóstico al tipo de cambio.
- Las hojas de cambio digital (`DocumentoCambio`) son agnósticas al tipo.
- La factibilidad, supervisión y caducidad son agnósticas.

### Lo que sí requiere cambios

1. **Validación:** función nueva para asegurar que todos los turnos son de la misma fecha.
2. **UI:** formulario y ruta nuevos para crear cambios_dia de forma intuitiva.
3. **Tests:** cobertura nueva para el tipo `cambio_dia`.
4. **Documentación:** especificación y CLAUDE.md si aplica.

### Migración de BD

No se requiere. Los cambios_dia se almacenan en las mismas tablas (`PublicacionCambio`, `TurnoCedido`, `TurnoAceptado`, `DocumentoCambio`, etc.) con el campo `tipo` ya existente.

---

## Instrucciones para ejecutar el trabajo

### Configuración inicial

```bash
# 1. Crear una rama de trabajo a partir de staging
git checkout staging
git pull origin staging
git checkout -b feature/cambios-turno-en-el-dia

# 2. Crear un worktree aislado (recomendado para trabajo en paralelo)
git worktree add .claude/worktrees/cambio-dia feature/cambios-turno-en-el-dia
cd .claude/worktrees/cambio-dia

# 3. Verificar que el árbol está limpio
git status
```

### Desarrollo por pasos

Seguir la estructura de commits indicada arriba. Para cada paso:

```bash
# 1. Escribir los tests primero (rojo)
# 2. Implementar el código mínimo para que pasen (verde)
# 3. Refactorizar si aplica (refactor)
# 4. Ejecutar tests con testmon para validar
/anaconda3/bin/python3 -m pytest --testmon tests/

# 5. Hacer commit atómico
git add -A
git commit -m "tipo: descripción del cambio"

# 6. Actualizar PROGRESS.md (si es necesario)
# 7. Hacer commit de PROGRESS.md si cambió
```

### Después de completar todos los pasos

```bash
# 1. Verificar que todos los tests pasan
/anaconda3/bin/python3 -m pytest tests/ -x

# 2. Limpiar el worktree
cd ../..
git worktree remove .claude/worktrees/cambio-dia

# 3. Hacer push de la rama a origin
git push origin feature/cambios-turno-en-el-dia

# 4. Crear un PR draft contra staging
gh pr create --draft \
  --base staging \
  --title "feat: cambios de turno en el día" \
  --body "Amplía el sistema de hojas de cambios para soportar cambios de turno dentro del mismo día laboral.
  
  - Validación de que todos los turnos son de la misma fecha
  - Nueva ruta POST /cambio-dia/nueva para crear cambios en el día
  - Integración con matching automático
  - Volcado a planilla
  - Hojas de cambio digital (DocumentoCambio)
  - Tests e2e de flujo completo
  
  Cierra #XXX (si aplica)"

# 5. Esperar revisión y feedback
```

---

## Notas finales

- Este plan asume que el código existente no requiere cambios importantes. Si durante el desarrollo se descubren issues con el matching, volcado o factibilidad, actualizar este documento.
- Los tests deben ser independientes y usar fixtures para datos de test (usuarios, unidades, franjas, etc.).
- La especificación debe quedarse como fuente de verdad del comportamiento esperado.
- Al terminar, actualizar PROGRESS.md y PROGRESS_ARCHIVE.md en la rama principal.
