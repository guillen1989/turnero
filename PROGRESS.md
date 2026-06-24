# Estado del desarrollo

## Fase actual
Fase 9 — Mejoras post-MVP

## Paso actual / siguiente paso
Sin pasos pendientes definidos.

## Backlog (fuente: .backlog)
- [x] B0: Panel Notificaciones: toggle global push, prefs individuales (match/confirmación/total), suscripciones a compañeros ✓
- [x] B0b: «Me interesa» en Buscar cambios: match manual desde cualquier publicación ajena (Regalo/Petición/Junte/Cambio con modal de selección) ✓
- [x] B1: Mensaje opcional (≤200 chars) al publicar un cambio ✓
- [x] B2: Jerarquía hospital > categoría > servicio en desplegables ✓
- [x] B3: Botón de instalación de la PWA ✓
- [x] B4: Tipos de turno personalizados al publicar (nombre + horario) ✓
- [x] B5: Arreglar notificaciones push (CSRF + codificación VAPID) ✓
- [x] B6: Pestaña confirmados muestra nombre del compañero ✓
- [x] B7: Banner de instalación reaparece tras desinstalar la PWA ✓
- [x] B8: Publicar tipo 'regalo' (ofrecer turno sin recibir nada) ✓
- [x] B9: Publicar tipo 'petición' (librar turno sin ofrecer nada) ✓
- [x] B10: Ofrecer 'cualquier turno de un día' al publicar ✓
- [x] B11: Avisos por email con límite diario configurable ✓
- [x] B12: Notificación por email al admin cuando se recibe un feedback ✓
- [x] B13: Matching a 3 bandas (ciclo A→B→C→A) — motor puro + servicio + ruta + dashboard ✓
- [x] B14: Aviso de coincidencia parcial (cambio ↔ regalo / cambio ↔ petición) ✓
- [x] B15: Contraoferta — proponer términos personalizados sobre una publicación de tipo cambio ✓
- [x] B16: Invitar a un compañero — enlace WhatsApp + URL pre-rellenada ✓
- [x] B17: Fix push acumulativo — contador basado en Notificacion.leida, se resetea al visitar Compatibles ✓

## Pasos completados
- [x] Fase 0, paso 1: git init · estructura de carpetas · requirements.txt · config.py · app factory · health check · test passing · Procfile
- [x] Fase 0, paso 2: Flask-Babel configurado · catálogo `es` · test de locale passing
- [x] Fase 1, paso 1: modelos Hospital, GrupoIntercambio y Unidad · conftest con PostgreSQL · 8 tests passing
- [x] Fase 1, paso 2: modelos Categoria (con seed idempotente) y FranjaHoraria · 15 tests passing
- [x] Fase 1, paso 3: modelo Usuario · hash de contraseña · Flask-Login UserMixin · grupo_intercambio accesible · 20 tests passing
- [x] Fase 1, paso 4: modelos PublicacionCambio, TurnoCedido, TurnoAceptado · resolución parcial · actualizar_estado() · 29 tests passing
- [x] Fase 1, paso 5: modelos MatchCambio, MatchParticipacion, Notificacion · extensible a N bandas · migración inicial generada y aplicada
- [x] Fase 2, paso 1: servicio de registro (encontrar_o_crear hospital/unidad/categoría) · formulario RegistroForm y LoginForm · rutas /auth/registro, /auth/login, /auth/logout · plantillas HTML · CSS básico · 52 tests passing
- [x] Fase 3, paso 1: dashboard del usuario · ruta / diferenciada por auth · lista de publicaciones propias · empty state · 57 tests passing
- [x] Fase 3, paso 2: ruta /publicar · servicio publicar_cambio · formulario con slots numerados · múltiples turnos cedidos · validación mínimo 1 cedido · 64 tests passing
- [x] Fase 3, paso 3: POST /publicaciones/<id>/cancelar · guarda "cancelada" · 403 si ajena · 409 si ya inactiva · 70 tests passing
- [x] Fase 4, paso 1: motor de matching puro (sin DB) · detectar_match_directo · 8 tests UAT-3.1/3.2/3.3 · 78 tests passing
- [x] Fase 4, paso 2: servicio buscar_matches_para · filtros categoría/grupo/estado · 84 tests passing
- [x] Fase 4, paso 3: crear_match_directo · MatchCambio + 2 MatchParticipacion + 2 Notificacion · disparado desde /publicar · 88 tests passing
- [x] Fase 5, paso 1: POST /matches/<id>/confirmar y /rechazar · confirmado_parcial → confirmado_total · resuelve turnos · Notificacion confirmacion_parcial/rechazo · 102 tests passing
- [x] Fase 6, paso 1: servicio caducar_publicaciones_expiradas(hoy) · caduca si todos los turnos cedidos abiertos son pasados · 110 tests passing
- [x] Fase 6, paso 2: caducidad disparada en GET / (dashboard) · 111 tests passing
- [x] Fase 7, paso 1: enviar_push + POST /push/suscribir · guarda subscription · silent ante excepciones WebPush · 118 tests passing
- [x] Fase 7, paso 2: push integrado en crear_match_directo, confirmar_participacion y rechazar_match · 121 tests passing
- [x] Fase 8, paso 1: /manifest.json + /sw.js + /push/vapid-public-key · sw.js con push/install/fetch handlers · 126 tests passing
- [x] Fase 8, paso 2: base.html — <link rel="manifest">, meta theme-color, registro SW, suscripción push automática para usuarios autenticados · iconos PNG 192×512 · 130 tests passing
- [x] Despliegue: Railway · PostgreSQL · variables de entorno · flask db upgrade automático · UAT 130/130
- [x] Fase 9, paso 1: cascade hospital→unidad en registro y perfil · ruta /auth/perfil · API /auth/api/unidades · botón Actualizar + Activar notificaciones en dashboard · enlace Mi perfil en nav · 140 tests passing
- [x] Fase 9, paso 2: campo es_admin en Usuario · migración · CLI flask init-admin · panel /admin (usuarios, hospitales, unidades, categorías, publicaciones) · 153 tests passing
- [x] Fase 9, paso 3: jerarquía geográfica País > Provincia > Ciudad > Hospital · modelos Pais/Provincia/Ciudad · migración · API /auth/api/provincias|ciudades|hospitales · cascade JS 4 niveles · CRUD admin para países/provincias/ciudades · panel de perfil y registro actualizados · 155 tests passing
- [x] Fase 9, paso 4: visor /cambios · filtro por mes y/o día · restringe a mismo grupo+categoría · enlace en nav · 166 tests passing
- [x] Fix: formularios anidados en /publicar · el form de «nueva franja» estaba dentro del form principal · el navegador fusionaba ambos e incluía accion=nueva_franja en el submit principal · bloqueaba la publicación a todos los usuarios · solución: mover el form de nueva franja fuera del form principal
- [x] Calidad: hook git pre-push · ejecuta pytest tests/ antes de cada push · aborta si algún test falla · script instalable en scripts/install-hooks.sh
- [x] Calidad: tests E2E con Playwright · 6 tests en e2e/ contra Chromium headless · cubren login, rutas protegidas, publicación de turno, validación server-side y regresión del bug de formularios anidados · pytest e2e/ los ejecuta · no bloquean el hook pre-push (que solo corre tests/)
- [x] Calidad: smoke test post-deploy · scripts/smoke_test.py · 7 checks HTTP contra la URL de producción · detecta app caída, migraciones rotas y estáticos inaccesibles · uso: python scripts/smoke_test.py https://tu-app.railway.app
- [x] feat: enlace «Mis cambios» añadido a la barra de navegación (apunta al dashboard /)
- [x] feat: footer de contacto rediseñado con separador, texto descriptivo y estilos integrados
- [x] feat: selector de tipo de publicación rediseñado como tarjetas con borde, negrita y descripción secundaria
- [x] feat: nuevo tipo de publicación «Junte de noches» · formulario asistido con selector de semana, cadencia (LMVD / MJS) y cuadrícula de 7 noches · el servidor deriva automáticamente cedidos y aceptados · matching usa el motor existente · 8 tests · 223 tests passing
- [x] fix(migration): patrón nullable→backfill→NOT NULL aplicado a tipo en publicacion_cambio y cualquier_franja en turno_aceptado · crashes de deploy resueltos
- [x] feat: sistema de feedback por email · ruta /feedback · envío a domingofestivo@gmail.com via Gmail SMTP · prerellena email si el usuario está autenticado · 7 tests
- [x] fix(feedback): guarda feedback en BD en vez de SMTP síncrono · nuevo modelo Feedback · vista /admin/feedback · 9 tests · 225 passing
- [x] chore: pipeline CI/CD completo · GitHub Actions (suite completa + smoke test post-deploy) · pytest-testmon en pre-push local · Railway gate bloqueado hasta que CI pase
- [x] feat(avisos): campana en nav con badge rojo · panel /avisos con lista de publicaciones de seguidos · Notificacion.publicacion_id · context processor avisos_no_leidos · 314 tests passing
- [x] style(admin/feedback): panel en tarjetas responsive · selección múltiple para marcar leídos · ruta bulk POST /admin/feedback/marcar-leidos · 316 tests passing
- [x] refactor+perf: resolver_geo/hospital/unidad extraídos a services/registro · _conteos_tabs consolida confirmada+caducada en 1 GROUP BY · 316 tests passing
- [x] fix(ui): «Me interesa» en publicaciones Regalo omite el diálogo de selección de turno y pasa directamente a pendiente de confirmar · backend auto-usa los turnos_aceptados del regalo como cedidos de la petición espejo · 375 tests passing
- [x] fix(ui): «Me interesa» en Petición de turno único pasa directo sin diálogo · _pub_js_data añade cualquierFranja a cedidos y defiende contra franja_horaria=None · con varios cedidos o cedido de cualquier turno mantiene el diálogo · 376 tests passing

## Backlog de calidad (pendiente)
- [x] Integrar pytest e2e/ en el ciclo de CI/CD de Railway (GitHub Actions o similar) ✓
- [x] Añadir APP_URL al .env local y smoke test integrado en GitHub Actions post-deploy ✓

## Notas / decisiones / asunciones pendientes
- Sin campo teléfono en ningún modelo ni formulario (decisión explícita del usuario).
- FranjaHoraria se define a nivel de GrupoDeIntercambio, no de Unidad individual.
- No se crea entidad Turno separada: fecha + franja_horaria_id se embeben directamente en turno_cedido y turno_aceptado.
- Autenticación: email + contraseña (Flask-Login + Werkzeug).
- El motor de matching se implementa como módulo puro sin acoplamiento a Flask ni SQLAlchemy.
- Los conflictos de pip (streamlit, spyder) son del sistema y no afectan al proyecto.
- conftest.py empuja un app context fresco por test para aislar g (Flask-Login) y la sesión SQLAlchemy. Necesario porque en Flask 3.x g está scoped al app context (no al request context) y Flask-Login cachea current_user en g._login_user.
