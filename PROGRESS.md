# Estado del desarrollo

## Fase actual
Fase 10 — Hoja de cambios digital (documento de cambio con firma)

## Paso actual / siguiente paso
Worktree `turnos-factibles-y-causas` (rama
`worktree-turnos-factibles-y-causas`, creada desde `origin/staging` en
`dfc0557`, que ya incluye el PR #21 mergeado -- ver más abajo). Motivado por
tres peticiones del usuario tras usar la app en producción:

a. Los desplegables de turno en `/documentos-cambio/nuevo` y
   `/documentos-cambio/registrar-papel` listan todas las `FranjaHoraria` del
   grupo, aunque el trabajador elegido no curre ese turno ese día concreto --
   deberían filtrarse por lo que el usuario realmente tiene asignado en la
   planilla ese día.
b. `comprobar_factibilidad` (`app/services/factibilidad_documento_cambio.py`)
   devuelve `no_factible` sin decir *por qué* (corta en el primer fallo que
   encuentra) -- la supervisora necesita ver el motivo concreto (no trabaja
   ese turno / no está libre / rompe el límite de días consecutivos / rompe
   el descanso nocturno) para cada participante.
c. "Hojas de cambio encadenadas": permitir registrar una hoja que depende de
   otra hoja todavía pendiente de autorizar, sin que salga `no_factible`
   solo porque los efectos de la primera aún no están volcados a la
   planilla real.

Van en **dos PRs separados** porque (c) es bastante más grande y arriesgado
que (a)+(b).

- **PR 1 (mergeado como PR #23): Bloque A + Bloque B.**
  - [x] Bloque A — Filtrado de `<select>` de turno por planilla real: HECHO.
  - [x] Bloque B — Motivos de no factibilidad: HECHO.
- [x] Bloque C — Hojas de cambio encadenadas: HECHO.
  - [x] Modelo: columna `DocumentoCambio.depende_de_id` (FK self-referential nullable) + relación `depende_de`.
  - [x] Migración: `0de75e74af26` (un solo paso, nullable sin backfill).
  - [x] Servicio de overlay: `_construir_overlay()` recorre la cadena de predecesores pendientes y construye conjuntos `added`/`removed` de turnos. Funciones de factibilidad (`_trabaja_turno`, `_libre_para_turno`, `_trabaja_el_dia`, `_contar_dias_consecutivos_trabajados`, `_viola_limite_dias_consecutivos`, `_viola_descanso_nocturno`) aceptan parámetro `overlay` opcional; sin overlay, comportamiento idéntico al actual.
  - [x] Servicio de recálculo: `_recalcular_factibilidad_dependientes()` se llama desde `autorizar_documento`, `denegar_documento` y `anular_documento` para actualizar `factibilidad_estado`/`factibilidad_motivos` de todos los documentos que dependen del documento modificado.
  - [x] Rutas: `nueva()` y `registrar_papel()` aceptan `depende_de_id` del formulario y pasan `hojas_pendientes` a las plantillas. Nuevo helper `_hojas_pendientes_encadenables()`.
  - [x] UI: select opcional "Esta hoja depende de otra" en `nuevo.html` y `registrar_papel.html` listando hojas pendientes de la misma unidad. Badge "Encadenada a" en `ver.html` y `supervisora.html`.
  - [x] Tests: 13 nuevos (2 modelo + 4 overlay + 3 recálculo + 4 rutas), 143 pasando. 3 tests de PDF con fallo preexistente (incompatibilidad `openssl_md5` en Python 3.8, no relacionado con este cambio).
- [x] Style: intensificados los colores de la fila de números de día (`#94a3b8`) y de los botones solo-supervisora en la navbar (mayor opacidad amber).

- **PR 2 (completado en `staging`): Bloque C — hojas de cambio encadenadas.**
  Implementado tras mergear el PR 1. Diseño acordado con el usuario:
  - Los números de hoja (`DocumentoCambio.numero_unidad`) son relativos a
    `unidad_id` (`_siguiente_numero_unidad`, `UniqueConstraint("unidad_id",
    "numero_unidad", ...)`), **no** un identificador global -- el
    encadenado debe referenciar siempre por el `id` real (autoincrement,
    único de verdad), nunca por `numero_unidad`, para evitar ambigüedad
    entre unidades.
  - Nueva columna nullable `DocumentoCambio.depende_de_id` (FK
    self-referential a `DocumentoCambio.id`). Migración de un solo paso
    (nullable, sin backfill necesario -- no rompe el patrón de tres pasos
    porque no es `NOT NULL`).
  - UI en el alta de una hoja: select opcional "¿Esta hoja depende de otra
    hoja aún no autorizada?", listando las hojas pendientes de la misma
    `unidad_id` como p.ej. `"Hoja nº 12 (14/03) -- cedes noche a Ana,
    recibes tarde de Ana"` (el `value` del `<option>` es el `id` real;
    mostrar `numero_unidad` como texto es seguro porque la lista ya está
    acotada a una sola unidad).
  - Backend: construir un "overlay" del estado hipotético de la planilla
    (estado real + deltas de la cadena de documentos predecesores aún
    pendientes) y hacer que las funciones auxiliares de
    `factibilidad_documento_cambio.py` (`_trabaja_turno`,
    `_libre_para_turno`, `_trabaja_el_dia`,
    `_contar_dias_consecutivos_trabajados`) consulten ese overlay en vez de
    `TurnoPlanilla`/`EstadoDiaPlanilla` directamente -- sin cadena, el
    overlay es un no-op y el comportamiento actual no cambia (compatible
    hacia atrás).
  - Si se deniega/anula un predecesor, hay que recalcular la factibilidad
    de la hoja dependiente (puede volver a `no_factible`); una vez
    autorizado el predecesor (`volcar_documento_a_planillas` aplicado), la
    dependiente pasa a comprobarse contra el estado real directamente (deja
    de necesitar el overlay).

## Paso anterior
Rama `feature/planilla-supervision-highlights` (PR #22 mergeada): 4 mejoras
visuales de `/planilla/supervision` pedidas por el usuario.

Rama `fix/planilla-supervision-followups` (a partir de `staging`, ya con la
lista de 9 mejoras anterior mergeada). Lista de 8 seguimientos pedidos por el
usuario tras probar `/planilla/supervision` y `/documentos-cambio/supervisora`
en vivo:

### Detalle de la ronda anterior (8 seguimientos, ya mergeada en `staging`)
- [x] 1. Color propio (ámbar) para los botones solo-supervisora del nav, para
  distinguirlos de un vistazo de la fila de usuario normal de arriba
  (`.nav-supervisora-row a` en `main.css`).
- [x] 2. Los usuarios eliminados (`Usuario.eliminado`, nueva property que
  comprueba `password_hash == 'CUENTA_ELIMINADA'`) ya no aparecen en
  `/planilla/supervision` (filtrado en la ruta `index`).
- [x] 3. Bug real encontrado y corregido: el commit anterior (`e7df65d`) solo
  había verificado que "añadir turno extra sin sustituir" funcionaba en la
  planilla propia del trabajador (`/planilla/dia/añadir`), **no** en el editor
  de la supervisora. `ajustar_turno_trabajador` (servicio) siempre borraba
  todo el día antes de aplicar la selección; ahora acepta `sustituir: bool =
  True` y, si es `False` y hay `franja_id`, añade sin tocar lo que ya había.
  La ruta `/planilla/supervision/ajustar` acepta un nuevo campo de formulario
  `anadir_extra`; el modal de la plantilla añade un checkbox "Añadir turno
  extra" que solo se muestra cuando la selección es un turno concreto (no un
  estado ni "vaciar"). Tests de regresión a nivel de servicio y de ruta.
- [x] 4. El modal de "Modificar turno" de `/planilla/supervision` incluye
  ahora un enlace "📄 Registrar cambio manualmente (papel)" que lleva a
  `/documentos-cambio/registrar-papel` preseleccionando trabajador y fecha
  (`registrar_papel` acepta `usuario1_id`/`fecha` por query string en GET).
- [x] 5. Botón "Registrar cambio desde papel" con clase propia
  `.btn-registrar-papel` (ámbar, con emoji 📄) en vez de `btn-secondary`
  genérico, tanto en `/documentos-cambio/supervisora` como en el nuevo enlace
  del punto 4.
- [x] 6. `registrar_documento_cambio_papel` comprueba la factibilidad antes de
  aplicar el cambio: si sale `no_factible`, hace rollback, lanza
  `CambioNoFactibleError` (nueva excepción) y no crea ni aplica nada; la ruta
  `registrar_papel` la captura y muestra un aviso en vez de aplicar el
  cambio. `no_verificado` sigue dejando pasar (no hay planilla suficiente
  para *saber* que es inviable, distinto de saber que sí lo es).
- [x] 7. Las hojas de cambio (`DocumentoCambio`/`ParticipanteDocumentoCambio`)
  ya no dependen del nombre en vivo de `Usuario` para documentos completos:
  nuevo campo `nombre_congelado` (nullable, migración `fce42d5845ad`, sin
  backfill porque el proyecto todavía no ha llegado a producción) en
  `ParticipanteDocumentoCambio`, con la propiedad `nombre_mostrar` (=
  `nombre_congelado or usuario.nombre`). Se rellena en el momento de
  completarse el documento: en `registrar_documento_cambio_papel` (nace
  completo) y en `firmar_documento` cuando `todos_han_firmado()`. Plantillas
  (`ver.html`, `lista.html`, `supervisora.html`) y generación de PDF/notas
  ilog (`app/services/documento_cambio.py`) cambiadas a `nombre_mostrar`.
  `eliminar_cuenta()` no necesitó tocarse. Se muestra siempre el nombre
  congelado para documentos completos (no solo cuando la cuenta ya no
  existe), para que el PDF sea estable en el tiempo. Tests de regresión a
  nivel de modelo, servicio (firma digital y papel, incluyendo PDF) y ruta
  (`/documentos-cambio/supervisora` tras `eliminar_cuenta`).
- [x] 8. Confirmado el hueco real que sospechaba el usuario sobre
  `origen_papel` (commit `4d3636d3`): la columna sí se usaba en
  `documento_cambio/ver.html` y `supervisora.html`, pero **no** en
  `documento_cambio/lista.html` ("Mis hojas de cambio", la vista de cada
  trabajador) -- ahí no había ninguna insignia "Papel". Añadida + test de
  regresión.
- [x] 9. UX del modal "Modificar turno" de `/planilla/supervision`
  reordenado: el checkbox "Añadir turno extra" del punto 3 solo aparecía
  *después* de elegir el turno concreto, lo cual no era evidente para la
  supervisora al probarlo en vivo. Sustituido por un `radiogroup` de dos
  opciones ("Modificar turno del día" / "Añadir turno extra (doblaje)")
  que se muestra *antes* del desplegable de turno/estado; al elegir
  "añadir", se deshabilitan las opciones no aplicables ("Vaciar día" y el
  optgroup de estados especiales, que no tienen sentido en un doblaje).
  Sin cambios de backend (la ruta/servicio ya soportaban `sustituir=False`
  desde el punto 3). Cobertura nueva a nivel e2e con Playwright
  (`e2e/test_planilla_supervision.py`, 3 tests: orden visual del radio
  antes que el select, deshabilitado de estados especiales en modo
  "añadir", y que añadir un turno extra no borra el turno existente del
  día). 49 tests en verde (`test_rutas_planilla_supervision.py` +
  `test_servicio_planilla_supervision.py` + el nuevo fichero e2e).
- [x] 10. El radiogroup del punto 9 seguía sin ser evidente al usarlo en
  vivo (dos radios + un desplegable compartido para todo: turnos, estados
  y "vaciar" era demasiado indirecto). Rediseño a UI de filas con iconos:
  el modal ahora lista una fila por cada turno/estado ya asignado ese día,
  cada una con "✎" (modificar esa franja concreta por otra) y "−"
  (eliminarla, sin tocar el resto -- soporta doblajes); debajo, un botón
  "+ Añadir" muestra el formulario para dar de alta un turno o estado
  nuevo. El icono de papel del punto 4 se queda sin texto visible (solo el
  emoji) para que el modal sea más visual. Backend: dos rutas nuevas,
  `POST /planilla/supervision/turno/eliminar` y
  `POST /planilla/supervision/turno/editar`, más los servicios
  `eliminar_turno_trabajador`/`editar_turno_trabajador` (reutilizan
  `eliminar_turno`/`añadir_turno` de `app/services/planilla.py`) --
  `ajustar_turno_trabajador` y su ruta `/ajustar` se conservan para
  "añadir turno nuevo" / asignar estado / vaciar día. Regla de sustitución
  simplificada: elegir un turno en el "+" siempre añade (nunca vacía el
  día), elegir un estado especial o "vaciar" siempre sustituye todo el
  día -- ya no hace falta el checkbox/radio de modo. Los datos de cada
  celda (turnos + estado) se serializan a JSON en la ruta (`_turnos_a_json`,
  `_estado_a_json`) y se pintan en el modal por JS sin peticiones extra.
  Tests: cobertura completa a nivel de ruta para las dos rutas nuevas,
  test de ruta para los atributos JSON de la celda, y reescritura completa
  de `e2e/test_planilla_supervision.py` (5 tests Playwright: iconos
  editar/eliminar en la fila, eliminar quita solo esa franja, editar
  sustituye solo esa franja, añadir no pierde el turno existente, icono de
  papel sin texto). 68 tests en verde (`test_rutas_planilla_supervision.py`
  + `test_servicio_planilla_supervision.py` + `e2e/test_planilla_supervision.py`).

Todos los tests afectados en verde (incluidos los del punto 7, ya
implementado tras confirmación del usuario). PR #21 abierto en borrador
contra `staging`. Pendiente: mergear esta rama en `staging` y empujar a
`origin`.

## Backlog (fuente: .backlog)
- [x] B19: "Cambios a 4" — cadena de intercambio a 4 bandas (ciclos completos, sintéticas/avisos para huecos parciales, badges, preferencia de visualización en calendario) ✓
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

## Historial completo
El registro detallado de pasos y fases anteriores (previo al último resumido arriba), y el checklist histórico completo de pasos completados, están en `PROGRESS_ARCHIVE.md`. No hace falta leerlo para reanudar el trabajo — solo consultarlo si se necesita el contexto de una decisión antigua.

## Notas / decisiones / asunciones pendientes
- Sin campo teléfono en ningún modelo ni formulario (decisión explícita del usuario).
- FranjaHoraria se define a nivel de GrupoDeIntercambio, no de Unidad individual.
- No se crea entidad Turno separada: fecha + franja_horaria_id se embeben directamente en turno_cedido y turno_aceptado.
- Autenticación: email + contraseña (Flask-Login + Werkzeug).
- El motor de matching se implementa como módulo puro sin acoplamiento a Flask ni SQLAlchemy.
- Los conflictos de pip (streamlit, spyder) son del sistema y no afectan al proyecto.
- conftest.py empuja un app context fresco por test para aislar g (Flask-Login) y la sesión SQLAlchemy. Necesario porque en Flask 3.x g está scoped al app context (no al request context) y Flask-Login cachea current_user en g._login_user.

### Hoja de cambios digital (Fase 10) — decisiones tomadas con el usuario
- Fase 1 explícitamente: sin cadenas a 3/4 bandas, sin juntes de noches, mono-cuenta (las dos firmas se hacen desde el mismo dispositivo/cuenta).
- Se genera el documento aunque no se haya comprobado factibilidad contra planillas (decisión consciente: el objetivo inmediato es tener un prototipo que enseñar a los jefes, no bloquear por falta de verificación). La comprobación de factibilidad es un paso posterior.
- Firma dibujada con el dedo (canvas) por decisión explícita del usuario para dar sensación de formalidad ante su supervisora, aunque no tenga valor legal reforzado — de ahí `hash_documento` en `FirmaDocumentoCambio` como rastro real por detrás del gesto visual.
- El documento generado debe ser visualmente lo más fiel posible a `hojacambios.png` (formulario real "SOLICITUD DE CAMBIO DE TURNO O GUARDIA" del Hospital Universitario La Paz, guardado en la raíz del repo).
- Las dos rejillas L-M-X-J-V-S-D del impreso son para juntes de noches (fuera de alcance ahora) — se renderizan en blanco/estáticas, sin datos.
- El bloque "INFORME POR PARTE DE LA SUPERVISORA" (Favorable/Desfavorable + firma) no se usa en la práctica según el usuario, pero se mantiene en el documento generado como bloque estático/en blanco, sin tercer firmante ni lógica funcional.
- Plantilla: HTML/Jinja2 + renderizado a PDF con WeasyPrint (no Word/LibreOffice), generado bajo demanda (no se persiste el PDF, evita el problema de disco efímero en Railway) — pendiente de implementar.
- `ESPECIFICACION.md` pendiente de actualizar (ver nota en el paso anterior): el principio "no deja constancia oficial... no es un documento de RRHH" queda desactualizado con esta funcionalidad.
- Bug preexistente encontrado en `app/templates/publicaciones/publicar.html` (no arreglado, fuera de alcance de esta fase): usa clases `alert`/`alert--{{cat}}` para los flash messages, que no existen en `main.css` (solo `flash`/`flash--*` están definidas), y además duplica el bloque `get_flashed_messages` que `base.html` ya renderiza globalmente — el mensaje sale dos veces, una con estilo y otra en texto plano sin caja. Las plantillas nuevas de `documento_cambio` no repiten el patrón. Pendiente decidir si merece su propio paso de limpieza.

- [x] fix(documento-cambio): la decisión de la supervisora (autorizar/denegar en `ver.html`) mostraba dos recuadros de firma duplicados, uno por cada `<form>` independiente (`autorizar-form`/`denegar-form`) · fusionados en un único `<form id="decision-form">` con un solo lienzo de firma y dos acciones vía `formaction` en los botones "Autorizar"/"Denegar" (y en sus respectivos "usar firma guardada") · el textarea de motivo pasa a ser común a ambas acciones (ya no `required` en HTML: el servidor ya validaba y redirigía con flash si faltaba, sin esa validación ninguna ruta se rompe) · `firma-canvas.js::initFirmaForm` generalizado para soportar varios botones `.firma-usar-guardada` en el mismo formulario (antes asumía uno solo) y estos pasan a ser botones `type="submit"` reales con `formaction` propio en vez de disparar `form.requestSubmit()`/`form.submit()` a mano (se simplifica el JS: el navegador ya respeta `formaction` al hacer clic) · mismo cambio aplicado al botón "Firmar con firma guardada" de la sección de firma del participante, por coherencia con el nuevo mecanismo · 1 test nuevo (`test_decision_supervisora_muestra_un_unico_recuadro_de_firma`) · 65 tests de `test_rutas_documento_cambio.py` + 90 de auth/dashboard passing

- [x] fix(documento-cambio): `comprobar_factibilidad` marcaba como `no_factible` cambios en papel legítimos cuando el día cedido caía dentro de la racha de días consecutivos (o era la noche anterior/siguiente) del día que ese mismo participante recibía en el mismo documento — detectado en staging al intentar registrar un cambio real (Ana García cede "Mañana" el 1/7 y recibe "Diurno 12h" el 4/7): su racha ya publicada llegaba a 12 días seguidos sin descontar el 1/7, por encima del límite de 8 del grupo, aunque ese día deja de ser suyo con el propio cambio · `_trabaja_el_dia`, `_contar_dias_consecutivos_trabajados`, `_viola_limite_dias_consecutivos` y `_viola_descanso_nocturno` reciben ahora `fecha_cedida` (el `turno_cede_fecha` del participante en ese documento) y tratan ese día como no trabajado al evaluar la racha/descanso del día recibido · 2 tests nuevos (racha con día cedido de por medio, descanso nocturno con la noche cedida como día anterior) · 11 tests de `test_servicio_factibilidad_documento_cambio.py` + 178 de los módulos relacionados de `documento_cambio` passing

- [x] style(planilla-supervision): 4 mejoras visuales de `/planilla/supervision` pedidas por el usuario. De las 4, 2 ya estaban implementadas de rondas anteriores sin cambios necesarios: botones solo-supervisora con color propio (`.nav-supervisora-row a`) y resaltado de fila al clicar el nombre de un trabajador (`.supervision-fila-resaltada`, ya soporta varios trabajadores resaltados a la vez de forma independiente). Las 2 restantes sí requerían trabajo: (1) la fila de números de día en la cabecera no se distinguía de la fila de contadores de presencia justo encima (ambas con el mismo fondo `#f5f7fa` heredado de `.supervision-matriz thead th`) — nueva clase `supervision-dianum-fila` en el `<tr>` con fondo propio (`#e2e8f0`), excluyendo vía `:not()` las celdas que ya tienen fondo de "hoy"/fin de semana para no pisarlas; (2) los días con doblaje (más de un turno el mismo día) no resaltaban visualmente, solo se veían los chips apilados — en vez del borde negro grueso que proponía el usuario, se usa `box-shadow: inset 0 0 0 3px` en ámbar (mismo acento ya usado para lo "de supervisora"/papel) sobre una nueva clase `supervision-celda--doblaje`: un borde real hubiera desplazado la cuadrícula al chocar con `border-collapse: collapse` de la tabla, mientras que el inset shadow no participa en el colapso de bordes ni compite con los fondos de "hoy"/fin de semana/fila resaltada, que son la misma propiedad `background`. 3 tests nuevos (clase de doblaje presente con 2 turnos, ausente con 1, clase de la fila de números de día) · 48 tests de `planilla_supervision` (rutas + servicio) passing
