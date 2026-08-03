# Bugs detectados durante la auditoría de Sentry (2026-08-03)

Efecto secundario de revisar los eventos de tipo `error` en Sentry/Glitchtip mientras se
hacía la auditoría de rendimiento (ver `docs/sentry.md`). No relacionados con el objetivo
original de esa sesión — se documentan aquí para priorizarlos en un plan de trabajo aparte
(worktree + TDD, según el método de trabajo del proyecto).

## 1. IntegrityError al borrar un usuario desde admin

`admin.usuario_eliminar` → `app/services/registro.py::eliminar_usuario_admin`.

- `IntegrityError` por violación de FK: `notificacion_documento_cambio_id_fkey`.
- También se observó un `NotNullViolation` relacionado.

Causa probable: al borrar un usuario no se limpian/reasignan las filas de `documento_cambio`
que quedan referenciadas por `notificacion`, y el borrado falla a mitad.

## 2. IntegrityError al crear un usuario desde admin

`admin.usuario_nuevo` — `UniqueViolation` (registro duplicado). Observado dos veces en los
eventos. Falta validar/manejar la colisión (probablemente email o alguna combinación única)
antes de intentar el `INSERT`.

## 3. IntegrityError en `publicaciones.me_interesa`

Sin más detalle en el evento capturado — revisar el flujo completo antes de reproducir.

## 4. `OSError: cannot load library 'libgobject-2.0-0'` al generar PDF de documento de cambio

`app.services.documento_cambio` (generación de `documento_cambio.pdf`). Repetido varias veces
el 2026-07-16. Falta una dependencia de sistema (probablemente para WeasyPrint/Pango/Cairo o
similar) en el entorno de despliegue — el proyecto usa `svglib`, `reportlab`, `xhtml2pdf`,
`pyhanko` y `pillow` para PDFs, alguna de las cuales depende de librerías nativas de
GTK/Pango no instaladas en la imagen de Railway.

## 5. `Invalid base64-encoded string` al generar PDF de documento de cambio

Mismo flujo que el bug 4 (`documento_cambio.pdf`), observado el 2026-07-17 y el 2026-07-23.
Probablemente relacionado con una firma o imagen embebida mal codificada antes de pasarla al
generador de PDF — revisar el punto donde se decodifica base64 en ese flujo.

## 6. `ProgrammingError: UndefinedColumn` en `main.index`

Observado una vez, 2026-07-09. Tiene pinta de desajuste de migración puntual ya resuelto
(no ha vuelto a aparecer desde entonces). Prioridad baja — solo confirmar que no se repite
antes de descartarlo.

## Prioridad sugerida

Los bugs 1 y 4 son los más graves (rompen flujos completos: borrado de usuario y firma de
documentos de cambio). Los bugs 2, 3 y 5 afectan a casos concretos pero no bloquean el flujo
principal. El bug 6 es de baja prioridad, posible ruido histórico.
