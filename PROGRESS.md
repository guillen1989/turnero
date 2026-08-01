# Estado del desarrollo

## Fase actual
Fase 13 — Usuarios normales en varios servicios (unidades). Plan completo en
`docs/USUARIOS_MULTI.md`. **Cerrada.**

## Paso actual / siguiente paso
Fase 13 cerrada. Pendiente para una fase futura: los 21 casos MUST change
de la auditoría del Paso 5 (publicaciones.py, busquedas.py, unidad.py,
documento_cambio.py) y la verificación manual en navegador de los Pasos 4, 5
y 6.

## Últimos pasos completados
- [x] Paso 8 (`docs/USUARIOS_MULTI.md`) — Documentación y cierre. Eliminadas
  importaciones muertas en `app/routes/auth.py` (`encontrar_o_crear_pais`,
  `encontrar_o_crear_provincia`, `encontrar_o_crear_ciudad`, no usadas en ese
  módulo). Suite completa de tests en verde (excepto fallos preexistentes por
  compatibilidad Python 3.8/OpenSSL en generación de PDFs). PROGRESS.md y
  USUARIOS_MULTI.md actualizados reflejando el cierre de la fase.
- [x] Paso 7 (`docs/USUARIOS_MULTI.md`) — Web Push: incluir unidad en el
  payload. `enviar_push()` y `enviar_push_condicional()` aceptan
  `unidad_nombre=None`. Si se proporciona y el usuario pertenece a más de una
  unidad, se añade `[Unidad]` al cuerpo de la notificación push. Actualizados
  los 7 callers: `matches.py` (4), `publicaciones.py` (1),
  `busquedas_guardadas.py` (1) y `documento_cambio.py` (1). 4 tests nuevos en
  `test_push.py`, todos en verde; suite completa de los servicios afectados
  (push, matches, publicaciones, busquedas, documento_cambio, flujos) pasa sin
  regresiones.
- [x] Paso 6 (`docs/USUARIOS_MULTI.md`) — notificaciones con unidad de
  origen + bandeja única. Añadido `unidad_id` (FK NOT NULL) al modelo
  `Notificacion`, migración en 3 pasos, 15 sitios de creación actualizados
  para registrar la unidad de origen. Plantilla `avisos.html` muestra el
  nombre de la unidad junto a cada aviso solo si el usuario pertenece a más
  de una. `_colegas_del_usuario()` considera todos los pares
  (grupo_intercambio_id, categoria_id) de todas las unidades del usuario.
  8 tests nuevos en `test_notificacion_unidad.py`; 27 tests existentes
  adaptados al nuevo campo obligatorio.
- [x] Paso 5 (`docs/USUARIOS_MULTI.md`) — selector de unidad activa en
  `/calendario`, `/cambios`, `/planilla`. `unidad_activa_o_403` ahora
  persiste en sesión (`session["unidad_activa_id"]`) cuando se elige una
  unidad explícitamente por query param. Las 3 rutas sustituyen
  `current_user.unidad`/`grupo_intercambio`/`categoria_id` por la unidad
  activa y su categoría. `calendario_mercado.py` (`_candidatas`,
  `construir_calendario_mes`, `construir_semanas_juntes`) acepta ahora
  `categoria_id` y `grupo_id` opcionales para filtrar por la unidad
  activa. `planilla.py` recibe `unidad_id` en todas las rutas (GET y
  POST) y valida las franjas contra el grupo de la unidad activa.
  Plantillas: `<select onchange=...>` en `calendario.html`,
  `cambios.html` y `planilla.html`, visible solo si el usuario pertenece
  a más de una unidad. 16 tests nuevos en `tests/test_unidad_activa_rutas.py`,
  todos en verde. **Auditoría de 41 referencias a `current_user.unidad`/
  `categoria_id`/`grupo_intercambio` completada:** 21 casos MUST change en
  `publicaciones.py`, `busquedas.py`, `unidad.py` y `documento_cambio.py`
  quedan pendientes de implementación (ver `docs/USUARIOS_MULTI.md`).
- [x] Paso 3 (`docs/USUARIOS_MULTI.md`) — alta de cuenta con segundo servicio
  opcional: `registrar_usuario` acepta `unidades_extra` (lista de dicts con
  hospital, unidad, categoría) y construye `{unidad_id: categoria_id}` para
  `sincronizar_unidades`, sembrando la membresía principal + las extra en una
  misma transacción. El formulario `RegistroForm` gana `BooleanField
  extra_servicio` + campos prefijados `extra_*` (hospital, unidad, categoría,
  geo). La ruta `registro` extrae el helper `_nombres_geo_registro(prefijo)` y
  valida el bloque extra con sus propios mensajes de error. Plantilla
  `registro.html` con checkbox "Añadir otro servicio" que revela una segunda
  cascada completa (`extra-pais-select`...). `cascade-hospital.js` generalizado
  a `inicializarCascada(prefix)` para reutilizarse con `''` y `'extra-'`.
  `eliminar_usuario_admin` limpia también filas de `usuario_unidad`.
  152 tests en verde.
- [x] Paso 2 (`docs/USUARIOS_MULTI.md`) — migración Alembic
  `migrations/versions/def6b117664c_añade_tabla_usuario_unidad.py`:
  `op.create_table('usuario_unidad')` con PK compuesta `(usuario_id,
  unidad_id)`, FKs a `usuario.id`, `unidad.id` y `categoria.id`,
  `categoria_id NOT NULL`; backfill `INSERT INTO usuario_unidad ...
  SELECT id, unidad_id, categoria_id FROM usuario` que siembra la membresía
  de la unidad principal de cada usuario existente; `downgrade()` simétrico
  (`op.drop_table`). `flask db heads` → 1 head (`def6b117664c`). Migración
  aplicada en local y verificada con ciclo downgrade→upgrade (el backfill
  siembra correctamente). `flask db check` confirma sin drift.
  Suite de modelos del paso 1: 20 tests en verde.
- [x] Paso 1 (`docs/USUARIOS_MULTI.md`) — modelo de datos `usuario_unidad`:
  `app/models/usuario_unidad.py` (PK compuesta `(usuario_id, unidad_id)` +
  `categoria_id NOT NULL`), relaciones `Usuario.unidades` /
  `Usuario.membresias_unidad` / `Unidad.miembros` / `Unidad.membresias_unidad`
  (con `overlaps` declarados para silenciar los avisos de SQLAlchemy), y
  servicio `app/services/unidad_usuario.py` con `unidades_de` (siempre
  incluye la principal, ordenada por nombre), `categoria_en_unidad` (global
  en la principal, de la membresía en el resto), `pertenece_a`,
  `unidad_activa_o_403` (query param > sesión > principal) y
  `sincronizar_unidades` (dict `{unidad_id: categoria_id}`, actualiza la
  categoría de `usuario.categoria_id` con la de la principal, no permite
  eliminar la principal). Tests: `tests/test_models_usuario_unidad.py` y
  `tests/test_servicio_unidad_usuario.py` (20 tests en verde).
- [x] Paso 8 (`docs/PLAN_3.md`) — revisión final y UAT: UAT-7.1 a 7.4
  (detección de la cadena por el motor de matching) ya cubiertos por
  `tests/test_motor_matching.py`, `tests/test_integracion_matching.py`,
  `tests/test_pub_sintetica.py` y `tests/test_sintetica_4.py`; la
  generación de la hoja de cambio cadena_3 (alcance de este plan) cubierta
  por `tests/test_servicio_documento_cambio.py`,
  `tests/test_documento_cambio_desde_match.py`,
  `tests/test_documento_cambio_creacion.py`, `tests/test_cadena_3.py` y
  `tests/test_confirmar_con_documento.py`. Suite completa
  (`anaconda3/bin/python3 -m pytest`) en verde. PDF real de una cadena_3
  generado con datos ficticios y revisado visualmente: los 3 participantes
  aparecen, los paréntesis `(lo trabaja <nombre>)` resuelven al usuario
  correcto y el solape del tercer compañero es el esperado.
- [x] Paso 7 (`docs/PLAN_3.md`) — `app/routes/documento_cambio.py` +
  `app/templates/documento_cambio/nuevo.html`: nueva opción `cadena_3` en
  el selector de tipo; rama `elif tipo == "cadena_3":` en `nueva()` que
  recoge `tercero_id`, `turno_companero_cede_fecha/franja_id` (reutilizando
  `turno_cede_*`/`turno_recibe_*` para lo que cede/recibe el creador) y
  llama a `crear_documento_cambio_cadena_3`. Validaciones: tercero
  seleccionado y distinto del compañero, franjas y fechas válidas.
  `firmar_ambos` se ignora para `cadena_3` (solo soporta 2 firmantes, fuera
  de alcance de este paso). JS del formulario muestra/oculta el select de
  tercero y el bloque de turno intermedio según el tipo elegido. Testeado
  con `pytest --testmon` (creación correcta con 3 participantes y ciclo
  A→B→C→A, y los 2 casos de error).
- [x] Paso 6 (`docs/PLAN_3.md`) — `app/services/documento_cambio.py`:
  `match_admite_documento_cambio()` ahora admite también
  `match.tipo == "cadena_3"` con exactamente 3 `MatchParticipacion` (misma
  validación de franja/aceptado concreto que ya tenía para `directo_2`).
  `crear_documento_cambio_desde_match()` generalizado para iterar sobre
  todas las participaciones del match (2 o 3) en vez de desempaquetar
  `p1, p2` a mano, construyendo el `DocumentoCambio` con `tipo="cadena_3"`
  cuando corresponde (y `tipo="cambio"` sin cambios para `directo_2`).
  Testeado con un match cadena_3 completo (ciclo ana→pedro→luis→ana, cada
  participación con `turno_cedido` y `turno_aceptado`); el test previo que
  verificaba que una cadena_3 incompleta (sin `turno_aceptado`) seguía sin
  admitirse se mantiene sin cambios. `pytest --testmon` en verde.
- [x] Paso 5 (`docs/PLAN_3.md`) — `app/services/documento_cambio.py`:
  nueva función `crear_documento_cambio_cadena_3(creado_por, companero,
  tercero, turno_creado_por_cede, turno_companero_cede, turno_tercero_cede,
  depende_de_id=None)` que crea un `DocumentoCambio(tipo="cadena_3")` con 3
  `ParticipanteDocumentoCambio` coherentes con el ciclo
  creado_por→companero→tercero→creado_por, calcula factibilidad y notifica
  a `companero` y `tercero` (no a `creado_por`). Sigue el estilo de
  `crear_documento_cambio_junte`. Testeado con `pytest -k cadena_3` (8
  passed); pendiente ejecutar la suite completa al cierre de la fase
  (Paso 8).
- [x] Paso 4 (`docs/PLAN_3.md`) — `app/services/documento_cambio.py`:
  `generar_notas_ilog` y el email de `firmar_documento` usan
  `_usuario_que_recibe` en vez del patrón «otro por exclusión», que con 3
  participantes era ambiguo. Para documentos cadena_3 de 3 participantes
  cada nota/email referencia al usuario correcto (el que recibe el turno
  cedido). El comportamiento con 2 participantes no cambia. Testeado con
  casos de 2 y 3 participantes.
- [x] Paso 3 (`docs/PLAN_3.md`) — `app/services/documento_cambio.py`:
  función `_contexto_pdf_cadena_3(documento)` (paralela a `_contexto_pdf_junte`)
  que devuelve `mostrar_cadena_3=True` + variables para el tercer participante
  (`cede_tercer_franja_c`, `cede_tercer_fecha_c`, `tercer_companero_c`,
  `firma_tercero`). `generar_pdf_documento` modificado para identificar
  correctamente los 3 roles (solicitante, compañero=quien recibe del
  solicitante, tercero=quien cede al solicitante) y pasar
  `cede_fecha_receptor_nombre`/`recibe_fecha_receptor_nombre` via
  `_usuario_que_recibe`. Testeado con documento cadena_3 de 3 participantes
  firmado y generación de PDF.
- [x] Paso 2 (`docs/PLAN_3.md`) — `app/services/documento_cambio.py`:
  función `_usuario_que_recibe(documento, participante)` que, dado un
  participante, devuelve el `Usuario` del participante que recibe el
  turno que cede. Funciona para 2 o 3 participantes y reemplaza el
  patrón «otro por exclusión». Testeado con ciclo A→B→C→A y con
  intercambio 1-a-1 clásico.
- [x] Paso 1 (`docs/PLAN_3.md`) — `app/templates/documento_cambio/pdf.html`:
  5 `@frame` nuevos para el tercer participante de una cadena_3
  (`cede_tercer_franja_frame`, `cede_tercer_fecha_frame`,
  `tercer_companero_frame`, `firma_tercero_frame`, coordenadas exactas del
  plan), todos condicionados a un flag nuevo `mostrar_cadena_3` (mismo
  patrón que `mostrar_junte`). `cede_fecha_c`/`recibe_fecha_c` (ya
  existentes) ganan un paréntesis opcional `(lo trabaja <nombre>)` vía
  `cede_fecha_receptor_nombre`/`recibe_fecha_receptor_nombre` (variables que
  llenará el Paso 2/3). Sin tests unitarios de layout en este proyecto
  (validado renderizando un PDF de prueba manual con datos ficticios y
  confirmando visualmente las 5 posiciones nuevas, incluido el solape
  intencional con `firma_solicitante_frame`/`firma_companero_frame`).

## Historial completo
El registro detallado de fases y pasos anteriores está en
`PROGRESS_ARCHIVE.md`.

## Notas / decisiones / asunciones pendientes
- Fase 12 (`docs/PLAN_3.md`) cerrada — historial detallado en
  `PROGRESS_ARCHIVE.md`.
- La unidad principal del usuario siempre aparece en `usuario_unidad`
  (invariante sembrado por el backfill de la migración; `sincronizar_unidades`
  lo mantiene y no permite eliminarla).
- `unidad_activa_o_403` sigue la precedencia query param > sesión
  (`session["unidad_activa_id"]`) > unidad principal. Persiste en sesión
  automáticamente cuando se pasa `unidad_id` explícito por query param.
- Quedan 21 referencias MUST change en `publicaciones.py`, `busquedas.py`,
  `unidad.py` y `documento_cambio.py` que deberían usar la unidad activa pero
  aún usan `current_user.unidad`/`categoria_id`/`grupo_intercambio`. Se
  abordarán a continuación.
- Preguntas abiertas del plan (registro libre de unidades, abandono de
  unidad) siguen pendientes de confirmar.
