# Estado del desarrollo

## Fase actual
Fase 9 — Mejoras post-MVP

## Paso actual / siguiente paso
Ronda 2 del calendario completa (Pasos 1-6, rama `staging`, sin push — lo
hace el usuario a mano). Todos los fallos e2e locales investigados y
corregidos — los 9 tests e2e locales pasan (`e2e/test_sintetica_staging.py`
queda deliberadamente sin ejecutar por apuntar a la app real de Railway).
Siguiente: cuando se decida abordar B18 (modo "Juntes de noches"), retomar
desde ahí.
`e2e/test_sintetica_staging.py` apunta a la app real de Railway (STAGING_URL)
y no se ha vuelto a ejecutar tras el diagnóstico para no seguir escribiendo
usuarios de prueba en la base de datos compartida de staging sin necesidad.

## Backlog (fuente: .backlog)
- [ ] B18: Calendario visual — modo visor "Juntes de noches" (además de Ofertas/Peticiones). Diseño ya contempla el hueco para un tercer `modo`; implementar más adelante.
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
- [x] feat(cuenta): eliminar cuenta · servicio eliminar_cuenta (rechaza matches, cancela publicaciones, anonimiza datos) · ruta POST /auth/perfil/cuenta/eliminar · zona de peligro en perfil_cuenta.html · 13 tests · 449 tests passing
- [x] feat(admin): eliminar usuario con página de confirmación · servicio eliminar_usuario_admin maneja todos los FK (BusquedaGuardada, Suscripciones, notif. ajenas) · GET /admin/usuarios/<id>/eliminar muestra pub count · 5 tests nuevos · 454 tests passing
- [x] feat(cambios): filtro tipo_fecha (cedido / aceptado) en /cambios · distingue «quiere librar esa fecha» de «ofrece trabajar esa fecha» · actualiza busquedas_guardadas y publicacion_cumple_filtros · 3 tests nuevos · 457 tests passing
- [x] feat(matching): aviso de interés (cambio↔cambio solapamiento unilateral) · notificación aviso_interes para ambas partes · badge naranja en avisos · push notification · 9 tests · 466 tests passing
- [x] feat(matching): generador de cambios a 3 bandas · PublicacionCambio sintética (es_sintetica+FKs) · migración e8e3d3c815bd · crear_pub_sintetica / buscar_sinteticas_que_coinciden_con / crear_cadena_3_desde_sintetica · ciclo de vida: cancelar pub fuente cancela sintética (cancelar + editar + caducidad) · badge «Oportunidad a 3» en búsqueda · excluye sintéticas del dashboard propio · 11 tests · 87 tests passing en suite relacionada
- [x] feat(matching): aviso a ambas partes cuando se genera la sintética · tipo aviso_sintetica · push notification · idempotente · 2 tests
- [x] fix(avisos): aviso_interes y aviso_sintetica aparecen en /avisos y cuentan en el badge · el filtro de la ruta solo incluía 3 tipos y excluía los dos nuevos
- [x] feat(matching): flujo «Me interesa» sobre pub sintética cierra cadena_3 directamente · sin necesidad de que el tercer usuario publique su propio cambio · copia cedidos/aceptados de la sintética sin invertir · llama crear_cadena_3_desde_sintetica · 2 tests nuevos · 15 tests en suite sintetica · 481 tests passing
- [x] feat(ui): dashboard Activos muestra tarjeta «Oportunidad a 3 bandas» (azul) y «Interés parcial» (naranja) para los dos usuarios implicados en la sintética
- [x] feat(planilla): planilla de turnos mensual · modelos TurnoPlanilla+PlanillaMes · servicio CRUD (añadir/eliminar/publicar/despublicar) · motor compatibilidad puro (turnos_solapan, libres/compatibles por día, con/sin nombres según planilla publicada) · UI /planilla con navegación mensual y doblajes · enlace en nav · flash de compatibilidad al publicar cambio · 45 tests
- [x] feat(planilla): validación 100% estricta al publicar mes (días sin cumplimentar bloquean) · compatibilidad persistente en BD (CompatibilidadPlanilla) · tarjeta "Disponibilidad en planilla" en Activos · trigger de recálculo al publicar planilla · 558 tests
- [x] feat(planilla): relleno masivo · relleno por rango (del día N al día M con un turno/estado, 1 clic) · selección múltiple con checkboxes por día + barra flotante · "Marcar todos/Ninguno" · 9 tests · 567 tests
- [x] feat(ui): botón de compartir por WhatsApp en tarjetas «Oportunidad a 3 bandas» · texto con fechas y enlace directo a la pub sintética
- [x] feat(planilla): notas por día + volcado de cambios confirmados · modelo NotaDia · campo volcado_planilla en MatchParticipacion · migración 58a556f9da30 · servicios guardar_nota_dia/get_notas_mes/get_matches_pendientes_volcar/volcar_matches_a_planilla · rutas /planilla/dia/nota y /planilla/volcar-cambios · banner en planilla con cambios pendientes · <details> editables por día · 23 tests · 590 tests passing
- [x] feat(planilla): calendario compacto + color por tipo de turno · columna FranjaHoraria.color + color_texto · paleta general + paleta oscura noche/nocturno · auto-asignación y backfill migración e2f9e8059eaa · chips con color propio · celda diagonal en doblaje · scroll-anchor en acciones de día único · 592 tests passing
- [x] test(e2e): golden path local con tres usuarios (Ana/Pedro/Carlos) · headed · Playwright · pausa 5 s en pantallas clave · Carlos cierra el triángulo con «Me interesa»
- [x] test(e2e): golden path contra staging en Railway · registro de usuarios via UI (cascade hospital) · selector específico para el botón de la tarjeta sintética · diagnóstico en aserciones
- [x] merge(staging→main): todo el bloque de cambio a 3 bandas fusionado en producción · conflictos resueltos a favor de staging · 481 tests passing · deploy en Railway
- [x] feat(analytics): clics «Me interesa» + cambios activos acumulados en gráfica + backfill match.fecha_creacion NULLs · Event "me_interesa" en ruta me_interesa · fecha_cierre en PublicacionCambio (event listener ORM + caducidad bulk) · migración 40d574d237f8 · nueva serie "activas (acumulado)" en chart · tarjeta contador me_interesa · 7 tests nuevos · 19 passing en suite analytics
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
- [x] feat(ui): tarjetas de match muestran «libra» y «trabaja» de cada parte implicada · _calcular_trabajas() aplica fórmula (i-1)%N sobre el ciclo de participaciones · cubre cambio directo, cadena a 3 bandas y coincidencias parciales · 376 tests passing
- [x] ops: Sentry/GlitchTip integrado · sentry-sdk[flask] · _init_sentry() en app factory · condicionado a SENTRY_DSN · traces_sample_rate=0.1 · sin impacto en tests ni dev local · 376 tests passing
- [x] ops: tabla event para funnel · modelo Event · migración · servicio registrar_evento (silencioso) · enganches en publicar_cambio, crear_match_directo, crear_cadena_3 y confirmar_participacion · 5 tests · 381 tests passing
- [x] ops: evento publication_cancelled · enganche en cancelar_publicacion · 1 test · 382 tests passing
- [x] ops: evento match_cancelled · enganche en rechazar_match para todos los participantes · scripts/funnel_queries.sql con 5 queries de funnel · 1 test · 383 tests passing
- [x] feat: búsquedas guardadas con alertas · modelo BusquedaGuardada · servicio puro publicacion_cumple_filtros · notificar_busquedas_guardadas integrado en publicar_cambio · rutas CRUD · pestaña "Mis alertas" en /cambios · botón "Guardar como alerta" con filtros activos · notificación alerta_busqueda_guardada en panel /avisos y push · migración · 33 tests · 416 tests passing
- [x] feat(ux): UX refactor /cambios + push toggle búsquedas guardadas · título "Buscar cambios" · tabs en formato visual · botón "Guardar búsqueda como alerta" junto a filtrar/limpiar (HTML5 form= attribute) · pestaña Activos combina matches+publicaciones abiertas (backcompat via _ALIASES_ESTADO) · toggle notif_busqueda_guardada en panel notificaciones · aviso alerta_busqueda_guardada enlaza a /cambios con filtros de búsqueda (busqueda_guardada_id FK con ondelete=SET NULL) · migración e93a778414b8 · 419 tests passing
- [x] fix(matching): cancelar/editar/eliminar una publicación con un match activo (propuesto/confirmado_parcial) ya no lo deja huérfano ni lo borra en silencio · nuevo `_rechazar_matches_activos_de_publicacion` reutiliza `rechazar_match` (notifica a la contraparte + registra evento match_cancelled) antes de tocar los turnos · `_eliminar_matches_de_publicacion` ahora solo borra el MatchCambio si se queda sin ninguna participación, preservando el historial de rechazo · detectado analizando por qué la tasa de confirmación de matches en producción era tan baja (18%) · 8 tests nuevos + 6 tests existentes actualizados a la nueva semántica · 675 tests passing
- [x] feat(calendario): Paso 1 — servicio puro `construir_calendario_mes` (app/services/calendario_mercado.py) · agrupa TurnoAceptado (modo "ofertas") o TurnoCedido (modo "peticiones") abiertos, por fecha y franja, para tipos cambio/regalo/peticion/cambio_dia (excluye junte) · respeta visibilidad (misma categoría+grupo), excluye propias/sintéticas/no-activas/fuera de mes · clave especial "cualquiera" para turnos con cualquier_franja · 18 tests · 693 tests passing
- [x] feat(calendario): Paso 2 — ruta `GET /calendario` (app/routes/calendario.py) · navegación mensual anyo/mes igual que `/planilla` · selector ofertas/peticiones vía query param `modo` (con fallback a "ofertas" si es inválido) · plantilla mínima sin colores ni drill-down todavía (calendario/calendario.html) · blueprint registrado en app/__init__.py · 7 tests · 700 tests passing
- [x] feat(calendario): Paso 3 — grid visual mensual reutilizando `.planilla-cal`/`.cal-celda` de `/planilla` · nueva función pura `preparar_celdas_mes` (color sólido si hay 1 franja ese día, estilo "multi" neutro + tooltip con nombres si hay varias, clave especial para "cualquiera") · CSS nuevo (.calendario-modo-selector, .calendario-ayuda-texto) · catálogo i18n actualizado (pybabel extract/update/compile) · 4 tests nuevos · 704 tests passing
- [x] feat(calendario): Paso 4 — drill-down día→franja→publicaciones · nueva `resumen_publicaciones` (autor+tipo) en calendario_mercado.py · datos del mes embebidos como JSON (`<script type="application/json">`) en la página, JS vanilla navega los 3 niveles con pila de "volver" sin llamadas adicionales al servidor · panel modal deslizante (.calendario-panel) · fix de bug real: `_, num_dias = calendar.monthrange(...)` shadowaba el `_()` de flask_babel importado en el mismo módulo, rompiendo la ruta en cuanto se usó gettext · 1 test nuevo · 707 tests passing
- [x] feat(calendario): Paso 5 — el nivel franja→publicaciones enlaza directamente a `/cambios` filtrado (mes/dia/tipo_fecha/usuario/franja) en vez de reimplementar la tarjeta completa y el modal «Me interesa» dentro del calendario · decisión de diseño: reutilizar la página de búsqueda ya existente (con «Me interesa»/«Contraoferta» ya funcionales) en vez de duplicar esa lógica · nuevo test e2e (e2e/test_calendario_drilldown.py, Playwright) que ejerce el click real día→franja→enlace y detectó un bug real: `.calendario-panel { display:flex }` pisaba por especificidad CSS el `display:none` del atributo `hidden`, dejando el overlay interceptando clics aunque estuviera "oculto" · corregido con `.calendario-panel[hidden] { display:none }` · 707 tests unitarios + 1 e2e passing
- [x] feat(calendario): Paso 6 — enlace "Calendario" en el menú principal (base.html, junto a "Buscar cambios") · smoke test `test_smoke_calendario_get` · catálogo i18n actualizado · 708 tests passing. Feature completa (Pasos 1-6); modo "Juntes de noches" queda en backlog (B18)
- [x] feat(calendario): Ronda 2, Paso 1 — colores distintos por modo en el selector Ofertas/Peticiones (verde/teal vs. ámbar/naranja, sólido si activo) en vez de azul/gris genérico · solo CSS, sin test automatizado (sin lógica de negocio) · 708 tests passing
- [x] feat(publicar): Ronda 2, Paso 2 — prefill de fecha/modo en `/publicar` vía `?fecha=&modo=` · modo "ofertas" precarga el primer turno aceptado, "peticiones" el primer turno cedido · valores inválidos (fecha no-ISO o modo desconocido) se ignoran en silencio, sin prefill · 4 tests nuevos · 712 tests passing
- [x] feat(calendario): Ronda 2, Paso 3 — botón fijo "Publicar cambio" bajo el grid · cualquier día (con o sin ofertas) abre el panel de drill-down; si está vacío muestra "Nadie ha publicado nada este día todavía" + enlace a `/publicar?fecha=&modo=` precargado (usa el Paso 2) · 1 test de ruta + 1 test e2e nuevo (día vacío → enlace correcto → aterriza en /publicar con el campo precargado) · 713 tests unitarios + 2 e2e passing
- [x] feat(calendario): Ronda 2, Paso 4 — título corto "Calendario" (antes "Calendario de cambios") + icono ⓘ "¿Cómo funciona?" con banner de ayuda inline, replicando el patrón exacto de `/planilla` (mismas clases CSS `.planilla-ayuda-link`/`.planilla-onboarding-*`, mismo control por localStorage) · banner enlaza a `main.como_funciona` con anchor `#calendario` (preparado para el Paso 5) · 1 test nuevo · 714 tests unitarios + 2 e2e passing
- [x] feat(onboarding): Ronda 2, Paso 5 — nueva sección "1. Descubre cambios en el calendario" en `/como-funciona` (con `id="calendario"` para el anchor del banner del Paso 4), renumerando el resto de secciones (2→8) · 1 test nuevo (verifica orden) · 715 tests unitarios + 2 e2e passing
- [x] feat(nav): Ronda 2, Paso 6 (último) — el calendario pasa a ser la pantalla de inicio: redirect de login/registro (guard ya-autenticado + login exitoso) apunta a `calendario.index` en vez de `main.index`, logo de la cabecera y CTA final de "Cómo funciona" también · orden del menú: "Calendario" antes que "Mis cambios" · no se toca la ruta `main.index` ni sus redirects post-acción (publicar/cancelar/editar siguen llevando a "Mis cambios") · 5 tests nuevos · 720 tests unitarios + 2 e2e passing. **Ronda 2 completa (Pasos 1-6).**

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
