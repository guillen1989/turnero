# Archivo histórico de PROGRESS.md

> Roll-up (condensado) del historial completo de pasos y fases anteriores, movido aquí desde `PROGRESS.md` el 2026-07-25 para mantener ese archivo ligero (ver `CLAUDE.md`).
> Este archivo **no se lee automáticamente al reanudar sesión** — solo se consulta bajo demanda (p. ej. "¿cómo se resolvió X hace tiempo?"). Para el historial detallado commit a commit, `git log` es la fuente autoritativa (la narrativa completa previa a este roll-up sigue recuperable vía `git`).

---

## Resumen por fases y tema (índice expandido)

### Fase 1-9 (base de la app, checklist completo abajo)
Estructura del proyecto, modelos (Hospital/GrupoIntercambio/Unidad/Categoria/FranjaHoraria/Usuario/PublicacionCambio/TurnoCedido/TurnoAceptado/MatchCambio/MatchParticipacion/Notificacion), auth, dashboard, motor de matching puro, caducidad, push/PWA, despliegue en Railway, administrativo/geografía, visor /cambios, junte de noches, feedback, CI/CD, avisos, búsquedas guardadas, eventos/funnel, Sentry, calendario. Detalle paso a paso en `## Pasos completados (checklist histórico)` más abajo.

### Fase 10 — Hoja de cambio digital (cerrada)
Documento de cambio con firma (`DocumentoCambio`/`ParticipanteDocumentoCambio`/`FirmaDocumentoCambio`), flujo mono-cuenta → firma cruzada, factibilidad contra planillas (no bloqueante), PDF fiel al impreso `hojacambios.png`, supervisora (autorizar/denegar con firma y motivo), anulación, nº de cambio por unidad (`numero_unidad`), "firmar los dos a la vez", enganche con matches simétricos. Librería de PDF: WeasyPrint crasheaba Railway (deps nativas) → **xhtml2pdf** (Python puro). Import perezoso de librerías de PDF como red de seguridad.

### Plan de 4 pasos anti-cuelgues de producción (2026-07, cerrado, sin deploy pendiente)
1. N+1 en `notificar_busquedas_guardadas` (busqueda → `contains_eager(usuario)`), test con fixture `query_counter` en `conftest.py`.
2. Matching repetía 5x `_candidatas_base` por request → `candidatas_activas_para(publicacion)` + param `candidatas=None`, calculado una vez por ruta.
3. `Procfile` → `gunicorn --workers 3 --timeout 60`.
4. Índices faltantes en `publicacion_cambio`/`usuario`/`unidad` (migración `285a7610df2f`).

Pendiente residual documentado: verificar en `railway logs` tras deploy (3 workers, migración, ausencia de `WORKER TIMEOUT`).

### Fase 11 — Junte de noches en hoja de cambio + supervisoras multiunidad + fixes de usuarios (cerrada)
`PLAN_JUNTE.md`: columna `tipo` en `DocumentoCambio`, `junte_semanal.py`, `crear_documento_cambio_junte`, frames PDF para rejillas. `PLAN_SUPERVISORAS_MULTIUNIDAD.md`: `UnidadSupervisada` (N:M), `services/supervision.py`, selector de unidad, invitación para supervisoras, e2e. Fixes: etiquetas unit, perfil supervisora solo lectura, `descartado` en `MapeoTrabajadorPlanilla`; creación/eliminación de usuarios (contraseña por invitación generalizada, email duplicado, cascada FK, email Resend).

### Fase 12 — Hojas de cambio para "cambios a 3" (cadena_3, `docs/PLAN_3.md`, cerrada)
PDF con frames para el tercer participante; `_usuario_que_recibe` central para notas/emails/PDF (2 o 3 participantes); `crear_documento_cambio_cadena_3`; `match_admite_documento_cambio`/`crear_documento_cambio_desde_match` generalizados a 2 o 3 participaciones; opción `cadena_3` en el formulario. Confirmado: el solape visual de `firma_tercero_frame` con frames vecinos es intencional (decisión del usuario).

### Fase 13 — Usuarios en varios servicios/unidades (`docs/USUARIOS_MULTI.md`, cerrada)
Modelo `usuario_unidad` (PK compuesta + `categoria_id`), `services/unidad_usuario.py` (`unidad_activa_o_403`, `sincronizar_unidades`), selector de unidad activa en `/calendario`, `/cambios`, `/planilla`, notificaciones con unidad de origen, unidad en Web Push. Invariante: unidad principal siempre en `usuario_unidad`. Pendiente anotado: 21 casos MUST change de la auditoría (pub/busquedas/unidad/documento_cambio) para publicaciones/edición multi-unidad.

### Cambios de turno en el día (`docs/CAMBIOS_DE_TURNO_EN_EL_DIA.md`)
Motor de matching/volcado/documento_cambio es agnóstico al tipo; mayoría de trabajo = tests de regresión sobre código existente. Fases 1-4 hechas (validador `validacion_cambio_dia.py`, matching, volcado, supervisión). Pendiente anotado: confirmar si Fases 5+ (factibilidad, caducidad, dashboard, e2e/UAT) necesitan tests propios.

### Feature flags (infraestructura, Fases A+B cerradas)
Modelos `FeatureFlag`/`FeatureFlagUnidad` (migración `7be3ca3f48b9`), servicio `feature_flags.py`, decorador `requiere_feature`, admin `/admin/feature-flags`. Flags aplicados: `hoja_cambio_digital`, `planilla_supervision_multiunidad`, `importacion_planilla` (seed `c90b9b61f0f8`, los 3 `activo_global=False`).

### Ahorro de tokens (mantenimiento, cerrado)
`app/routes/admin.py` (1194 líneas) dividido en paquete `app/routes/admin/`; `test_rutas_documento_cambio.py` (1942 líneas) en 8 archivos + `helpers_documento_cambio.py`; `AGENTS.md` reducido a stub de `CLAUDE.md`; recomendado `pytest --testmon`. Lección: tras splits, verificar imports con `pyflakes` (NameError dejas transacciones a medias que parecen deadlocks de BD).

### Limpieza de sintéticas huérfanas (mantenimiento, cerrado)
`caducidad.py` ahora **elimina** sintéticas huérfanas (antes solo `cancelada`; llegaron a ser el 70% de la tabla). `admin/analytics.py`: `oportunidades_3/4` filtraban sin `estado`, inflaban el conteo (corregido). Pendiente anotado: fan-out ilimitado de `buscar_cadenas_parciales_4_para`/`buscar_avisos_interes_para` (sin top-K) y el mismo defecto en `_cancelar_sinteticas_de`.

### Planilla / importación / supervisión (cerrado salvo el motor de reglas)
Import ILOG (parser, mapeos `MapeoCodigoTurno`/`MapeoTrabajadorPlanilla`, `importar_planilla`, rutas `/planilla/importar`, vinculación retroactiva al registrarse `sugerir_trabajador_planilla`). Visor matriz `planilla_supervision` (servicios batch N+1-safe, ajuste unilateral `AjustePlanillaSupervisora`, modal turno/estado, opciones por fila con ✎/−/+, contadores de presencia, "Reglas de comprobación"). Reglas de factibilidad integradas en `comprobar_factibilidad` (`_viola_limite_dias_consecutivos`, `_viola_descanso_nocturno`, límite configurable `limite_dias_consecutivos`). Pendiente: **motor de reglas laborales no empezado** (día consecutivo y descanso tras noche ya están; falta aclarar qué más necesita el MVP).

### Checklist histórico de pasos completados (Fases 1-10 y backlog)
Ver más abajo. Incluye Backlog B0–B19 completado (cadenas 3/4, calendario incl. juntes por semanas, notificaciones, búsquedas guardadas, push persistente, contraoferta, regalo/petición, desconfirmar match, tap-to-select en publicar/editar, "recuérdame" siempre activo, eliminar cuenta, feedback/recuperación de contraseña, demo ampliada, analytics).

---

## Backlog (fuente: .backlog)
- [x] B19: "Cambios a 4" — cadena a 4 bandas + sintéticas/avisos `sintetica_pub_intermedio_id` + preferencia mostrar/ocultar oportunidades 3/4 ✓
- [x] B18: Calendario visual — modo visor "Juntes de noches" (filas por semana con distribución trabaja/libra) ✓
- [x] B0: Panel Notificaciones (push global + prefs individuales + suscripciones a compañeros) ✓
- [x] B0b: «Me interesa» en Buscar cambios ✓
- [x] B1–B17: resto completado (mensaje ≤200c, jerarquía hospital>cat>servicio, instalación PWA, tipos personalizados, push CSRF+VAPID, confirmados con nombre, banner reaparición, regalo, petición, cualquier turno, email diario configurable, email admin feedback, matching 3 bandas, aviso coincidencia parcial, contraoferta, invitar por WhatsApp, push contador) ✓

## Notas / decisiones / asunciones pendientes
- Sin campo teléfono en ningún modelo/formulario (decisión explícita del usuario).
- FranjaHoraria por GrupoDeIntercambio; sin entidad Turno (fecha+franja embebidas en turno_cedido/aceptado).
- Auth: email+contraseña (Flask-Login + Werkzeug). El motor de matching es módulo puro sin acoplamiento a Flask/SQLAlchemy.
- `conftest.py`: BD única por checkout (hash del path) para paralelismo entre worktrees; fixture `query_counter` para N+1.
- Hoja de cambio digital (Fase 10): sin cadenas 3/4 en el flujo manual, mono-cuenta a elegir, factibilidad no bloqueante, PDF fiel al impreso, bloque "INFORME DE LA SUPERVISORA" estático, WeasyPrint→xhtml2pdf por native deps en Railway, `ESPECIFICACION.md` actualizado.
- Bug latente conocido (no arreglado): `app/templates/publicaciones/publicar.html` usa clases `alert`/`alert--*` inexistentes (solo `flash`/`flash--*`) y duplica `get_flashed_messages`.
- `cli/seed_staging.py`: amplía UCO·La Paz·Enfermería aditivo/idempotente con emails propios (`uco.*@demo.turnero.com`) para no colisionar con la unidad demo.
- Deuda técnica i18n: el catálogo arrastra desfases históricos; añadir cadenas a mano con `pybabel compile`, regenerar por completo solo en commit propio.
- Deudas de infraestructura de test: PDF requiere Python 3.12 (`anaconda3/bin/python -m pytest`); `test_rutas_importar_planilla.py` flaky por contención de BD compartida (no bloqueante); BD de test compartida entre worktrees → verificar con `TEST_DATABASE_URL` privada ante `UndefinedColumn`/deadlocks.

## Issues/observaciones que requieren decisión del usuario (sin implementar)
- **Cadenas a 3/4 y juntes de noches en el flujo de hoja de cambio** + **enganche completo del motor de matching**: pausados 2026-07-16 a petición del usuario; hay que aclarar cómo se construye una cadena a 3 a mano y qué campos necesita un junte de noches antes de retomarlos.
- **Crecimiento sin límite de publicaciones sintéticas** por cadena_3/4 (causa de las 225 por publicación en producción): investigar acotación en `app/matching/service.py` (pendiente de decisión).
- **Anomalía sin causa confirmada** en producción: edición de la pub 818 generó 36 oportunidades sin notificar al propio rol "C". Posible doble envío del form `/editar` (sin protección anti-doble-clic). Pendiente decidir logging de diagnóstico y/o mitigación preventiva.
- **`turno_aceptado` 2104 de la pub 818** sigue `abierto` (el fix no es retroactivo) — solo si el usuario pide corregirlo: `UPDATE` de fila puntual, sin migración.
- Domino/DNS manual (acciones que no puede hacer el agente): CNAME/TXT de `staging` y `app` en `turnero.xyz`, verificación de dominio en Railway, cuenta/API key de Resend. Sin `APP_BASE_URL`/`RESEND_API_KEY`, cada servicio cae a su fallback.
- Los 3 E2E preexistentes que fallaban (`test_hoja_de_cambio_golden_path_completa`, `test_golden_path_cambio_a_3`, `test_golden_path_staging`) quedaron fuera de scope de su ronda; `test_hoja_de_cambio_golden_path_completa` está desactualizado desde `827cd00`.

---

## Pasos completados (checklist histórico)

### Fase 0-9 (base)
- Fase 0: git init/estructura/config/app factory/health/Procfile; Flask-Babel con catálogo `es`.
- Fase 1: modelos Hospital/GrupoIntercambio/Unidad, Categoria, FranjaHoraria, Usuario (hash+UserMixin), PublicacionCambio/TurnoCedido/TurnoAceptado (resolución parcial), MatchCambio/MatchParticipacion/Notificacion + migración inicial.
- Fase 2: registro (crear hospital/unidad/categoría), LoginForm/RegistroForm, rutas auth, plantillas, CSS.
- Fase 3: dashboard, /publicar (múltiples cedidos), /publicaciones/<id>/cancelar.
- Fase 4: motor de matching puro (detectar_match_directo, UAT-3.1/3.2/3.3), buscar_matches_para, crear_match_directo desde /publicar.
- Fase 5: confirmar/rechazar match (confirmado_parcial→total, resuelve turnos, notificación).
- Fase 6: caducar_publicaciones_expiradas disparada en GET /.
- Fase 7: push (suscripción, integrado en crear_match/confirmar/rechazar).
- Fase 8: PWA (manifest, sw.js, icons, suscripción automática para autenticados).
- Despliegue: Railway+PostgreSQL+`flask db upgrade` automático (UAT 130/130).
- Fase 9: cascade hospital→unidad en registro y perfil; `es_admin` + panel admin; jerarquía País>Provincia>Ciudad; visor /cambios; fix formularios anidados /publicar; hook git pre-push (pytest tests/); E2E Playwright (6 tests); smoke_test.py post-deploy; tipos de publicación rediseñados; nuevo tipo «Junte de noches»; migraciones nullable→backfill→NOT NULL.
- Extra Fase 9: feedback (BD + /admin/feedback), CI/CD GitHub Actions, campana avisos con badge, contraoferta, «Me interesa» en Regalo/Petición, tarjetas libra/trabaja, Sentry/GlitchTip, tabla event/funnel, búsquedas guardadas con alertas, UX /cambios (tabs + guardar alerta), matching no deja matches huérfanos (tasa de confirmación 18%→mejorado).
- Calendario (Pasos 1-6 + Ronda 2): `construir_calendario_mes`, ruta + navegación mensual, grid con bandas de color y letra por banda, drill-down día→franja→publicaciones (JSON embebido, sin llamadas extra), enlace directo a `/cambios` filtrado, pantalla de inicio tras login, banners ayuda, oportunidades 3/4 con `es_sintetica_4`/`pub_intermedio`, juntes por semanas (`junte_semanal.py`).

### Fase 10 (hoja de cambio digital) — pasos
1. Modelos + migración `3f8d2428aa64` (9 tests).
2a. Servicio crear/firmar/notas ilog. 2b. Rutas + formulario + canvas (`pointerdown/move/up`) + e2e.
3. PDF fiel al impreso + botón (solo `completo`); WeasyPrint→xhtml2pdf; ajuste maquetación tras desborde a 2 páginas; verificado con `pdftoppm`/`pypdf` en cada iteración.
4. `comprobar_factibilidad` contra planillas (reutiliza reglas de `compatibilidad_planilla.py`), `factibilidad_estado`, aviso en `ver.html`.
5. `ESPECIFICACION.md` actualizado (entidades, reglas 11-14, CU10, xhtml2pdf, UAT-8.x).
6. Recomprobar factibilidad en la 2ª firma.
7. Firma cruzada entre cuentas reales + notificaciones (migración `c2938aae9b98`) + e2e.
8. Autorizar/denegar con firma y motivo (botón, checkbox "guardar firma", motivo en PDF y tabla, `<form id="decision-form">` unificado), bloque en lote (PDF combinado con `pypdf`) con firma guardada, anular con motivo (`anulado` aparte de `decision_supervisora`), `volcar_documento_a_planillas` (solo autoriza), nº de hoja con fecha de creación para desambiguar `numero_unidad`.
- Firma guardada reutilizable (`usuario.firma_guardada`, guardar/eliminar desde perfil y al firmar) — feedback: permanece en `/perfil/cuenta` y se ofrece al firmar (checkbox por defecto marcado).
- Listado "mis hojas de cambio", email opcional por usuario al completarse, "firmar los dos a la vez" (`firmar ambos`).
- Hoja encadenada: `depende_de_id` + overlay en factibilidad (PR #23 + PR 2); `_recalcular_factibilidad_dependientes` en autorizar/denegar/anular.
- Tabla de cambios (supervisora): filtros combinables por querystring, excluye `pendiente_firmas` de raíz; supervisora ve TODAS las de su grupo.
- `nombre_congelado` en `ParticipanteDocumentoCambio` para PDF estable (migración `fce42d5845ad`).

### Fase 11 (junte hoja + supervisoras multiunidad + usuarios)
Pasos 1-7 (junte) y 1-9 (multiunidad) como en el índice; Nota: pasos 1(a-c) de registro en papel (origen_papel) y mejoras de supervisión de planilla se documentan en las entradas originales vía `git`.

### Fase 12 (cadena_3 en hoja de cambio)
Paso 1: 5 `@frame` tercer participante; Paso 2: `_usuario_que_recibe`; Paso 3: `_contexto_pdf_cadena_3`; Paso 4: notas/email con `_usuario_que_recibe`; Paso 5: `crear_documento_cambio_cadena_3`; Paso 6: `match_admite_documento_cambio`/crear_desde_match para 3 partecip.; Paso 7: opción `cadena_3` en formulario (firma_ambos ignorado); Paso 8: UAT y revisión visual del PDF real (fase cerrada).

### Plan 4 pasos anti-cuelgues (detalle)
N+1 búsquedas guardadas (`contains_eager(usuario)`, fixture `query_counter`, workers) → `candidatas_activas_para` compartida (call_count==1 vía `unittest.mock.patch.object(wraps=...)`) → `Procfile` 3 workers/60s → índices `285a7610df2f`. Todo verificado (890 tests) y pendiente solo de decisión de push/deploy + verificación en `railway logs`.