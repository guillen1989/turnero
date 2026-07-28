# Estado del desarrollo

## Fase actual
Fase 12 — Hojas de cambio para "cambios a 3" (cadena_3), plan completo en
`docs/PLAN_3.md`.

## Paso actual / siguiente paso
Paso 7 completado (wiring en `app/routes/documento_cambio.py` y
`nuevo.html` para crear hojas `cadena_3` desde el formulario).
Siguiente: Paso 8 de `docs/PLAN_3.md` — revisión final y UAT (repasar
`especificacion-app-cambio-turnos.md` UAT-7.1 a UAT-7.4, ejecutar la suite
completa una sola vez, generar un PDF real desde la UI, cerrar la fase en
`PROGRESS.md` y abrir la PR contra `staging`).

## Últimos pasos completados
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
- El solape visual de `firma_tercero_frame` con los frames de firma vecinos
  es una decisión explícita e irrevocable del usuario (ver cabecera de
  `docs/PLAN_3.md`) — no proponer alternativas que reubiquen campos.
- `_usuario_que_recibe` (Paso 2 de `docs/PLAN_3.md`) es la pieza central que
  desbloquea los Pasos 3 y 4; implementarla y probarla bien antes de seguir.
- `tipo == "cadena_3"` no requiere migración: `DocumentoCambio.tipo` es un
  `String(20)` libre.
