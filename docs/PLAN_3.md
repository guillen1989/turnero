# Plan: hojas de cambio para "cambios a 3" (cadena_3)

> Cada paso está pensado para completarse en una sesión independiente. Marca la
> casilla al terminar el paso, haz commit siguiendo `CLAUDE.md` (TDD, commit
> atómico, `PROGRESS.md` actualizado) y continúa con el siguiente paso en una
> sesión nueva si hace falta ahorrar contexto.
>
> **Instrucción vinculante del usuario, no renegociable:** el layout de
> `pdf.html` para el tercer participante se implementa exactamente como se
> describe en el Paso 1, aceptando que los frames se solapen visualmente con
> los ya existentes. No propongas ni implementes alternativas que reubiquen
> los campos para evitar el solape (ya se evaluaron y fueron rechazadas
> explícitamente: *"ignora los problemas de espacio real. mantén lo que te he
> descrito aunque se solapen los campos"*).

## Contexto técnico (leer antes de empezar cualquier paso)

- `DocumentoCambio.tipo` es `db.Column(db.String(20), ...)`, ya usado con
  valores `"cambio"` y `"junte"`. Añadir `"cadena_3"` **no requiere
  migración**: es un string libre, no un enum de base de datos.
- `ParticipanteDocumentoCambio` es una lista genérica (relación uno-a-muchos
  desde `DocumentoCambio`), no hay límite de 2 en el modelo. La restricción a
  2 participantes vive solo en la capa de servicio (`app/services/documento_cambio.py`).
- Precedente a imitar en todo: `tipo == "junte"`, implementado con
  `_contexto_pdf_junte()` y `crear_documento_cambio_junte()`.
- El motor de matching **ya genera** matches de cadena_3:
  `app/matching/service.py::crear_match_cadena_3(pub_a, pub_b, pub_c)` crea un
  `MatchCambio(tipo="cadena_3")` con **3** `MatchParticipacion`, cada una con
  `turno_cedido_id` (lo que esa banda cede a la siguiente del ciclo) y
  `turno_aceptado_id` (lo que recibe de la anterior). El ciclo es
  A→B→C→A: A cede a B, B cede a C, C cede a A.
- Puntos de la capa de servicio con hardcoding a 2 participantes que hay que
  tocar (todos en `app/services/documento_cambio.py`):
  - `match_admite_documento_cambio()` (línea ~254): rechaza explícitamente
    todo lo que no sea `tipo == "directo_2"` con `len(participaciones) == 2`.
  - `crear_documento_cambio_desde_match()` (línea ~275): `p1, p2 = match.participaciones`.
  - `generar_pdf_documento()` (línea ~465): busca "solicitante" y "companero"
    con `next(... if p.usuario_id != solicitante.id)` — asume exactamente 2.
  - `generar_notas_ilog()` (línea ~398): busca "otro" con
    `next(o for o in documento.participantes if o.usuario_id != p.usuario_id)`
    — con 3 participantes esto es ambiguo (hay 2 "otros" posibles).
  - `firmar_documento()`, bloque de email al completar (línea ~344): mismo
    patrón "otro" por exclusión, mismo problema con 3 participantes.
- Ruta de creación manual: `app/routes/documento_cambio.py::nueva()` (línea
  ~358) ya tiene un `<select>` de `tipo` que rama a `crear_documento_cambio_junte`
  cuando `tipo == "junte"`. Es el sitio donde añadir la rama `cadena_3`.

---

## Paso 1 — Frames de `pdf.html` para el tercer participante ✅

- [x] Editar `app/templates/documento_cambio/pdf.html`.

Coordenadas exactas a usar (todas mirando los frames existentes, delta
vertical = `companero_frame.top - recibe_franja_frame.top` = `92.16 - 84.96` =
**7.2mm**, el mismo delta que separa `recibe_franja_frame`/`recibe_fecha_frame`
de `companero_frame`):

1. **`cede_tercer_franja_frame`** (nuevo, por encima de `cede_franja_frame`):
   `left: 53.60mm; top: 67.09mm; width: 35.73mm; height: 8mm;`
   (top = `74.29 - 7.2`, mismo left/width que `cede_franja_frame`).
   Contenido: `-pdf-frame-content: cede_tercer_franja_c;`

2. **`cede_tercer_fecha_frame`** (nuevo, por encima de `cede_fecha_frame`, misma
   distancia que el anterior):
   `left: 99.78mm; top: 67.09mm; width: 83.54mm; height: 8mm;`
   Contenido: `-pdf-frame-content: cede_tercer_fecha_c;`
   Este frame debe mostrar, entre paréntesis, el nombre del usuario que
   trabajará ese día/turno tras el cambio — mismo patrón que el punto 4.

3. **`tercer_companero_frame`** (nuevo, por debajo de `companero_frame`, mismo
   delta 7.2mm):
   `left: 58.01mm; top: 99.36mm; width: 125.30mm; height: 8mm;`
   Contenido: `-pdf-frame-content: tercer_companero_c;`

4. **`cede_fecha_frame`** y **`recibe_fecha_frame`** (ya existentes, se editan
   in situ, NO se mueven): en su contenido Jinja añadir, entre paréntesis,
   `(lo trabaja + <nombre del usuario que trabajará ese turno tras el
   cambio>)`. Ver Paso 2 para de dónde sale ese nombre.

5. **`firma_tercero_frame`** (nuevo, justo entre `firma_solicitante_frame` y
   `firma_companero_frame`; punto medio de los `left` de ambos —
   `(22.51 + 106.74) / 2 = 64.625mm` — se solapará con ambos frames vecinos,
   esto es intencional y aceptado):
   `left: 64.625mm; top: 174.5mm; width: 77.27mm; height: 17mm;`
   Contenido: `-pdf-frame-content: firma_tercero_c;`

- [x] En el body del template, envolver los bloques de los 2 participantes
  base igual que ya se hace con `{% if not mostrar_junte %}`, usando un nuevo
  flag `mostrar_cadena_3` (ver Paso 3) para los 5 divs nuevos
  (`cede_tercer_franja_c`, `cede_tercer_fecha_c`, `tercer_companero_c`,
  `firma_tercero_c`), condicionados a `{% if mostrar_cadena_3 %}`.
- [x] Test: no hay tests unitarios de layout PDF en este proyecto (se valida
  visualmente). Generar un PDF de prueba manual con datos ficticios de cadena_3
  y confirmar visualmente que los 5 frames nuevos aparecen (aunque solapados)
  en las posiciones esperadas.
- [x] Commit: `feat(documento_cambio): añade frames de pdf.html para el tercer participante de una cadena_3`

---

## Paso 2 — Helper para resolver "quién trabaja cada turno tras el cambio" en una cadena_3

Para renderizar los paréntesis `(lo trabaja + <nombre>)` en
`cede_fecha_frame`, `recibe_fecha_frame` y `cede_tercer_fecha_frame`, y para
arreglar `generar_notas_ilog`/`firmar_documento` (Paso 5), hace falta poder
mapear, para un documento de 3 participantes, qué usuario terminará
trabajando cada turno_cedido tras el cambio (es el usuario cuyo
`turno_aceptado` coincide en fecha+franja con ese `turno_cedido`).

- [ ] Test (rojo): en `tests/services/test_documento_cambio.py` (o el fichero
  de tests que corresponda), crear un test que construya un
  `DocumentoCambio` con 3 `ParticipanteDocumentoCambio` simulando un ciclo
  A→B→C→A y verifique que la función nueva devuelve, para el
  `turno_cedido` de A, el usuario B (quien lo recibe).
- [ ] Verde: implementar en `app/services/documento_cambio.py` una función
  `_usuario_que_recibe(documento, participante)` que, dado un participante
  `p`, devuelva el `usuario` del participante `o` tal que
  `o.turno_aceptado.fecha == p.turno_cedido.fecha and
  o.turno_aceptado.franja_horaria_id == p.turno_cedido.franja_horaria_id`.
  Esta función reemplaza el patrón "otro por exclusión" y funciona igual de
  bien para 2 o para 3 participantes (para 2 participantes da el mismo
  resultado que el código actual).
- [ ] Ejecutar `pytest --testmon`.
- [ ] Commit: `feat(documento_cambio): añade _usuario_que_recibe para resolver el destinatario real de un turno cedido`

---

## Paso 3 — `_contexto_pdf_cadena_3` y contexto base de `generar_pdf_documento`

- [ ] Test (rojo): test para una nueva función
  `_contexto_pdf_cadena_3(documento)` (paralela a `_contexto_pdf_junte`) que,
  para un documento con `tipo == "cadena_3"`, devuelva un dict con al menos:
  `mostrar_cadena_3=True`, `cede_tercer_franja_c`, `cede_tercer_fecha_c`
  (con el nombre entre paréntesis ya resuelto vía `_usuario_que_recibe`),
  `tercer_companero_c` (nombre del tercer usuario), `firma_tercero_c`. Para
  cualquier otro `tipo`, debe devolver `{"mostrar_cadena_3": False}` (mismo
  patrón que `_contexto_pdf_junte`).
- [ ] Verde: implementar `_contexto_pdf_cadena_3` en
  `app/services/documento_cambio.py`, cerca de `_contexto_pdf_junte`.
- [ ] Modificar `generar_pdf_documento(documento)` para:
  - Seguir soportando el caso de 2 participantes sin cambios.
  - Cuando `documento.tipo == "cadena_3"`, en vez de
    `participante_companero = next(p for p in documento.participantes if p.usuario_id != solicitante.id)`
    (que con 3 participantes es ambiguo), identificar explícitamente los 3
    roles: el `solicitante` (ya se identifica igual, por `creado_por`), y los
    otros 2 participantes en el orden en que aparecen en
    `documento.participantes` (o mejor, siguiendo el ciclo con
    `_usuario_que_recibe`, para que el "compañero" de `companero_frame` sea
    consistentemente quien recibe del solicitante, y el "tercero" sea el que
    cede al solicitante).
  - Añadir `**_contexto_pdf_cadena_3(documento)` al dict de kwargs pasado a
    `render_template`, igual que ya se hace con `**_contexto_pdf_junte(documento)`.
  - Rellenar los paréntesis de `cede_fecha_c`/`recibe_fecha_c` con
    `_usuario_que_recibe` también cuando `tipo == "cadena_3"` (para `tipo ==
    "junte"` o `"cambio"` normal, dejar el comportamiento actual si no lo
    tenían ya).
- [ ] Ejecutar `pytest --testmon`.
- [ ] Commit: `feat(documento_cambio): _contexto_pdf_cadena_3 y soporte de 3 participantes en generar_pdf_documento`

---

## Paso 4 — Arreglar `generar_notas_ilog` y el email de `firmar_documento` para 3 participantes

- [ ] Test (rojo): test de `generar_notas_ilog` con un documento cadena_3 de 3
  participantes que verifique que cada nota "cede"/"recibe" referencia al
  usuario correcto (el que realmente cede/recibe ese turno concreto, según
  `_usuario_que_recibe`), no un "otro" arbitrario.
- [ ] Verde: sustituir el `otro = next(o for o in documento.participantes if
  o.usuario_id != p.usuario_id)` de `generar_notas_ilog` por
  `_usuario_que_recibe(documento, p)` (del Paso 2). Confirmar que el
  comportamiento con 2 participantes no cambia (debe dar el mismo resultado).
- [ ] Test (rojo): test de `firmar_documento` con cadena_3 que verifique que,
  al completarse la firma de los 3, cada participante recibe el email de
  notificación referenciando al usuario correcto (no ambiguo).
- [ ] Verde: mismo fix (`_usuario_que_recibe`) en el bloque de email dentro de
  `firmar_documento`.
- [ ] Ejecutar `pytest --testmon`.
- [ ] Commit: `fix(documento_cambio): corrige la resolución de "otro participante" para cadenas de 3`

---

## Paso 5 — `crear_documento_cambio_cadena_3` (creación manual)

- [ ] Test (rojo): test para una nueva función
  `crear_documento_cambio_cadena_3(creado_por, companero, tercero, turno_cede_a_companero, turno_cede_companero_a_tercero, turno_cede_tercero_a_creado_por, depende_de_id=None)`
  (firma exacta a decidir por quien implemente, siguiendo el estilo de
  `crear_documento_cambio_junte`) que cree un `DocumentoCambio(tipo="cadena_3")`
  con 3 `ParticipanteDocumentoCambio`, cada uno con su `turno_cedido` y
  `turno_aceptado` coherentes con el ciclo A→B→C→A.
- [ ] Verde: implementar en `app/services/documento_cambio.py`, junto a
  `crear_documento_cambio_junte`.
- [ ] Ejecutar `pytest --testmon`.
- [ ] Commit: `feat(documento_cambio): añade crear_documento_cambio_cadena_3`

---

## Paso 6 — `crear_documento_cambio_desde_match` para matches de cadena_3

- [ ] Test (rojo): test que, dado un `MatchCambio(tipo="cadena_3")` con sus 3
  `MatchParticipacion` (como los crea
  `app/matching/service.py::crear_match_cadena_3`), verifique que se puede
  generar un `DocumentoCambio` de 3 participantes a partir del match.
- [ ] Verde: extender `match_admite_documento_cambio()` para admitir también
  `match.tipo == "cadena_3"` con `len(match.participaciones) == 3` (con las
  mismas validaciones de franja/aceptado que ya tiene para `directo_2`,
  adaptadas a 3), y extender `crear_documento_cambio_desde_match()` (o crear
  una función hermana) para construir el `DocumentoCambio` de 3 participantes
  a partir de las 3 `MatchParticipacion`, usando el mapeo
  `turno_cedido`/`turno_aceptado` que ya expone `crear_match_cadena_3`.
- [ ] Ejecutar `pytest --testmon`.
- [ ] Commit: `feat(documento_cambio): admite creación de hoja de cambio desde matches de cadena_3`

---

## Paso 7 — Wiring en `app/routes/documento_cambio.py`

- [ ] Añadir la opción `cadena_3` al `<select>` de tipo en
  `app/templates/documento_cambio/nuevo.html` (junto a `cambio` y `junte`).
- [ ] En `nueva()` (línea ~358), añadir la rama `if tipo == "cadena_3":` que
  recoja del formulario los datos del tercer participante y turno (nuevos
  campos: tercer compañero, turno que se le cede, etc. — diseñar el
  formulario en paralelo a como `_extraer_turnos_junte()` resuelve el caso
  junte) y llame a `crear_documento_cambio_cadena_3` (Paso 5).
- [ ] Añadir validaciones de formulario equivalentes a las de `directo_2`/`junte`
  (compañero válido, tercero válido y distinto del compañero y del propio
  usuario, franjas válidas, fechas válidas).
- [ ] Test (rojo→verde): test de integración de la ruta `POST
  /documentos-cambio/nuevo` con `tipo=cadena_3` que verifique la creación
  correcta del documento y la redirección a `ver`.
- [ ] Ejecutar `pytest --testmon`.
- [ ] Commit: `feat(documento_cambio): permite crear hojas de cambio de cadena_3 desde el formulario`

---

## Paso 8 — Revisión final y UAT

- [ ] Repasar `especificacion-app-cambio-turnos.md`, sección "Cadenas a 3
  bandas" (UAT-7.1 a UAT-7.4), y verificar que cada UAT queda cubierto por
  tests existentes; añadir los que falten.
- [ ] Ejecutar la suite completa una sola vez al cerrar la fase (excepción al
  uso habitual de `--testmon`, para detectar regresiones cruzadas):
  `anaconda3/bin/python3 -m pytest`.
- [ ] Generar un PDF real de una hoja de cadena_3 desde la UI y confirmar
  visualmente que el resultado es aceptable (con el solape ya asumido).
- [ ] Actualizar `PROGRESS.md` cerrando esta fase.
- [ ] Commit final y apertura de la Pull Request contra `staging`.

---

## Notas / decisiones ya tomadas

- No hace falta migración de base de datos: `tipo` es un `String(20)` libre.
- El solape visual en `pdf.html` (Paso 1) es una decisión explícita e
  irrevocable del usuario, no un defecto a corregir en pasos posteriores.
- `_usuario_que_recibe` (Paso 2) es la pieza central que desbloquea correctamente
  los Pasos 3 y 4 — impleméntala y pruébala bien antes de seguir.
