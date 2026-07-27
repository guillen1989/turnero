      Junte de noches en /documentos-cambio/nuevo                                                                                            │
                                                                                                                                             │
      Contexto                                                                                                                               │
                                                                                                                                             │
      documento_cambio/pdf.html ya tiene los @frame para renderizar un junte de                                                              │
noches (Fase 10, PROGRESS.md), pero nada los rellena todavía:                                                                          │
│ match_admite_documento_cambio excluye explícitamente los matches junte, y                                                              │
│ ParticipanteDocumentoCambio solo modela un cede/recibe por fila. El objetivo                                                           │
│ de esta tarea es permitir crear, desde "Mis hojas de cambio > Nueva hoja de                                                            │
│ cambio", una hoja de tipo Junte de noches (dos compañeros reorganizan las                                                              │
│ noches de una semana), con su factibilidad comprobada, su PDF generado con los                                                         │
│ datos reales y su firma/autorización/volcado a planilla funcionando igual que                                                          │
│ una hoja normal.                                                                                                                       │
│                                                                                                                                        │
│ Ya existe un "junte" completo para publicaciones/matching (tipo de                                                                     │
│ PublicacionCambio): app/services/junte_semanal.py (cadencias LMVD=4                                                                    │
│ noches / MJS=3 noches, calcular_distribucion), _extraer_turnos_junte() en                                                              │
│ app/routes/publicaciones.py, matching en app/matching/service.py. Nada de                                                              │
│ eso toca DocumentoCambio — se reutiliza su lógica de cadencias, no su código                                                           │
│ de matching.                                                                                                                           │
│
│ Diseño elegido: reutilizar ParticipanteDocumentoCambio con varias filas por persona                                                    │
│                                                                                                                                        │
│ Un junte cede N noches y recibe N noches de la misma persona (mismo tamaño                                                             │
│ siempre: |cedidas| = |cadencia| - |cadencia ∩ noches_post| = |noches_post \ cadencia| = |aceptadas|, verificado matemáticamente). Eso  │
│ permite emparejar                                                                                                                      │
│ cada noche cedida con una aceptada y guardar el junte como varias filas                                                                │
│ ParticipanteDocumentoCambio por persona (una por noche intercambiada, cada                                                             │
│ una con su cede+recibe ya emparejado), en vez de diseñar un modelo nuevo.                                                              │
│                                                                                                                                        │
│ Con esto, toda la lógica de servicio existente funciona sin cambios                                                                    │
│ porque ya itera documento.participantes de forma genérica, sin asumir una                                                              │
│ fila por usuario: volcar_documento_a_planillas, generar_notas_ilog,                                                                    │
│ _hash_contenido, puede_anularse/anular_documento, todos_han_firmado,                                                                   │
│ firmas (FirmaDocumentoCambio es por usuario_id, no por fila). La plantilla                                                             │
│ ver.html tampoco necesita cambios: su sección "Datos del cambio" ya pinta                                                              │
│ una tarjeta por cada fila de documento.participantes.                                                                                  │
│                                                                                                                                        │
│ Solo hace falta:                                                                                                                       │
│ 1. Permitir varias filas por usuario en el mismo documento (constraint única                                                           │
│ actual lo impide).                                                                                                                     │
│ 2. Un campo tipo en DocumentoCambio para saber qué generar en el PDF.                                                                  │
│ 3. Una función de creación que arme las filas emparejadas.                                                                             │
│ 4. Que comprobar_factibilidad vea las noches hermanas del mismo documento al                                                           │
| comprobar racha de días consecutivos / descanso nocturno (hoy el overlay                                                               │
│ solo mira documentos predecesores en cadena, depende_de_id).                                                                           │
│ 5. El branch de generar_pdf_documento que ya faltaba (ver PROGRESS.md).                                                                │
│ 6. El formulario en /documentos-cambio/nuevo.
│ Pasos (TDD, un commit por paso)                                                                                                        │
│                                                                                                                                        │
│ Paso 1 — Modelo                                                                                                                        │
│                                                                                                                                        │
│ - app/models/documento_cambio.py: nueva columna tipo en DocumentoCambio                                                                │
│ (db.String(20), nullable=False, default="cambio",                                                                                      │
│ server_default="cambio" — seguro en un solo paso, ver CLAUDE.md, porque                                                                │
│ lleva server_default). Valores: "cambio" (ya existente) | "junte".                                                                     │
│ - Cambiar uq_participante_documento_usuario de                                                                                         │
│ (documento_id, usuario_id) a                                                                                                           │
│ (documento_id, usuario_id, turno_cede_fecha, turno_cede_franja_id) —                                                                   │
│ permite varias filas por usuario (una por noche), sigue impidiendo                                                                     │
│ duplicar la misma noche.                                                                                                               │
│ - Migración con flask db migrate + flask db heads (debe dar 1 head).                                                                   │
│ - Tests: constraint nueva permite 2 filas del mismo usuario con distinta                                                               │
│ fecha/franja y sigue rechazando duplicado exacto; tipo por defecto                                                                     │
│ "cambio" en filas existentes.
│ Paso 2 — app/services/junte_semanal.py: extraer lógica pura reutilizable                                                               │
│                                                                                                                                        │
│ - Extraer de calcular_distribucion(pub) una función nueva                                                                              │
│ distribucion_desde_fechas(fechas_cedidas, fechas_aceptadas) que reciba                                                                 │
│ listas de date en vez de objetos TurnoCedido/TurnoAceptado, con el                                                                     │
│ mismo cuerpo (cadencia LMVD/MJS por intersección, trabaja/libra,                                                                       │
│ num_noches, lunes_semana). calcular_distribucion pasa a ser un                                                                         │
│ wrapper de una línea sobre esta función. Reutilizado en el Paso 5 desde                                                                │
│ generar_pdf_documento, sin tener que depender de PublicacionCambio.                                                                    │
│ - Tests: distribucion_desde_fechas con los mismos casos que ya cubre                                                                   │
│ test_junte_semanal.py para calcular_distribucion; los tests existentes                                                                 │
│ de calcular_distribucion deben seguir en verde sin tocarlos (regresión).  │                                                                                                                                        │
│ Paso 3 — Factibilidad: overlay de filas hermanas del mismo documento                                                                   │
│                                                                                                                                        │
│ app/services/factibilidad_documento_cambio.py::_construir_overlay: hoy solo                                                            │
│ acumula deltas de la cadena depende_de_id. Añadir que siempre (con o                                                                   │
│ sin predecesor) añada también los deltas de las propias filas de                                                                       │
│ documento.participantes (added: su turno_recibe_*, removed: su                                                                         │
│ turno_cede_*). En comprobar_factibilidad, quitar el if documento.depende_de_id is not None: y llamar a _construir_overlay              │
│ siempre.                                                                                                                               │
│                                                                                                                                        │
│ Por qué es seguro para los documentos cambio de 2 filas de hoy: el propio                                                              │
│ día que se está comprobando ya se resuelve por parámetro directo                                                                       │
│ (fecha_hipotetica/fecha_cedida en _trabaja_el_dia) antes de mirar el                                                                   │
│ overlay, así que añadir las entradas de la fila propia al overlay es                                                                   │
│ redundante pero inofensivo; las de la otra persona no afectan porque                                                                   │
│ _turnos_dia filtra por usuario_id. El cambio de comportamiento real solo                                                               │
│ aparece con varias filas de la misma persona (junte): al comprobar la                                                                  │
│ racha de días consecutivos o el descanso nocturno de una noche, las noches                                                             │
│ hermanas del mismo junte para esa persona pasan a verse como ya aplicadas en                                                           │
│ vez de consultarse contra la BD real (que todavía no las tiene).                                                                       │
│ - Tests: regresión (toda la suite de test_servicio_factibilidad_documento_cambio.py                                                    │
│ sigue en verde); nuevo caso con un documento de 4 filas para una persona                                                               │
│ (varias noches consecutivas) donde la racha de días consecutivos solo se                                                               │
│ detecta correctamente contando las noches hermanas.
│ Paso 4 — Servicio: crear_documento_cambio_junte                                                                                        │
│                                                                                                                                        │
│ En app/services/documento_cambio.py, nueva función:                                                                                    │
│ crear_documento_cambio_junte(creado_por, companero, cedidos, aceptados, depende_de_id=None)                                            │
│ - cedidos/aceptados: listas de (fecha, franja_id) de creado_por                                                                        │
│ (mismo formato que ya usa _extraer_turnos_junte), longitud igual.                                                                      │
│ - Crea DocumentoCambio(tipo="junte", ...).                                                                                             │
│ - Por cada índice i: fila de creado_por con                                                                                            │
│ cede=cedidos[i]/recibe=aceptados[i]; fila de companero con                                                                             │
│ cede=aceptados[i]/recibe=cedidos[i] (mismo patrón de espejo que                                                                        │
│ crear_documento_cambio, solo que N filas en vez de 1).                                                                                 │
│ - Reutiliza comprobar_factibilidad, _notificar, _siguiente_numero_unidad                                                               │
│ tal cual.                                                                                                                              │
│ - Tests: crea 2*N filas correctas; notifica al compañero; factibilidad se                                                              │
│ calcula sobre las filas creadas.
│ Paso 5 — generar_pdf_documento: rama junte                                                                                             │
│                                                                                                                                        │
│ - Detectar documento.tipo == "junte". Agrupar documento.participantes por                                                              │
│ usuario_id (2 grupos). Para cada uno, distribucion_desde_fechas con sus                                                                │
│ fechas cede/recibe → (lunes_semana, trabaja, libra, num_noches). La                                                                    │
│ persona con num_noches == 3 va en las variables *_3_*, la de                                                                           │
│ num_noches == 4 en *_4_* (por construcción de LMVD/MJS uno de cada                                                                     │
│ siempre). junte_cambio_N_dias: lista de 7 (lunes..domingo), "N" en los                                                                 │
│ índices de trabaja, "" el resto (mismo contenido que espera                                                                            │
│ pdf.html, ver tests/test_pdf_junte_frames.py).                                                                                         │
│ - mostrar_junte=True y las variables junte_* al render; para el caso                                                                   │
│ normal, pasar mostrar_junte=False explícito (hoy no se pasaba nada,                                                                    │
│ Jinja lo trataba como falsy igualmente, pero mejor explícito).                                                                         │
│ - app/templates/documento_cambio/pdf.html: envolver los frames de                                                                      │
│ turno único (cede_franja_c, cede_fecha_c, recibe_franja_c,                                                                             │
│ recibe_fecha_c, companero_c) en {% if not mostrar_junte %} — no                                                                        │
│ aplican a un junte y hoy accederían a campos None                                                                                      │
│ (participante_solicitante no representa bien un junte de varias filas).                                                                │
│ El resto de cabecera (hospital/unidad/categoría/número/firmas/decisión) se                                                             │
│ queda igual, es común a cualquier tipo de hoja.                                                                                        │
│ - Tests: sustituir/ampliar tests/test_pdf_junte_frames.py para que al menos                                                            │
│ un test pase por generar_pdf_documento con un DocumentoCambio real                                                                     │
│ tipo junte (creado con el Paso 4) en vez de solo renderizar la plantilla                                                               │
│ a mano — cierra la salvedad que el propio archivo señala en su docstring.                                                              │
│ Mantener los tests actuales de layout (renderizado directo) como                                                                       │
│ regresión de las coordenadas de los @frame.   
│ Paso 6 — Ruta /documentos-cambio/nuevo                                                                                                 │
│                                                                                                                                        │
|app/routes/documento_cambio.py::nueva():                                                                                               │
|- Nuevo campo tipo en el formulario ("cambio" por defecto  "junte").                                                                  │
│ - Si tipo == "junte": leer junte_semana, junte_cadencia                                                                                │
│ ("LMVD"/"MJS"), junte_noches (lista de índices 0-6) — mismos nombres                                                                   │
│ de campo que ya usa publicar.html, para reutilizar directamente el JS de                                                               │
│ esa plantilla. Buscar la franja nombre="Noche" del grupo (mismo patrón                                                                 │
│ que _extraer_turnos_junte, ya con esa fragilidad conocida — no se                                                                      │
│ corrige aquí, fuera de alcance). Validar: semana no pasada, exactamente                                                                │
│ len(cadencia) noches marcadas, cedidas y aceptadas no vacías (se puede                                                                 │
│ extraer una función auxiliar a partir de la lógica ya en                                                                               │
│ _extraer_turnos_junte, o llamarla desde ahí si se refactoriza a                                                                        │
│ app/services/junte_semanal.py para no duplicar validación — a decidir                                                                  │
│ al implementar, prefiriendo reutilizar sobre duplicar).                                                                                │
│ - Llama a crear_documento_cambio_junte(...).                                                                                           │
│ - Mismo flujo de firmar_ambos que ya existe (no depende del tipo).                                                                     │
│ - Tests: POST con tipo junte crea el documento con las filas esperadas;                                                                │
│ validaciones (semana pasada, número de noches incorrecto, sin noches de la                                                             │
│ otra cadencia) devuelven error sin crear nada.                                                                                         │
│
│ Paso 7 — Plantilla nuevo.html                                                                                                          │
│                                                                                                                                        │
│ - Añadir selector de tipo (radio, mismo patrón visual tipo-opcion que                                                                  │
│ publicaciones/publicar.html): "Cambio de turno" (por defecto, formulario                                                               │
│ actual) / "Junte de noches".                                                                                                           │
│ - Sección section-junte (oculta por defecto, igual que en                                                                              │
│ publicar.html): junte_semana, radios junte_cadencia, grid de                                                                           │
│ checkboxes junte_noches generado por JS a partir de la semana elegida.                                                                 │
│ Reutilizar el bloque de JS de publicar.html (generarNochesGrid,                                                                        │
│ actualizarHintNoches, tabla CADENCIA) adaptado a este formulario en vez                                                                │
│ de extraerlo a un JS compartido (mismo criterio de "no sobre-ingenierizar"                                                             │
│ de CLAUDE.md; si al implementar se ve trivial compartirlo en un archivo                                                                │
│ js/junte-form.js común a las dos plantillas, mejor eso que duplicar).                                                                  │
│ - Ocultar/mostrar las secciones de turno único existentes según el tipo                                                                │
│ elegido (mismo patrón actualizarSecciones de publicar.html).                                                                           │
│ - Sin cambios en ver.html (ya pinta bien varias filas por participante) ni                                                             │
│ en el flujo de firmas.                                                                                                                 │
│
|Archivos clave                                                                                                                         │
│                                                                                                                                        │
│ - app/models/documento_cambio.py — columna tipo, constraint.                                                                           │
│ - migrations/versions/<nueva>.py — generada con flask db migrate.                                                                      │
│ - app/services/junte_semanal.py — distribucion_desde_fechas.                                                                           │
│ - app/services/factibilidad_documento_cambio.py — overlay siempre activo.                                                              │
│ - app/services/documento_cambio.py — crear_documento_cambio_junte,                                                                     │
│ rama junte en generar_pdf_documento.                                                                                                   │
│ - app/routes/documento_cambio.py — nueva().                                                                                            │
│ - app/templates/documento_cambio/nuevo.html, pdf.html.                                                                                 │
│ - Tests nuevos/ampliados: tests/test_models_documento_cambio.py,                                                                       │
│ tests/test_junte_semanal.py, tests/test_servicio_factibilidad_documento_cambio.py,                                                     │
│ tests/test_servicio_documento_cambio.py, tests/test_pdf_junte_frames.py,                                                               │
│ tests/test_documento_cambio_creacion.py.                                                                                               │
│                                                                                                                                        │
│ Verificación                                                                                                                           │
│                                                                                                                                        │
│ - pytest --testmon tras cada paso (todos los tests existentes en verde,                                                                │
│ sin regresión en los flujos cambio/cambio_dia/registrar_papel).                                                                        │
│ - flask db heads → exactamente 1 (head) tras la migración.                                                                             │
│ - Manual: levantar la app, crear una hoja tipo Junte de noches entre dos                                                               │
│ compañeros de la misma categoría/grupo, firmar ambos, autorizar como                                                                   │
│ supervisora, descargar el PDF y comprobar visualmente las dos rejillas                                                                 
│ rellenas.
