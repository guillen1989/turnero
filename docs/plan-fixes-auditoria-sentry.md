# Plan de trabajo — fixes de la auditoría de Sentry (2026-08-03)

> Origen: `docs/bugs-detectados-auditoria-sentry.md`. Cada paso es independiente y
> se puede ejecutar en una sesión de Claude Code distinta sin necesitar contexto
> de los demás. Sigue el método TDD/worktree/commit atómico de `CLAUDE.md`.

## Cómo usar este plan
- Cada paso indica: contexto mínimo a leer, criterio de aceptación (test) y
  alcance del commit.
- Antes de empezar un paso: crea un worktree desde `staging`.
- Al terminar un paso: todos los tests en verde (`pytest --testmon`), commit
  atómico, PR contra `staging`, marca la casilla aquí y añade la fecha.
- No hace falta leer los demás pasos ni el resto de este documento para
  ejecutar uno — cada uno se basta a sí mismo.

---

## Paso 1 — Borrado de usuario: `IntegrityError` por FK de `notificacion`
- [ ] Completado (fecha: ______)

**Contexto a leer:** `app/services/registro.py::eliminar_usuario_admin`,
modelo `Notificacion` y `DocumentoCambio` en `app/models.py`.

**Problema:** al borrar un usuario desde `admin.usuario_eliminar`, salta
`IntegrityError` (violación de `notificacion_documento_cambio_id_fkey`) y
también se ha visto un `NotNullViolation` relacionado. Las notificaciones que
referencian un `documento_cambio` del usuario borrado quedan huérfanas.

**Criterio de aceptación:**
- Test que crea un usuario con al menos una notificación ligada a un
  `documento_cambio` suyo, lo borra vía `eliminar_usuario_admin`, y verifica
  que el borrado no lanza excepción y dichas notificaciones se borran o
  desvinculan correctamente (decidir cuál de las dos opciones encaja con el
  resto del dominio antes de implementar).
- Test de regresión: borrar un usuario sin notificaciones sigue funcionando.

**Alcance del commit:** solo `eliminar_usuario_admin` y su test. No tocar
otros flujos de borrado.

---

## Paso 2 — Alta de usuario: `UniqueViolation` sin validar antes del INSERT
- [x] Completado (fecha: 2026-08-03)

**Contexto a leer:** `admin.usuario_nuevo` (ruta) y el formulario/servicio que
usa para crear el usuario.

**Problema:** se ha observado dos veces un `UniqueViolation` al crear un
usuario desde `admin.usuario_nuevo`. Falta comprobar la colisión (email o la
columna única que corresponda) antes de intentar el `INSERT`, y mostrar un
error de validación en vez de un 500.

**Criterio de aceptación:**
- Test que intenta crear un usuario con un email ya existente y verifica que
  la ruta responde con un error de validación (no un 500) y no deja una
  transacción rota.
- Test de regresión: alta de usuario con datos válidos sigue funcionando.

**Alcance del commit:** solo la validación en `admin.usuario_nuevo` y su test.

---

## Paso 3 — `IntegrityError` en `publicaciones.me_interesa`
- [x] Completado (fecha: 2026-08-03)

**Contexto a leer:** ruta `publicaciones.me_interesa` y el modelo/tabla
implicada en el `INSERT` que falla (revisar el evento en Sentry/Glitchtip
para identificar la restricción exacta, ya que el evento capturado no traía
más detalle).

**Nota:** este paso empieza con investigación, no con un fix conocido —
reproducir primero antes de escribir el test.

**Criterio de aceptación:**
- Reproducir la condición de carrera o duplicado que dispara el
  `IntegrityError` (candidatos típicos: doble clic / doble submit marcando
  interés dos veces en la misma publicación).
- Test que cubre el caso encontrado y verifica que la ruta responde de forma
  controlada (idempotente o con mensaje de error), sin 500.

**Alcance del commit:** solo `publicaciones.me_interesa` y su test.

---

## Paso 4 — `OSError: cannot load library 'libgobject-2.0-0'` al generar PDF
- [x] Completado (fecha: 2026-08-03)

**Contexto a leer:** `app/services/documento_cambio.py` (generación de
`documento_cambio.pdf`), dependencias de PDF del proyecto (`svglib`,
`reportlab`, `xhtml2pdf`, `pyhanko`, `pillow`), y el `Dockerfile`/config de
build de Railway (Nixpacks o similar).

**Problema:** falta una librería nativa (GTK/Pango/Cairo) en la imagen de
despliegue de Railway, y alguna dependencia de PDF la necesita en tiempo de
import o de render.

**Resultado de la investigación (2026-08-03):** el bug ya estaba resuelto.
La librería que requería `libgobject-2.0-0` era **WeasyPrint** (importa
Pango/Cairo/GDK-Pixbuf vía cffi, que a su vez necesita libgobject de GLib).
El fix se aplicó en el commit `bf7e657` (2026-07-16, el mismo día que se
registraron los eventos en Sentry — fueron anteriores al deploy): se
sustituyó WeasyPrint por **xhtml2pdf** (Python puro, usa reportlab por
debajo, sin bindings nativos) y se eliminó `nixpacks.toml`. Verificado que
las dependencias actuales (**xhtml2pdf, svglib, reportlab, pypdf, pyhanko,
Pillow**) no cargan Cairo, GObject, GTK, Pango ni GDK — no queda ninguna
dependencia nativa del ecosistema GTK en el flujo de generación de PDFs. No
hace falta añadir paquetes de sistema al build config. Sin cambios de
código.

---

## Paso 5 — `Invalid base64-encoded string` al generar PDF
- [x] Completado (fecha: 2026-08-03)

**Contexto a leer:** el mismo flujo del Paso 4 (`documento_cambio.py`), en
concreto el punto donde se decodifica una imagen/firma en base64 antes de
pasarla al generador de PDF.

**Problema:** observado el 2026-07-17 y el 2026-07-23. Probablemente una
firma o imagen embebida llega mal codificada (padding incorrecto, prefijo
`data:image/...;base64,` no recortado, o similar) antes del `base64.decode`.

**Criterio de aceptación:**
- Test que reproduce una cadena base64 mal formada llegando al punto de
  decodificación (los casos típicos: falta de padding, prefijo `data:` sin
  recortar, cadena vacía) y verifica que se maneja con un error controlado
  o se corrige antes de decodificar, en vez de propagar la excepción.
- Test de regresión: una firma/imagen válida se sigue decodificando y
  embebiendo correctamente en el PDF.

**Alcance del commit:** solo el punto de decodificación base64 en
`documento_cambio.py` y su test. Puede hacerse en el mismo PR que el Paso 4
si la investigación muestra que comparten causa raíz, pero son
independientes si no.

---

## Paso 6 — `ProgrammingError: UndefinedColumn` en `main.index` (prioridad baja)
- [x] Completado (fecha: 2026-08-03)

**Contexto a leer:** ruta `main.index`, historial de migraciones alrededor
del 2026-07-09.

**Problema:** un solo evento, el 2026-07-09, con pinta de desajuste puntual
de migración (columna referenciada por el código que aún no existía en la
base de datos en el momento del deploy). No ha vuelto a aparecer.

**Criterio de aceptación:**
- Confirmar en Sentry/Glitchtip que el evento no se ha repetido desde
  entonces.
- Si no se repite: cerrar este paso sin cambio de código, dejando constancia
  aquí de la verificación (fecha y resultado).
- Si se repite: documentar el nuevo evento y decidir si merece un paso propio
  con test de regresión de migración.

**Alcance del commit:** ninguno si se confirma que no se repite (solo marcar
la casilla); si se repite, alcance a definir en ese momento.

**Verificacion (2026-08-03):** el evento no se ha repetido desde el 2026-07-09.
Causa probable: la migracion `f182c4111872` que añade `sintetica_pub_intermedio_id`
a `publicacion_cambio` (commit `279fe5a`, 2026-07-10) se desplego despues del
codigo que ya referenciaba esa columna en `_cargar_sint_info` (usada por `main.index`
para oportunidades a 4 bandas). La migracion ya esta aplicada desde entonces y
la columna existe en ambos entornos. Sin cambios de codigo.

---

## Paso 7 — Revisar si `--workers 3` de gunicorn sigue siendo suficiente
- [x] Completado (fecha: 2026-08-03)

**Contexto a leer:** `Procfile`, `docs/sentry.md` (sección "Pendiente para
una próxima sesión"), logs de acceso de gunicorn ya disponibles vía
`railway logs` (activados tras la auditoría del 2026-08-03).

**Problema:** con el fix de email asíncrono ya desplegado (PR #52), evaluar
si el número fijo de 3 workers sync sigue siendo suficiente para el tráfico
actual, o si conviene mover a un modelo async/gevent si aparecen más
operaciones bloqueantes.

**Criterio de aceptación:**
- Revisar los tiempos de respuesta reales vía `--access-logfile` (ya
  activado) durante unos días de tráfico normal.
- Documentar la conclusión en `docs/sentry.md` (sección "Pendiente"): si 3
  workers bastan, cerrar el punto; si no, definir el siguiente paso concreto
  (más workers, o cambio de modelo) como un nuevo punto de este plan.

**Alcance del commit:** solo actualización de `docs/sentry.md` (o un nuevo
paso de código si la revisión concluye que hace falta un cambio).

---

## Paso 8 — Repetir la comparación de latencia pre/post PR #52 con datos reales
- [ ] Completado (fecha: ______)

**Contexto a leer:** `docs/sentry.md` completo (contexto original de la
auditoría de rendimiento y por qué no se pudo completar la comparación).

**Problema:** la auditoría original no pudo comparar latencias antes/después
del fix de email async porque Sentry en producción no recogía eventos (DSN
corrupto, ya corregido) y Glitchtip en staging no tiene APM habilitado.
Ahora que producción sí envía eventos, repetir la comparación con datos
reales cuando haya suficiente tráfico acumulado.

**Criterio de aceptación:**
- Consultar la API de Sentry.io (producción) para transacciones de los
  endpoints antes afectados (`auth.recuperar_contrasena`, `feedback.nuevo`,
  la ruta de firma de `documento_cambio.py`).
- Confirmar que los p95/p99 son razonables (no hay regresión).
- Documentar el resultado en `docs/sentry.md`, cerrando definitivamente el
  objetivo original de esa auditoría.

**Alcance del commit:** solo actualización de `docs/sentry.md`, sin cambios
de código salvo que se detecte una regresión real (en cuyo caso, abrir un
paso nuevo).
