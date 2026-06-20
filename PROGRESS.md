# Estado del desarrollo

## Fase actual
Fase 9 — Mejoras post-MVP

## Paso actual / siguiente paso
Panel de administración implementado. 153/153 tests pasando.
Siguiente: ejecutar `flask init-admin --yes` en la consola de Railway para borrar datos y crear el admin.

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

## Notas / decisiones / asunciones pendientes
- Sin campo teléfono en ningún modelo ni formulario (decisión explícita del usuario).
- FranjaHoraria se define a nivel de GrupoDeIntercambio, no de Unidad individual.
- No se crea entidad Turno separada: fecha + franja_horaria_id se embeben directamente en turno_cedido y turno_aceptado.
- Autenticación: email + contraseña (Flask-Login + Werkzeug).
- El motor de matching se implementa como módulo puro sin acoplamiento a Flask ni SQLAlchemy.
- Los conflictos de pip (streamlit, spyder) son del sistema y no afectan al proyecto.
- conftest.py empuja un app context fresco por test para aislar g (Flask-Login) y la sesión SQLAlchemy. Necesario porque en Flask 3.x g está scoped al app context (no al request context) y Flask-Login cachea current_user en g._login_user.
