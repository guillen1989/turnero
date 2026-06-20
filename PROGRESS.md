# Estado del desarrollo

## Fase actual
Fase 0 — Andamiaje

## Paso actual / siguiente paso
Fase 1, paso 1: modelos SQLAlchemy de Hospital, GrupoDeIntercambio y Unidad con tests.

## Pasos completados
- [x] Fase 0, paso 1: git init · estructura de carpetas · requirements.txt · config.py · app factory (Flask + Babel + SQLAlchemy + Login) · health check · test passing · Procfile
- [x] Fase 0, paso 2: Flask-Babel configurado · catálogo `es` inicializado y compilado · test de locale por defecto passing

## Notas / decisiones / asunciones pendientes
- Sin campo teléfono en ningún modelo ni formulario (decisión explícita del usuario).
- FranjaHoraria se define a nivel de GrupoDeIntercambio, no de Unidad individual.
- No se crea entidad Turno separada: fecha + franja_horaria_id se embeben directamente en turno_cedido y turno_aceptado.
- Autenticación: email + contraseña (Flask-Login + Werkzeug).
- El motor de matching se implementa como módulo puro sin acoplamiento a Flask ni SQLAlchemy.
- Los conflictos de pip (streamlit, spyder) son del sistema y no afectan al proyecto.
