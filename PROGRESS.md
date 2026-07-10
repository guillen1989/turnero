# Estado del desarrollo

## Fase actual
Fase 9 — Mejoras post-MVP

## Paso actual / siguiente paso
B19 en marcha: "ocasiones a 4" (cadena de intercambio A→B→C→D→A), siguiendo el
mismo patrón que la cadena a 3 (B13). Paso 1 completado: motor puro
`detectar_cadena_4` en `app/matching/engine.py`. Paso 2 completado: capa de
servicio `buscar_cadenas_4_para`/`crear_match_cadena_4` (triple bucle
anidado, ciclo completo, sin sintéticas todavía) en
`app/matching/service.py` · 12 tests en `tests/test_cadena_4.py` mirroring
`test_cadena_3.py`. Paso 3 completado: `buscar_cadenas_4_para`/`crear_match_cadena_4` enganchados
en las 3 rutas que ya disparan cadena_3 (`/publicar`, editar, contraoferta
— `app/routes/publicaciones.py`) · 1 test de integración de ruta nuevo.
Siguiente paso: generalizar el badge hardcodeado `match.tipo == 'cadena_3'`
en `app/templates/main/dashboard.html` para reconocer también `cadena_4`
("¡Cambio a 4 bandas!" + CSS `.match--cadena-4`). Alcance completo de B19
(visto con el usuario):
detección + confirmación de ciclos completos de 4, sintéticas/avisos para
cadenas parciales de 4 (3 bandas reales + 1 hueco) igual que ya hace la
cadena a 3, y una preferencia de usuario para mostrar/ocultar oportunidades
a 3 y a 4 por separado en el calendario (Ofertas/Peticiones).

Fix: regenerar la unidad de demo fallaba con `ForeignKeyViolation` en
`match_cambio` (`notificacion_match_id_fkey`) porque `_borrar_demo()`
(`app/services/demo.py`) borraba `match_cambio` antes que `notificacion`,
y `notificacion.match_id` tiene FK a `match_cambio.id`. En producción, los
matches reales de la unidad demo generan notificaciones (`nuevo_match`,
etc. — `app/matching/service.py`) que sobreviven al primer reset; al
regenerar de nuevo, esas notificaciones huérfanas bloqueaban el borrado.
Corregido el orden: `notificacion` se borra antes que
`match_participacion`/`match_cambio`. Test de regresión añadido en
`tests/test_demo.py::test_reset_demo_con_notificaciones_de_match_pendientes`
(crea una notificación con `match_id` tras el primer `reset_demo()` y
verifica que el segundo no lanza la excepción). 805 tests passing.

Fix de producción: `SQLALCHEMY_ENGINE_OPTIONS` con `pool_pre_ping=True` +
`pool_recycle=280` en `ProductionConfig` — Railway cierra conexiones
ociosas a Postgres y el pool por defecto reutilizaba conexiones muertas,
provocando `SSL SYSCALL error: EOF detected` en `/auth/login` y otras
rutas (visto en logs de Railway). 776 tests passing.

B18 rediseñado: el modo "Juntes de noches" del calendario pasó de un grid
día-a-día (como Ofertas/Peticiones) a filas por semana natural con la
distribución trabaja/libra desplegable (ver más abajo, rama
`feat/calendario-juntes-semanas` sobre `staging`, push directo pedido por
el usuario). Motivo: un junte es un patrón semanal completo, no una noche
suelta — un mockup (Artifact) se validó con el usuario antes de implementar.

Botón "Probar con una cuenta demo" añadido también en la portada (`/`,
`main.index`), junto a "Crear cuenta"/"Entrar" (antes solo estaba en
`/auth/login`) — mismo flag `demo_login_enabled` (`DEMO_LOGIN_EMAIL`
configurada), mismo endpoint `auth.login_demo`.

`APP_BASE_URL` en staging: al probar el feedback en staging tras el fix de
producción, el email volvió a rebotar — el enlace usaba
`turnero-staging.up.railway.app` (mismo problema que producción, staging
nunca tuvo dominio propio). Corregido igual que producción: dominio
`staging.turnero.xyz` añadido en Railway (servicio `turnero`, entorno
`staging`) y `APP_BASE_URL=https://staging.turnero.xyz` configurada en ese
servicio. Importante: NO apuntar `APP_BASE_URL` de staging a
`app.turnero.xyz` (el de producción) — el email quedaría enlazando a la
app de producción con tokens/datos de la BD de staging, rota. Pendiente
de acción manual del usuario (no lo puede hacer el agente): añadir en el
DNS de `turnero.xyz` el `CNAME staging → ezh8vdkw.up.railway.app` y el
`TXT _railway-verify.staging → railway-verify=03ea54e3d41023334f9b4de5d77f467d20e0c8a4f159b483a68e7b28b8f7ab79`.

Añadido `APP_BASE_URL` + dominio propio `app.turnero.xyz` (ver más abajo).
Pendiente de acción manual del usuario (no lo puede hacer el agente): crear
en el DNS de `turnero.xyz` el registro `CNAME app → hfdey1z5.up.railway.app`
y el `TXT _railway-verify.app → railway-verify=4bcf313781d937050c193da1180bb73a1f3c44d36b20420277a63d57e1817b98`
(dado por `railway domain app.turnero.xyz`), y una vez verificado el dominio
en Railway, configurar `APP_BASE_URL=https://app.turnero.xyz` como variable
de entorno en production. Hasta entonces `url_absoluta()` usa el host de la
petición entrante como antes (sin romper nada).

Pendiente de acción manual del usuario (no lo puede hacer el agente):
crear cuenta en resend.com, verificar un dominio propio en
resend.com/domains, generar una API key, y configurar `RESEND_API_KEY` y
`RESEND_FROM_EMAIL` como variables de entorno en Railway (production y
staging). Hasta entonces, `enviar_email()` detecta la ausencia de
`RESEND_API_KEY`, no intenta conectar, registra un warning y devuelve
`False` sin romper el flujo — el fallback manual de admin
(`/admin/feedback/<id>/restablecer-contrasena`) sigue disponible.

Siguiente: decidir el próximo punto del backlog.

Nota: `e2e/test_sintetica_staging.py` apunta a la app real de Railway
(STAGING_URL) y no se ejecuta salvo necesidad explícita, para no seguir
escribiendo usuarios de prueba en la base de datos compartida de staging.

Análisis de datos de producción (2026-07-08): de 361 publicaciones tipo
`cambio`, 137 son reales y 224 sintéticas (oportunidad a 3 detectada); de
esas 224, ninguna había terminado en match confirmado y solo 1 tenía un
"me interesa" registrado. Causa raíz: `crear_pub_sintetica()` no disparaba
ninguna notificación proactiva a terceros, y el aviso a los dos usuarios
originales enlazaba a un callejón sin salida. Arreglos aplicados:
- La sintética ahora pasa por `notificar_busquedas_guardadas()` al
  crearse, igual que cualquier publicación normal.
- El aviso `aviso_oportunidad_3` en `/avisos` enlaza al panel (dashboard,
  donde ya vive la sección "oportunidades a 3") en vez de al listado
  filtrado por el nombre del otro usuario original.
Se descartó una tercera solución (re-escanear candidatas reales ya
existentes contra sintéticas nuevas de forma retroactiva): el caso que
resolvía es poco frecuente y el aviso a terceros ya cubre el hueco real,
así que añadir esa lógica era sobre-ingeniería para el problema real.

## Backlog (fuente: .backlog)
- [x] B18: Calendario visual — modo visor "Juntes de noches" (además de Ofertas/Peticiones) ✓
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
- [x] fix(e2e): fixture compartido `usuario` sin `onboarding_visto=True` (redirigía a /como-funciona en vez de a la pantalla de inicio) + `_login` de `test_sintetica_golden_path.py` actualizado a `/calendario/` tras el Paso 6 + aserciones obsoletas de `aviso_interes`/"Interés parcial" reescritas al aviso combinado `aviso_oportunidad_3` actual · 9/9 tests e2e locales passing (`test_sintetica_staging.py` deliberadamente no ejecutado, apunta a Railway real)
- [x] feat(calendario): bandas de color por franja en días con varios tipos distintos — `preparar_celdas_mes` genera un `linear-gradient` de cortes duros (una banda de igual ancho por franja, ordenadas por `hora_inicio`, sin transición) en vez del color neutro anterior · tope de 4 franjas distintas antes de caer al tratamiento neutro con nº de tipos (más bandas serían ilegibles en ~40px) · sin etiqueta superpuesta en el caso de bandas (el propio patrón de color ya informa) · 4 tests nuevos + 1 actualizado · 723 tests unitarios + 9 e2e passing
- [x] fix(calendario): `_gradiente_bandas` devolvía `linear-gradient(...)` suelto, sin el prefijo `background:` ni el `;` final — CSS inválido que el navegador descarta en silencio, dejando la celda en blanco/negro por defecto en vez de con las bandas de color. Detectado por el usuario probando en staging (confirmado leyendo en solo lectura la BD de staging y ejecutando las funciones reales contra datos reales del 20 de septiembre). Corregido devolviendo la declaración CSS completa (`background: linear-gradient(...); color: #ffffff;`) · test reforzado para comprobar el formato exacto de la declaración, no solo que contuviera las palabras · 723 tests unitarios + 9 e2e passing
- [x] feat(calendario): letra por banda además del color — sustituido el `linear-gradient` de una sola celda por sub-elementos independientes (`celda.bandas`: lista de {color, letra}, uno por franja, ordenados por hora_inicio), cada uno con su color sólido y su inicial (o "?" para "cualquier turno") · más fiable que superponer texto sobre un gradiente CSS · nuevas clases `.cal-bandas-row`/`.cal-banda` · tests reescritos para comprobar la lista de bandas en vez del string de gradiente · 723 tests unitarios + 9 e2e passing
- [x] fix(calendario): color de texto por banda en vez de blanco fijo — al pensar en turnos personalizados (que reciclan la misma paleta que los de serie) se detectó que un color claro de la paleta (amarillo `#EAB308`, cian `#06B6D4`) dejaría la letra casi ilegible en blanco. `celda.bandas` ahora lleva también `color_texto` (mismo cálculo de brillo que ya usa el caso de una sola franja) · 1 test de regresión nuevo · 724 tests unitarios + 9 e2e passing
- [x] feat(calendario): oportunidades a 3 bandas (publicaciones sintéticas) incluidas en el calendario — se quita el filtro `es_sintetica.is_(False)` de `_candidatas` (tienen tipo 'cambio' y sus turnos ya están orientados desde la perspectiva del tercer usuario, así que encajan sin más en el mapeo ofertas/peticiones existente) · `resumen_publicaciones` devuelve también `es_sintetica`, y la ruta usa esa marca para etiquetarlas como "Oportunidad a 3" en el drill-down en vez de la etiqueta genérica de tipo · 4 tests nuevos (2 servicio + 1 resumen + 1 ruta) · 727 tests unitarios + 9 e2e passing
- [x] feat(calendario): salto directo a publicaciones cuando el día solo tiene un tipo de turno — se ahorra el paso intermedio de elegir franja (pendiente desde la fase de planificación, nunca se había implementado) · de paso se detectó y corrigió otro caso del bug de especificidad CSS `[hidden]`: `.btn { display: inline-block }` pisaba el `display:none` implícito del atributo `hidden` en el botón "Volver", dejándolo siempre visible · arreglado con `.btn[hidden] { display: none }`, igual que se hizo antes con `.calendario-panel[hidden]` · 1 test e2e nuevo + 1 actualizado · 727 tests unitarios + 10 e2e passing
- [x] Integrar pytest e2e/ en el ciclo de CI/CD de Railway (GitHub Actions o similar) ✓
- [x] Añadir APP_URL al .env local y smoke test integrado en GitHub Actions post-deploy ✓
- [x] fix(admin): la contraseña temporal al restablecer cuenta desde el panel de feedback ya no se muestra en un flash message (el admin reportó que no lo veía) · ahora se envía como `Notificacion` tipo `contrasena_restablecida` (nuevo campo `mensaje` en el modelo, migración `9310c6bbcb55`) al usuario afectado, visible en /avisos y contando en el badge de la campana · 5 tests nuevos
- [x] feat(push): aviso push a todos los administradores (`es_admin=True`) al crearse cualquier Feedback (formulario de contacto o solicitud de recuperación) · las solicitudes de recuperación de contraseña van marcadas como urgentes (cabecera `Urgency: high` en `enviar_push`, nuevo parámetro `urgente`) · 5 tests nuevos
- [x] fix(calendario): oportunidades a 3 mostradas al revés (ofertas↔peticiones) — reportado por el usuario en producción (turno del 6/8 de Victoria). Causa: `crear_pub_sintetica()` guarda como `turno_cedido` de la sintética el ACEPTADO real de pub_a (una oferta) y como `turno_aceptado` el CEDIDO real de pub_b (una petición) — necesario para el matching de la cadena a 3 (`buscar_sinteticas_que_coinciden_con` compara cedido-con-cedido y aceptado-con-aceptado del mismo día, no en cruce). `construir_calendario_mes` aplicaba a las sintéticas el mismo mapeo genérico que a las publicaciones normales (`turno_cedido`→peticiones, `turno_aceptado`→ofertas), mostrándolas invertidas. Corregido separando candidatas normales/sintéticas y consultando la tabla contraria para las sintéticas. Verificado contra producción (Railway, solo lectura) antes de tocar código: pub 785 de Victoria (real) correcta en peticiones; sintéticas 787/789/790 con esa misma noche mal clasificada en ofertas, confirmando la hipótesis. Los dos tests que fijaban el comportamiento anterior como correcto se corrigieron + 1 test de regresión nuevo que reproduce el caso real vía `crear_pub_sintetica()` · 732 tests unitarios passing
- [x] feat(email): servicio de envío vía Resend HTTPS API (`app/services/email.py`) — Railway bloquea los puertos SMTP salientes en el plan Hobby (confirmado con la documentación oficial y varios hilos del foro), así que el reintento con Gmail SMTP se descarta a favor de una API HTTPS, que no está bloqueada. `enviar_email()` nunca lanza: sin `RESEND_API_KEY` configurada, sin conexión o con respuesta de error, registra y devuelve `False` en vez de tumbar el flujo que lo llama. Config `RESEND_API_KEY`/`RESEND_FROM_EMAIL`; limpieza del bloque `MAIL_*` de Flask-Mail en `config.py`, que llevaba muerto desde que se eliminó esa dependencia en el commit `5c05ea4` y nadie lo había limpiado · 4 tests
- [x] feat(auth): modelo y migración `PasswordResetToken` (token de un solo uso, hash SHA-256 en BD, expiración a 60 min) · columnas `fecha_creacion`/`fecha_expiracion` declaradas `timezone=True` a propósito: con `TIMESTAMP` naive, la sesión local de Postgres (`Europe/Madrid`) reinterpreta el datetime aware UTC como hora local al guardarlo, desplazando la expiración ~2h y rompiendo la comparación tras un commit/recarga — detectado por un test que fallaba de forma intermitente
- [x] feat(auth): servicio `password_reset.py` — `generar_token_reset`/`obtener_usuario_por_token`/`consumir_token`, invalida cualquier token anterior sin usar del mismo usuario al generar uno nuevo · 8 tests
- [x] feat(auth): recuperación de contraseña self-service — sustituye el flujo manual (el usuario pedía por un ticket de feedback y el admin generaba una contraseña temporal a mano) por `/auth/recuperar-contrasena` + `/auth/restablecer-contrasena/<token>`, con el mismo mensaje de éxito exista o no el email (anti-enumeración) y envío del enlace por email vía Resend · el reseteo manual de admin (`/admin/feedback/<id>/restablecer-contrasena`) se mantiene como fallback si el email no llega · 12 tests · 758 tests passing
- [x] feat(feedback): email a todos los admins (además del push ya existente) cuando llega un feedback nuevo de tipo error/sugerencia · excluye a propósito el tipo `recuperacion`, que ya está cubierto por el flujo self-service y solo queda como fallback manual poco frecuente · reutiliza la misma consulta de admins que ya usaba el push · 5 tests
- [x] feat(demo): amplía el contenido de la unidad de demostración (`app/services/demo.py`), que se notó demasiado escasa en producción · bots 5→20 · publicaciones abiertas de bots generadas a partir de plantillas cicladas en 4 rondas (7→28) · matches `confirmado_total` entre bots 1→4 (nuevo helper `_match_confirmado_total`) · `_sembrar_planillas` generalizado para dar planilla a todos los usuarios (antes hardcodeado a 8) en vez de dejar sin planilla a los bots nuevos · cuentas demo (Ana/Carlos/Elena) y sus escenarios de match sin cambios · 4 tests nuevos · 776 tests passing
- [x] fix(db): `SQLALCHEMY_ENGINE_OPTIONS` con `pool_pre_ping=True` + `pool_recycle=280` en `ProductionConfig` — Railway cierra conexiones ociosas a Postgres, el pool por defecto (sin ping) reutilizaba conexiones muertas y causaba `SSL SYSCALL error: EOF detected` en `/auth/login` y otras rutas (visto en logs de producción) · sin test dedicado (config de infraestructura, no lógica de negocio) · 776 tests passing
- [x] feat(admin): panel de Analytics — scroll horizontal en el gráfico de líneas existente (contenedor con ancho fijo `nº puntos × 44px` dentro de `overflow-x:auto`, sin forzar scroll si el contenido cabe) + segundo gráfico de barras con desplegable de un único indicador (cambios publicados, matches, cambios eliminados, planillas publicadas, clics «Me interesa», confirmados, activos acumulados) y su propia granularidad día/semana/mes · nuevas series temporales `eliminadas` (`AuditEliminacion.fecha`) y `planillas_publicadas` (nuevo `Event` `planilla_publicada`, registrado en `POST /planilla/<a>/<m>/publicar`) añadidas a `/admin/analytics/data` · paleta de las 2 series nuevas validada con el script de la skill dataviz (teal `#0d9488` / dorado `#a16207`, 8 colores categóricos, todos los checks en PASS) · bug real de layout encontrado y corregido de paso: `.admin-layout { align-items: flex-start }` en el breakpoint móvil (`flex-direction: column`) hacía que `.admin-content` se dimensionara por su contenido en vez de por el contenedor, rompiendo cualquier `overflow-x` de un descendiente — corregido con `align-items: stretch` solo dentro de esa media query · verificado con Playwright headless (móvil 500px con scroll contenido + escritorio 1280px sin overflow, selector de métrica e granularidad probados con datos reales insertados y luego limpiados de la BD de desarrollo local) · 6 tests nuevos · 763 tests passing
- [x] fix(datos): columna `notificacion.mensaje` ausente en la BD de `staging` pese a que `alembic_version` ya marcaba el head correcto — la migración `9310c6bbcb55` (main) se insertó en el historial *después* de que `staging` ya hubiera llegado a la revisión siguiente (`6085c41640ba`, password reset), así que al fusionar ambas ramas Alembic vio "ya estoy en head" y nunca ejecutó su `ALTER TABLE` en staging, aunque el código (y producción, desplegada en otro orden) ya esperaban la columna — causaba un 500 en cualquier página que tocara `Notificacion` (detectado por el usuario en GlitchTip tras una prueba manual de feedback). Diagnosticado comparando `alembic_version` y el esquema completo (`information_schema.columns`) de ambas bases vía `railway` CLI + `psql` de solo lectura; corregido aplicando en staging el mismo `ALTER TABLE notificacion ADD COLUMN mensaje TEXT` que la migración habría ejecutado (columna nullable, sin tocar `alembic_version` porque ya apuntaba al head correcto) · esquemas de producción y staging verificados idénticos tras el fix
- [x] feat(feedback): email a todos los admins cuando llega un feedback nuevo (`/feedback`), complementando el aviso push existente — el push depende de que el admin tenga la suscripción activa en ese navegador/dispositivo, el email siempre llega · reutiliza `enviar_email` (Resend) y el patrón de plantilla HTML de `email/recuperar_password.html` · nueva plantilla `email/nuevo_feedback.html` (tipo, contacto si lo hay, descripción, enlace a `/admin/feedback`) · 2 tests nuevos
- [x] feat(calendario): B18 — tercer modo "Juntes de noches" en el calendario visual, junto a Ofertas/Peticiones · a diferencia de esos dos modos (donde cedido/aceptado son direccionales y `construir_calendario_mes` elige un único modelo), en un junte cedido y aceptado son las dos caras de la misma permuta semanal, así que el modo `juntes` combina ambas tablas en vez de elegir una · nueva entrada `"juntes": ("junte",)` en `_TIPOS_POR_MODO` · añadida la etiqueta `junte` que faltaba en `tipo_labels` de la ruta (antes se colaba el tipo crudo en el drill-down) · tercer botón morado en el selector (`--juntes`, a juego con el `#9333ea` que ya usa "cualquier franja") · JS `_urlPublicacion` no fija `tipo_fecha` en modo juntes (no direccional; `/cambios` ya hace el OR correcto) · catálogo i18n actualizado (pybabel extract/update/compile) · 7 tests nuevos (servicio + ruta) · 779 tests passing · rama `feat/calendario-juntes-noches` sobre `staging`
- [x] fix(email): los avisos de feedback a `guillen@delbarrioblanco.net` rebotaban en producción (`last_event: bounced` en Resend) — diagnosticado enviando pruebas directas a la API de Resend: un email con enlace a `*.up.railway.app` rebota siempre (con o sin HTTPS), uno sin ese enlace se entrega bien, así que el filtro de correo del destinatario bloquea específicamente los enlaces al dominio compartido de Railway, no el envío en sí. Añadido `url_absoluta()` en `app/services/email.py` (usa `APP_BASE_URL` si está configurada, si no cae al `url_for(_external=True)` de siempre) y aplicado a los dos enlaces salientes existentes (aviso de feedback y recuperación de contraseña). Se añade el dominio propio `app.turnero.xyz` como custom domain en Railway (`web-production-0f001.up.railway.app` se deja intacto y sigue sirviendo el mismo servicio sin redirección: los usuarios que ya instalaron la PWA desde ese origen no pueden "migrarse" a otro origen, es una limitación del propio modelo de PWA) · 2 tests nuevos
- [x] feat(calendario): rediseño del modo "Juntes de noches" — de grid día-a-día a filas por semana con distribución trabaja/libra desplegable, tras validar un mockup (Artifact) con el usuario · nuevo módulo `app/services/junte_semanal.py` (`calcular_distribucion`, `resumen_textual`, `lista_es`, `DIAS_CORTOS`), compartido entre `main.py::_junte_info` (WA/resumen en /cambios y /dashboard) y el calendario — elimina la duplicación de la lógica LMVD/MJS que antes vivía solo en `main.py` · el cálculo del lunes de la semana pasa de "primer turno_cedido insertado" a `min()` de todas las fechas del junte (más robusto, mismo resultado en todos los casos reales) · revertido el soporte de `construir_calendario_mes`/`_TIPOS_POR_MODO` para `modo="juntes"` (quedaba como código muerto tras el rediseño: ya no lo llama la ruta) · nuevas `construir_semanas_juntes`/`preparar_semanas_juntes` en `calendario_mercado.py`: agregan por lunes natural en vez de por día, generan la tira de 7 días (trabaja=verde/libra=naranja, mismos colores que Ofertas/Peticiones) y marcan semanas parciales (a caballo entre meses) · plantilla con `<details>/<summary>` nativo (sin JS) para el desplegable por semana; el grid+JS de drill-down de ofertas/peticiones queda intacto, solo se salta para `modo=juntes` · enlace "Ver publicación" usa `/cambios?pub_id=` (ya soportado) en vez del flujo día+franja+usuario de ofertas/peticiones · catálogo i18n actualizado · 10 tests nuevos (`test_junte_semanal.py`, `test_calendario_semanas_juntes.py`) + 2 tests de ruta reescritos · verificación afectada por sesiones concurrentes compartiendo la BD Postgres local de test (deadlocks/errores de sesión ajenos a este cambio); los ficheros de test relevantes (junte_semanal, calendario_mercado, calendario_ruta, calendario_semanas_juntes, combinaciones_match, cambios, dashboard, publicar_junte) pasan limpios en ventanas sin contención · rama `feat/calendario-juntes-semanas` sobre `staging`, push directo pedido por el usuario
- [x] feat(auth): botón "Probar con una cuenta demo" también en la portada (`main.index`, `/`), junto a "Crear cuenta"/"Entrar" — antes solo estaba en `/auth/login`. `main.index` calcula `demo_login_enabled` igual que la vista de login (`bool(DEMO_LOGIN_EMAIL)`) y la plantilla añade el mismo `<form>`/botón dentro del `.btn-group` existente, sin bloque nuevo (verificado visualmente con Playwright en 420px y 1200px: el botón queda alineado junto a los otros dos, con estilo `btn-secondary` para distinguirlo como acción alternativa) · 2 tests nuevos

## Notas / decisiones / asunciones pendientes
- Sin campo teléfono en ningún modelo ni formulario (decisión explícita del usuario).
- FranjaHoraria se define a nivel de GrupoDeIntercambio, no de Unidad individual.
- No se crea entidad Turno separada: fecha + franja_horaria_id se embeben directamente en turno_cedido y turno_aceptado.
- Autenticación: email + contraseña (Flask-Login + Werkzeug).
- El motor de matching se implementa como módulo puro sin acoplamiento a Flask ni SQLAlchemy.
- Los conflictos de pip (streamlit, spyder) son del sistema y no afectan al proyecto.
- conftest.py empuja un app context fresco por test para aislar g (Flask-Login) y la sesión SQLAlchemy. Necesario porque en Flask 3.x g está scoped al app context (no al request context) y Flask-Login cachea current_user en g._login_user.
