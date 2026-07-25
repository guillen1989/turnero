# Propuesta: backup cifrado de emergencia por unidad

**Estado:** pendiente de aprobación (la ayudante de la supervisora tiene que hablarlo con sus jefas). Planteado el 2026-07-22.

**Para retomarlo:** dile a Claude que lea este archivo y siga las especificaciones.

## Motivación

El software centralizado del hospital (usado por varios hospitales) tiende a colgarse en épocas de mucho trabajo. La ayudante de la supervisora quiere una vía para consultar el estado de turnos y cambios de su unidad aunque la app no responda — sin depender de tener la app funcionando en ese momento.

## Diseño acordado

Dos archivos distintos, con propósitos distintos:

1. **Excel de consulta** (para leer a simple vista durante una caída): mes actual + 3 siguientes, por unidad. Por trabajador y fecha: turno asignado, o libre/vacaciones/no_disponible. Pestaña aparte con los cambios de turno (`DocumentoCambio`) pendientes o ya autorizados que afecten a esas fechas.
2. **Zip de datos crudos** (backup de recuperación, no de consulta en caliente): turnos (`TurnoPlanilla`), estados de día (`EstadoDiaPlanilla`), y documentos de cambio con sus participantes y firmas (`DocumentoCambio`, `ParticipanteDocumentoCambio`, `FirmaDocumentoCambio`), en CSV/JSON, filtrados a los usuarios de esa unidad únicamente.

### Frecuencia

Job nocturno único (no hace falta más). Regenerar bajo demanda no sirve como red de seguridad: si hace falta el archivo es precisamente porque la app no responde en ese momento.

### Cifrado

Ambos archivos van dentro de un único zip cifrado con AES-256 (librería `pyzipper`; no usar el cifrado nativo de Excel — es débil y mal soportado en Python).

- **No reutilizar la contraseña de login de la supervisora.** El backend no la tiene en texto plano (solo el hash), y aunque la tuviera, acoplarla sería un riesgo: si el zip se filtra, se filtra también la contraseña de la cuenta real.
- Contraseña propia y dedicada, sin relación con ninguna cuenta. Se guarda en el gestor de contraseñas de Google de supervisora y ayudante (para que no dependa de que la recuerden de memoria — es un archivo de uso muy poco frecuente).

### Almacenamiento

Google Drive, en una carpeta a la que solo tengan acceso supervisora + ayudante (no todo el hospital — son datos de horarios de trabajadores).

## Bloqueantes pendientes

- **Credenciales de Google Drive:** subir el archivo requiere una cuenta de servicio de Google Cloud, creada por ellas, con la carpeta destino compartida con el email de esa cuenta de servicio. Esto no se puede generar desde aquí — requiere acción suya en Google Cloud Console.
- **Dónde vive el job:** hoy el `Procfile` solo tiene el proceso `web`; no hay worker/cron montado en Railway. Habría que añadir un cron job (Railway soporta esto como tipo de servicio aparte) que ejecute un script Python.

## Alcance técnico (referencia rápida para implementar)

- Datos ya modelados en `app/models/planilla.py` (`TurnoPlanilla`, `EstadoDiaPlanilla`) y `app/models/documento_cambio.py`.
- Unidad de scope: `Unidad` (una unidad por Excel/zip, no todo el hospital ni todo el grupo de intercambio).
- Dependencias nuevas a añadir: `pyzipper` (cifrado AES-256), una librería de generación de Excel (p. ej. `openpyxl`, ya que `xhtml2pdf` no sirve para esto).
- Seguir TDD y el patrón de migraciones en tres pasos de `CLAUDE.md` si se añade algún modelo/columna nueva (probablemente no haga falta ninguna — es un job de solo lectura sobre datos ya existentes).
