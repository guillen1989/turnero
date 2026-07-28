# Estado del desarrollo

## Fase actual
Fase 12 — Hojas de cambio para "cambios a 3" (cadena_3), plan completo en
`docs/PLAN_3.md`.

## Paso actual / siguiente paso
Paso 1 completado (frames de `pdf.html`). Siguiente: Paso 2 de
`docs/PLAN_3.md` — helper `_usuario_que_recibe(documento, participante)` en
`app/services/documento_cambio.py`, con TDD, para resolver quién recibe
cada `turno_cedido` en un ciclo A→B→C→A (reemplaza el patrón "otro por
exclusión" que solo vale para 2 participantes).

## Últimos pasos completados
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
