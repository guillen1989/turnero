❯ puedes auditar también la escalabilidad de la app? para escenarios de 1.000 usuarios, 100.000 usuarios y 1.000.000

● I'll investigate the codebase's architecture — DB access patterns, deployment config, background work, and file/session handling — to
  ground the audit in what's actually there rather than generic advice.

  Searched for 5 patterns, read 2 files, ran 4 shell commands (ctrl+o to expand)
  ⎿  Referenced file PROGRESS.md
  ⎿  Referenced file translations/es/LC_MESSAGES/messages.po
  ⎿  Read tests/test_i18n.py (121 lines)
  ⎿  Read app/models/planilla.py (174 lines)
  ⎿  Read app/routes/planilla_supervision.py (144 lines)
  ⎿  Skills restored (security-review)
  Ran 1 shell command (ctrl+o to expand)

● Confirmed: enviar_email() is fully synchronous — requests.post with a 10s timeout blocks the gunicorn worker for the entire request. No
  threading wrapper like the push sender has. Now checking the publish request flow and DB indices.

  Searched for 3 patterns, read 1 file (ctrl+o to expand)

● Good, the key matching-filter columns are already indexed. Now let me check the other perf-related commits and static asset serving
  config.

  Searched for 2 patterns, ran 1 shell command (ctrl+o to expand)

● Auditoría de escalabilidad — 1.000 / 100.000 / 1.000.000 usuarios

  Hallazgo positivo clave (contexto para todo lo demás)

  El motor de matching está particionado naturalmente por categoria_id + grupo_intercambio_id, no por el total de usuarios del sistema:

  # app/matching/service.py — _candidatas_base()
  .filter(
      ...
      Usuario.categoria_id == propietario.categoria_id,
      Unidad.grupo_intercambio_id == grupo_id,
  )

  Las búsquedas combinatorias buscar_cadenas_3_para (O(n²)) y buscar_cadenas_4_para (O(n³)) en app/matching/engine.py, invocadas de forma
  síncrona en app/routes/publicaciones.py:306-312, 401-407, 624-630, iteran solo sobre publicaciones abiertas del mismo grupo/unidad, no de
  toda la plataforma. Los índices que sostienen este filtro ya existen (migrations/versions/285a7610df2f_...py: ix_usuario_categoria_id,
  ix_unidad_grupo_intercambio_id, ix_publicacion_cambio_estado/tipo/usuario_id/es_sintetica). Esto significa que 1M usuarios repartidos en
  muchos grupos pequeños no degradan el matching — el tamaño real del problema es "cuántas publicaciones abiertas simultáneas hay en un
  mismo grupo de intercambio", que no crece con el total de usuarios de la plataforma. Este diseño no necesita cambiarse en ningún escenario
  de escala; es la base sobre la que se apoya el resto del análisis.

  Sesiones vía cookie firmada (Flask-Login, sin almacén de sesión en servidor) → capa web sin estado, escalable horizontalmente sin cambios.

  ---
  1.000 usuarios — sin riesgo real

  La arquitectura actual (3 workers síncronos de gunicorn, Postgres directo, email/PDF síncronos) sostiene esta escala sin problema. El
  único riesgo latente es que un envío de email lento coincida con otro tráfico y bloquee temporalmente 1 de los 3 workers (ver abajo), pero
  a este volumen la probabilidad de que eso afecte a un usuario real es marginal.

  100.000 usuarios — el techo de concurrencia empieza a notarse

  - Procfile: gunicorn --workers 3 --timeout 60 run:app — sin --threads ni worker class async: solo 3 peticiones concurrentes por dyno en
  todo el sistema. Este es el primer cuello de botella real a esta escala.
  - enviar_email() es completamente síncrono (app/services/email.py:34-60, timeout de 10s vía requests.post a Resend), invocado dentro del
  ciclo de petición en app/routes/auth.py:229 (recuperar contraseña), app/services/documento_cambio.py:85 (hoja completa) y
  app/routes/feedback.py:51. Una respuesta lenta de Resend bloquea 1 de los 3 workers hasta 10s — con más tráfico esto se convierte en un
  riesgo concreto de agotar la capacidad del dyno. Contraste: los avisos push sí van en hilo aparte (app/push/sender.py:252,
  threading.Thread(daemon=True)) — el email debería seguir ese mismo patrón como mínimo.
  - Pool de conexiones a Postgres sin ajustar: config.py solo fija pool_pre_ping/pool_recycle, sin pool_size/max_overflow explícitos →
  default de SQLAlchemy (5+10=15) por proceso worker. Con 3 workers son hasta 45 conexiones desde un solo dyno; hay que verificar contra el
  límite de conexiones del plan de Postgres en Railway antes de escalar el número de workers/dynos.
  - Generación de PDF con xhtml2pdf ocurre en el propio request — coste de CPU no trivial que empieza a notarse con más tráfico concurrente.
  - Matching: sigue bien mientras el tamaño de cada grupo de intercambio se mantenga en decenas/pocas centenas de publicaciones abiertas
  simultáneas (no es función del total de usuarios, ver arriba).

  1.000.000 usuarios — requiere cambios estructurales

  - Falta una cola de tareas en segundo plano (no hay Celery/RQ/Redis en requirements.txt): email, generación de PDF y, en menor medida,
  push, deberían salir del ciclo request/response. Este es el cambio de mayor impacto — sin él, cualquier aumento de workers/dynos solo
  desplaza el problema.
  - Pooler de conexiones obligatorio (PgBouncer o equivalente gestionado): la aritmética workers × pool ya no encaja en una sola instancia
  de Postgres a este volumen de tráfico concurrente.
  - Con más carga de lectura (dashboards, listados), considerar réplicas de lectura; el motor de matching en sí no lo necesita gracias al
  particionado por grupo.
  - Assets estáticos: no hay static_url_path/CDN configurado — Flask los sirve directamente. A este volumen conviene un CDN delante, aunque
  no es un problema de correctitud, solo de coste/latencia.
  - El particionado por grupo_intercambio_id sigue siendo la razón por la que el motor de matching no necesita rediseño a este volumen — es
  la propiedad de diseño a preservar en cualquier cambio futuro.

  ---
  Nota menor, no bloqueante: Procfile ejecuta flask db upgrade && flask seed-demo en cada arranque de dyno. seed-demo
  (app/__init__.py:272-292) ya es idempotente (comprueba antes de sembrar) y Alembic serializa db upgrade de forma segura entre procesos
  concurrentes, así que no es un riesgo hoy con 1 dyno — pero conviene revisarlo si en el futuro se escala horizontalmente a varios dynos
  arrancando a la vez.

✻ Brewed for 5m 22s

