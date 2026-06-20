# Estado del desarrollo

## Fase actual
Fase 0 — Andamiaje

## Paso actual / siguiente paso
Fase 0, paso 2: configurar Flask-Babel (i18n) — crear babel.cfg, catálogo `es`, y marcar los primeros textos con `_()`.

## Pasos completados
- [x] Fase 0, paso 1: git init · estructura de carpetas · requirements.txt · config.py · app factory (Flask + Babel + SQLAlchemy + Login) · health check · test passing · Procfile

## Notas / decisiones / asunciones pendientes
- Sin campo teléfono en ningún modelo ni formulario (decisión explícita del usuario).
- FranjaHoraria se define a nivel de GrupoDeIntercambio, no de Unidad individual.
- No se crea entidad Turno separada: fecha + franja_horaria_id se embeben directamente en turno_cedido y turno_aceptado.
- Autenticación: email + contraseña (Flask-Login + Werkzeug).
- El motor de matching se implementa como módulo puro sin acoplamiento a Flask ni SQLAlchemy.
- Los conflictos de pip (streamlit, spyder) son del sistema y no afectan al proyecto.
