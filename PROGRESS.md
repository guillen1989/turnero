# Estado del desarrollo

## Fase actual
Fase 10 — Hoja de cambios digital (documento de cambio con firma)

## Paso actual / siguiente paso
Trabajando la lista de 9 mejoras pedidas por el usuario sobre `documento_cambio`/
`planilla_supervision` (registro manual de cambios en papel, visibilidad de
doblajes, añadir turno sin sustituir, tooltip con datos del cambio, reglas de
comprobación configurables — días consecutivos + descanso tras noche/nocturno—,
contadores de presencia por franja, reordenar nav de supervisora en 2 filas,
firma duplicada al decidir, y arrancar la comprobación de factibilidad de esas
reglas nuevas). Se resuelve en el orden que parezca mejor, sin bloquear en
ninguno salvo que haga falta una decisión del usuario.

- [x] Corregido el recuadro de firma duplicado al autorizar/denegar (ver más
  abajo, último paso completado).
- [ ] Registro manual de cambios en papel por la supervisora (nº de cambio
  asignado, visible en `/documentos-cambio/supervisora`, marcado como "de
  papel"). Decisión tomada sin bloquear en el usuario (encaja en "hazlo todo,
  pregúntame solo si hace falta"): como el cambio ya ocurrió y ya se firmó a
  mano en papel, no tiene sentido pedir firmas digitales ni dejarlo
  "pendiente de decisión" -- se registra directamente como `completo` +
  `decision_supervisora='autorizado'`, aplicándose ya a las planillas (que es
  el objetivo real: mantenerlas al día para que la comprobación de
  factibilidad de futuros cambios sea correcta). Paso 1a (hecho): columna
  `origen_papel` (bool, `server_default='false'`, un solo paso porque tiene
  default de servidor) en `DocumentoCambio` -- migración
  `4b1f1eeadd91_add_origen_papel_to_documento_cambio`. Paso 1b (hecho):
  `registrar_documento_cambio_papel(supervisora, usuario1, usuario2, ...)`
  en `app/services/documento_cambio.py` -- crea el documento con
  `estado='completo'`/`origen_papel=True` directamente (sin pasar por
  `pendiente_firmas`) y reutiliza `autorizar_documento` para volcarlo a
  planillas y notificar a los dos implicados, igual que un cambio digital ya
  autorizado. De paso, arreglado un bug latente que este caso destapó:
  `puedo_firmar` en `documento_cambio.ver()` solo miraba
  `ids_firmantes`, así que un documento `completo` sin ninguna
  `FirmaDocumentoCambio` (como los de papel) ofrecía firmar digitalmente un
  cambio que ya estaba cerrado -- ahora exige también
  `documento.estado != 'completo'`. `ver.html` añade un banner "Registrado
  desde hoja de papel" y cambia el badge por participante a "Firmado en
  papel" cuando `origen_papel` es `True`. 3 tests nuevos (columna, servicio,
  plantilla), sin regresiones (92 tests en
  `test_rutas_documento_cambio.py` + `test_servicio_documento_cambio.py`).
  Paso 1c (hecho, cierra el item #1 de la lista): ruta
  `GET/POST /documentos-cambio/registrar-papel` (solo supervisora, 403 si
  no) + plantilla nueva `registrar_papel.html` (dos selects de trabajador
  del grupo de la supervisora + turno que cede/recibe cada uno, sin nada de
  firma). Valida que los dos trabajadores sean distintos y de la misma
  categoría profesional (si no, error "Los dos trabajadores deben ser de la
  misma categoría profesional", igual que exige el resto del sistema para
  cualquier intercambio). Añadido enlace "Registrar cambio desde papel" en
  `/documentos-cambio/supervisora` y badge "Papel" junto al número de cambio
  para los `origen_papel=True` (cuidado al tocar la celda: el badge va en la
  misma línea que el texto del número para no romper el test existente que
  compara el `<td>` completo). 6 tests nuevos (login requerido, 403 no
  supervisora, lista de trabajadores, creación + redirect, validación de
  categoría, badge visible). Catálogo i18n: 15 cadenas nuevas añadidas a
  mano en `messages.pot`/`messages.po` (mismo criterio que el resto de
  entradas de deuda técnica de este archivo), `pybabel compile` sin
  errores. 107 tests pasando en
  `test_rutas_documento_cambio.py`+`test_servicio_documento_cambio.py`+`test_models_documento_cambio.py`,
  sin regresiones (90 tests de auth/dashboard también verificados).
- [x] Item #2 (visibilidad de doblajes para la supervisora en
  `/planilla/supervisión`): comprobado que ya estaba implementado -- el bucle
  `{% for turno in turnos_dia %}` de `planilla_supervision/index.html` junto
  con `get_turnos_mes_unidad` (agrupa por `(usuario_id, fecha)` permitiendo
  varios turnos) y el CSS `.supervision-celda .supervision-chip { display:
  block; ... }` ya renderizan cada franja como un chip apilado visible. Añadido
  test de regresión (`test_index_muestra_doblaje_con_dos_turnos_el_mismo_dia`)
  sin ningún cambio de código de producción.
- [x] Item #4 (tooltip del badge de cambio en `/planilla/supervisión` con
  datos concretos en vez de un texto genérico): `get_cambios_autorizados_mes_unidad`
  pasa a devolver un `CambioDia = namedtuple("documento", "descripcion")` en
  vez de un `DocumentoCambio` a secas -- `_describir_cambio_dia(participante,
  fecha)` (nuevo, en `app/services/planilla_supervision.py`) navega a
  `participante.documento.participantes` para encontrar al compañero del
  cambio y compone "Cambio con X (turno Y) del dd/mm/aaaa". El template solo
  cambia `cambio.id` -> `cambio.documento.id` y `title="Día afectado por..."`
  -> `title="{{ cambio.descripcion }}"`. Catálogo i18n actualizado (msgid
  nuevo con placeholders con nombre, msgid viejo retirado por quedar sin
  referencias). 2 tests nuevos de ruta + 1 de servicio + 1 de servicio
  actualizado (`.id` -> `.documento.id`). 167 tests passing
  (`pytest --testmon`, ventana limpia sin contención de la BD compartida).
- [x] Item #3 (añadir un turno extra a un día -p.ej. quedarse doblando de
  mañana a tarde- sin sustituir el que ya hay): comprobado que ya estaba
  implementado en toda la pila -- `añadir_turno` (servicio) es idempotente
  por `(usuario_id, fecha, franja_horaria_id)` y solo limpia el *estado
  especial* del día (libre/vacaciones/no_disponible), nunca otros turnos ya
  puestos; la ruta `POST /planilla/dia/añadir` y su alias legacy
  `/planilla/turno/añadir` delegan directamente en él; el selector "+
  Añadir" de `planilla/planilla.html` ya excluye del desplegable las franjas
  ya asignadas (`ids_asignados`) pero deja el resto disponibles sin límite
  de turnos por día. Añadido test de regresión de extremo a extremo
  (`test_dia_anadir_permite_turno_extra_sin_sustituir_el_existente` en
  `tests/test_planilla_rutas.py`) sin ningún cambio de código de
  producción. 11 tests passing (`test_planilla_rutas.py`).
- [x] Item #7 (los botones solo-supervisora del menú -- Supervisión de
  cambios, Supervisión de planilla, Importar planilla -- apretados junto al
  resto en escritorio): investigado primero si ya estaba resuelto (patrón de
  los items #2/#3), pero no era el caso -- el rediseño de nav con hamburguesa
  para móvil (commit `eabd05e`, 2026-06-23) solo toca el breakpoint <601px;
  en escritorio (>=601px) los enlaces siguen siendo una fila `flex-wrap` sin
  distinción, por lo que los 3 enlaces solo-supervisora se intercalaban con
  el resto según fuera cayendo el wrap. Solución (a petición explícita del
  usuario, que no le importa que esto complique el comportamiento en móvil
  para cuentas de supervisora): en `base.html`, los 3 enlaces
  solo-supervisora se envuelven en `<div class="nav-supervisora-row">`;
  en `main.css`, dentro de `@media (min-width: 601px)`, esa clase usa
  `flex: 1 0 100%` para forzar que siempre empiecen su propia fila dentro
  del nav `flex-wrap`, con `order: 10` para que caigan al final. En móvil no
  se añade CSS nuevo para esa clase -- al ser un `<div>` normal dentro del
  dropdown vertical existente, los enlaces se siguen apilando igual que
  antes (verificado visualmente con capturas Playwright a 1280px y 375px).
  2 tests nuevos en `tests/test_nav_base.py` (agrupación visible para
  supervisora, ausente para usuario normal). 85 tests passing
  (`test_nav_base.py`+`test_planilla_rutas.py`+`test_rutas_documento_cambio.py`).
- [x] Item #5 (pantalla de reglas de comprobación: máx. días consecutivos
  configurable + descanso obligatorio tras noche/nocturno de 12h): columna
  `limite_dias_consecutivos` (Integer, `server_default='8'`, un solo paso)
  en `GrupoIntercambio` -- migración `7ed9c5cc5e02` (single head verificado
  con `flask db heads`). El límite se guarda por grupo de intercambio (igual
  granularidad que `FranjaHoraria`, ya que es lo que define qué usuarios
  comparten planilla/matching). Nueva ruta `GET/POST
  /planilla/supervision/reglas` en `planilla_supervision.py` (solo
  supervisora, 403 si no, reutilizando `_exigir_supervisora`), plantilla
  `reglas.html` con un único campo numérico. La segunda regla (ningún turno
  puede empezar antes de las 14:00 el día siguiente a un turno que cubra
  0:00-6:00) se documenta en la pantalla como texto fijo -- el enunciado del
  usuario no pide que sea configurable, solo el límite de días. Enlace
  "Reglas de comprobación" añadido al `nav-supervisora-row` del item #7.
  Catálogo i18n: 6 cadenas nuevas añadidas a mano en
  `messages.pot`/`messages.po` (mismo criterio que el resto de deuda técnica
  de este archivo -- un `pybabel extract` completo arrastra reformulaciones
  pendientes de otras pantallas que no tocan este paso). 5 tests nuevos en
  `tests/test_reglas_comprobacion.py` (default a 8, 403 sin supervisora, GET
  muestra el valor, POST actualiza, POST rechaza valores <= 0). Verificado
  visualmente con Playwright (pantalla + nav) a 900px. 43 tests passing
  (`test_reglas_comprobacion.py`+`test_nav_base.py`+
  `test_rutas_planilla_supervision.py`+`test_servicio_planilla_supervision.py`).
  Siguiente: item #6 de la lista (contadores de presencia por franja encima
  de las columnas de día en `/planilla/supervisión`). Nota: item #9 (motor
  de comprobación de factibilidad que use estas reglas) queda para después,
  ya que depende de que ambas reglas de este paso existan primero -- solo
  está implementada la persistencia/configuración, no el motor que las
  aplica todavía.

Fuera de la Fase 10, iniciativa pendiente sin retomar aún: carga masiva de
planilla por parte de la supervisora, sustituyendo (para las unidades que lo
adopten) la cumplimentación manual día a día de `app/routes/planilla.py`.
Motivación: reducir fricción a supervisoras y trabajadores, y permitir
comprobar la factibilidad real de una hoja de cambio (ya existe
`comprobar_factibilidad` en `app/services/factibilidad_documento_cambio.py`)
contra los datos reales de la planilla en vez de depender de que cada usuario
la rellene a mano.

Se planificó en 3 pasos:
1. Anonimizar un archivo real de ejemplo (formato de exportación "ILOG":
   texto separado por tabuladores con extensión `.xls`) para poder
   desarrollar sin usar datos reales de personal — HECHO (ver más abajo).
2. Parser puro del formato ILOG — HECHO (ver más abajo).
3. D1 confirmado por el usuario: turno deslizante de 13:00 a 20:00 en
   esta unidad. MC/TC se tratan igual que M/T a efectos de qué turno
   trabaja y de solapamientos (la reducción de jornada no tiene un
   horario propio fiable: unas veces son menos horas, otras menos días
   al mes, pero ambas aparecen con el mismo código) — decisión
   confirmada con el usuario, no modelamos horas reducidas por persona.

Hecho — paso 3a (modelos de mapeo persistente):
`app/models/planilla_import.py` — `MapeoCodigoTurno` (código de planilla
-> `FranjaHoraria`, único por `grupo_intercambio_id` + `codigo`, se
configura una vez por grupo) y `MapeoTrabajadorPlanilla` (número de
empleado -> `Usuario`, único por `unidad_id` + `numero_empleado`,
`usuario_id` nullable mientras no hay cuenta o no se ha confirmado la
asociación). Migración `16d83172b341` (tablas nuevas, sin datos previos,
no aplica el patrón de tres pasos). Nota de mantenimiento: al generarla,
`flask db upgrade` falló porque la base de dev local (`cambiaturnos`,
no la de test) tenía la columna `firma_supervisora` ya aplicada pero
`alembic_version` desactualizada a la revisión anterior — desfase de
bookkeeping preexistente, no relacionado con este cambio. Se resolvió
con `flask db stamp 7920cee19df7` antes de migrar (no se re-ejecutó DDL,
solo se corrigió el registro de versión). `flask db heads` da
exactamente 1 head. Cubierto por `tests/test_models_planilla_import.py`
(7 tests: creación, unicidad por grupo/unidad, mismo código o número en
grupos/unidades distintas es válido, vínculo a `Usuario`).

Hecho — paso 3b (servicio de resolución):
`app/services/planilla_matching.py` — `resolver_franja`/
`establecer_mapeo_codigo` (idempotente, permite reconfigurar) para el
mapeo de código de turno, y `resolver_o_crear_trabajador` (por número de
empleado; reutiliza el mapeo existente en cargas siguientes y solo crea
fila nueva para números no vistos antes, actualiza `nombre_planilla` si
cambió pero conserva `usuario_id` ya vinculado) / `vincular_usuario` /
`trabajadores_sin_vincular` (para que la supervisora revise pendientes)
para el mapeo de trabajador. Cubierto por
`tests/test_servicio_planilla_matching.py` (9 tests). 105 tests pasan en
el conjunto de archivos relacionados con planilla/factibilidad, sin
regresiones.

Hecho — paso 4 (orquestador):
`app/services/importar_planilla.py` (`importar_planilla`) une parser +
`planilla_matching` + escritura real. Reglas de diseño:
- Todo o nada respecto a códigos de turno: si falta el mapeo de algún
  código usado en el archivo a `FranjaHoraria` para el grupo de la
  unidad, no escribe nada y devuelve qué códigos faltan
  (`codigos_sin_mapear`). Se decidió así para no importar unos turnos sí
  y otros no de forma silenciosa.
- Los trabajadores sin `Usuario` vinculado no bloquean el resto de la
  importación: se registran/actualizan como pendientes
  (`trabajadores_pendientes`) vía `resolver_o_crear_trabajador` y no se
  les escribe ningún turno hasta que se vinculen.
- Para los vinculados, escribe cada turno con `añadir_turno` y publica
  el mes con `publicar_mes` (la carga de la supervisora hace de
  publicación; no queda como borrador). Reutiliza el vínculo ya hecho en
  cargas de meses anteriores sin repetir trabajo (verificado con una
  carga de enero seguida de otra de febrero para el mismo trabajador:
  no duplica `MapeoTrabajadorPlanilla`, sí escribe los turnos nuevos).

Cubierto por `tests/test_importar_planilla.py` (4 tests). 109 tests
pasan en el conjunto de archivos relacionados con planilla/factibilidad,
sin regresiones.

Hecho — paso 5 (ruta HTTP):
`app/routes/planilla_import.py` (blueprint `planilla_import`, prefijo
`/planilla/importar`, registrado en `app/__init__.py`), todas las rutas
exigen `current_user.es_supervisora` (403 si no):
- `GET /` (`index`): formulario de subida + tabla de
  `trabajadores_sin_vincular` de la unidad, cada fila con un desplegable
  (`usuarios_disponibles_para_vincular`, nueva función en
  `planilla_matching.py`) para vincular manualmente.
- `POST /` (`subir`): lee el archivo subido (decodificado como
  `latin-1`, igual que el resto del parser ILOG) y llama a
  `importar_planilla`. Si faltan códigos por mapear, redirige a
  `codigos` con el aviso de qué códigos son; si no, aviso de cuántos
  trabajadores se actualizaron y cuántos quedan pendientes de vincular.
- `GET/POST /codigos` (`codigos`): formulario con un campo de texto por
  `FranjaHoraria` del grupo (códigos separados por comas) que llama a
  `establecer_mapeo_codigo` por cada código introducido.
- `POST /<mapeo_id>/vincular` (`vincular`): vincula manualmente un
  `MapeoTrabajadorPlanilla` pendiente a un `Usuario` de la misma unidad
  (403 si el mapeo es de otra unidad, aviso si el usuario elegido no es
  válido).

Plantillas nuevas `planilla_import/index.html` y
`planilla_import/codigos.html`, mismas convenciones que el resto del
proyecto (`form-container`, `btn btn-primary`/`btn-secondary`,
`csrf_token()` en cada formulario). Cubierto por
`tests/test_rutas_importar_planilla.py` y el 10º test añadido a
`tests/test_servicio_planilla_matching.py` (para
`usuarios_disponibles_para_vincular`). Catálogo i18n: 19 cadenas nuevas
añadidas a mano en `translations/es/LC_MESSAGES/messages.po` (mismo
criterio que el resto de entradas de deuda técnica de este archivo: el
catálogo lleva tiempo desincronizado, ver más abajo), `pybabel compile`
sin errores.

Hecho — vinculación retroactiva al registrarse:
`sugerir_trabajador_planilla(unidad, nombre_usuario)` en
`planilla_matching.py` compara por tokens (minúsculas, sin acentos, sin
importar orden ni comas) el nombre del usuario contra los
`trabajadores_sin_vincular` de su unidad; solo sugiere si hay
coincidencia exacta de tokens (evita vincular a la persona equivocada
con una coincidencia parcial). `auth.registro()` la consulta justo
tras crear la cuenta y, si hay sugerencia, redirige a la nueva ruta
`GET/POST /auth/registro/vincular-planilla/<mapeo_id>`
(`confirmar_vinculo_planilla`, requiere login, 403 si el mapeo es de
otra unidad) donde el propio usuario confirma o descarta el vínculo
antes de continuar al onboarding; si descarta o no hay sugerencia,
sigue quedando pendiente para que la supervisora lo vincule a mano
desde `/planilla/importar` como hasta ahora. Plantilla nueva
`auth/confirmar_vinculo_planilla.html`. 11 tests nuevos (5 del
matcher puro en `test_servicio_planilla_matching.py`, 6 de la ruta en
`test_auth_routes.py`). Catálogo i18n actualizado a mano (7 cadenas
nuevas), `pybabel compile` sin errores.

Pendiente para completar la funcionalidad (no empezado):
- Motor de reglas laborales (turnos consecutivos, descanso tras noche):
  todavía no se ha empezado; pendiente de que el usuario aclare qué
  reglas son imprescindibles para el MVP.

---

Nueva sub-iniciativa (mismo dominio de planilla, independiente de la
anterior): visor tipo calendario para que la supervisora vea, en una
matriz trabajador x día del mes, quién trabaja qué turno cada día y qué
días vinieron de un cambio ya autorizado. Puntos débiles identificados
con el usuario antes de implementar: ámbito por `unidad` (no
`grupo_intercambio`, que puede abarcar varias unidades); evitar N+1 con
consultas batch por unidad+mes en vez de usuario a usuario; no duplicar
el turno "antes/después" del cambio (la planilla ya refleja el estado
final tras `volcar_documento_a_planillas`, solo hace falta una
marca/badge con enlace al documento); densidad de la celda (turno +
estado + saliente + nota no caben todos inline con decenas de filas x
~30 columnas, se deja para un popover/tooltip). `anular_documento`
(servicio ya existente, ver Fase 10) ya cubre la futura necesidad de
"anular un cambio" que planteó el usuario — no hace falta construirla.
La futura "modificación unilateral de un turno de un trabajador" (p.ej.
dar el día libre) no encaja en `ParticipanteDocumentoCambio` (no hay
contraparte) y se deja pendiente de decidir su propio modelo, para que
sea igual de anulable/trazable que un cambio normal.

Paso 1 (servicios batch, hecho): `app/services/planilla_supervision.py`
— `get_turnos_mes_unidad`, `get_estados_mes_unidad` y
`get_cambios_autorizados_mes_unidad`, cada uno con una única consulta
por unidad+mes (agrupadas en un dict por `(usuario_id, fecha)` en
Python) en vez de un bucle por trabajador.
`get_cambios_autorizados_mes_unidad` solo incluye `DocumentoCambio` con
`decision_supervisora == "autorizado"` y `anulado == False`, y considera
tanto `turno_cede_fecha` como `turno_recibe_fecha` de cada participante
(pueden caer en meses distintos si el cambio cruza el mes). 11 tests
nuevos (`tests/test_servicio_planilla_supervision.py`), sin regresiones
en el resto de la suite de planilla/documento_cambio.

Paso 2 (ruta HTTP + plantilla, hecho): nuevo blueprint
`app/routes/planilla_supervision.py` (`GET /planilla/supervision/`,
protegido por `_exigir_supervisora()` igual que `planilla_import.py`;
`anyo`/`mes` como query params con el mismo patrón prev/next que
`planilla.index`). Plantilla `planilla_supervision/index.html`: tabla
con los trabajadores de `current_user.unidad` como filas (columna de
nombre fija con `position: sticky`) y un día del mes por columna,
envuelta en `.table-scroll` para scroll horizontal. Cada celda muestra
el/los turno(s) del día (chip con el color de la `FranjaHoraria`,
soporta doblaje apilando chips), el estado del día si lo hay, y si el
día está en `get_cambios_autorizados_mes_unidad` un badge enlazando a
`documento_cambio.ver`. Enlace añadido al menú principal junto a
"Supervisión de cambios". 6 tests nuevos
(`tests/test_rutas_planilla_supervision.py`): login requerido, 403 si
no es supervisora, filtrado por unidad, turno/estado visibles, enlace
al documento de un cambio autorizado. 124 tests pasando sin
regresiones en toda la suite de planilla/documento_cambio.

Paso 3 (modificación unilateral de turno, modelo + servicio, hecho):
nuevo modelo `AjustePlanillaSupervisora` (`app/models/planilla.py`,
migración `b9d6698355e6`) que registra usuario afectado, quién hizo el
cambio, la fecha, una descripción legible del antes/después (p. ej.
"Mañana" → "libre") y un motivo opcional. No usa
`ParticipanteDocumentoCambio` porque aquí no hay dos partes que se
ceden turno entre sí, es una decisión unilateral de la supervisora.
Nuevo servicio `ajustar_turno_trabajador(supervisora, trabajador,
fecha, tipo_estado=None, franja_id=None, motivo=None)` en
`planilla_supervision.py`: sustituye por completo el turno/estado del
día (borra turnos + estado existentes, aplica el nuevo si se indica) y
deja el `AjustePlanillaSupervisora` como rastro. 5 tests nuevos cubren
asignar estado sobre día vacío, reemplazar turno existente, asignar
turno sobre estado existente, vaciar el día sin nada, y guardar el
motivo. 137 tests pasando sin regresiones.

Paso 4 (ruta HTTP + UI de modificación, hecho): nuevo servicio batch
`get_ajustes_mes_unidad` (último ajuste por (usuario_id, fecha), mismo
patrón que `get_cambios_autorizados_mes_unidad`). Ruta `POST
/planilla/supervision/ajustar` en el mismo blueprint: valida que el
trabajador sea de `current_user.unidad`, resuelve la `seleccion` del
formulario (estado, id de franja del grupo, o `"vaciar"` explícito) y
llama a `ajustar_turno_trabajador`. En la plantilla, cada celda de la
matriz es ahora un botón que abre un modal (JS puro, sin dependencias)
con un select turno/estado/vaciar + motivo opcional, que hace POST al
mismo sitio y redirige de vuelta al mes que se estaba viendo. Las
celdas con un `AjustePlanillaSupervisora` muestran un icono con
tooltip (antes → después + motivo) -- sin enlace propio, a diferencia
del badge de cambios autorizados, porque no hay página de detalle para
un ajuste individual (no la necesita, es MVP). Migración
`b9d6698355e6` aplicada también en la base de datos de desarrollo
(`flask db upgrade`) -- si se despliega, aplicarla igual en
staging/producción antes o durante el deploy. 8 tests nuevos + 3 de
`get_ajustes_mes_unidad`: 148 tests pasando sin regresiones. Probado a
mano en el navegador (vía curl) contra la base de datos de desarrollo
real: la celda cambia de turno a "Libre", aparece el icono con el
tooltip correcto y el flash de confirmación.

Fix (hecho): el usuario reportó no encontrar la carga de planilla en la
app ("ya estuvimos trabajando en esto pero no lo veo"). Diagnóstico: la
funcionalidad estaba completa (parser, mapeo, orquestador, ruta
`planilla_import` con formulario de subida y configuración de códigos,
137+ tests) pero nunca se enlazó desde el menú -- `base.html` solo tenía
el enlace a "Supervisión de planilla" (el visor de calendario,
`planilla_supervision.index`), no a "Importar planilla"
(`planilla_import.index`, donde está el formulario de subida). Añadido
el enlace que faltaba junto a los demás de supervisora en `base.html`.
1 test nuevo (`test_menu_enlaza_a_importar_planilla_para_supervisora`
en `tests/test_rutas_importar_planilla.py`): confirma que una
supervisora ve el enlace en el menú; rojo antes del cambio, verde
después. La cadena "Importar planilla" ya existía en el catálogo i18n
(añadida en el paso 5 de esta misma iniciativa aunque no se usara
todavía), no hizo falta tocar `messages.po`.

Nota de entorno de test detectada durante este arreglo: el intérprete
`/usr/bin/python3` (python3.8, el que resuelve el binario
`~/.local/bin/pytest`) no puede ejecutar la suite -- el código usa
sintaxis `list[X]` (PEP 585) que requiere Python 3.9+, y además tenía
Flask-Login/Flask-WTF desactualizados respecto a `requirements.txt`
(rotos contra el Werkzeug/Flask instalados). Los tests de este cambio
se ejecutaron con `/home/portatil/anaconda3/bin/python -m pytest`, que
sí trae Python 3.12. Pendiente de confirmar con el usuario cuál es el
intérprete correcto para este proyecto en esta máquina (no había un
venv dedicado en el repo ni referenciado en `.python-version`).

Siguiente paso: a decidir con el usuario. Pendiente de esta
sub-iniciativa: densidad de la celda si hace falta mostrar también
saliente/nota (popover/tooltip en vez de inline).


## Paso anterior
Paso aparte, fuera de la Fase 10 (fix de infraestructura de tests):
la suite de tests compartía la misma base de datos Postgres local
(`cambiaturnos_test`, nombre heredado del directorio del proyecto antes
de renombrarse a `turnero`) entre distintos checkouts/worktrees cuando
había varios agentes trabajando en paralelo. Sus `TRUNCATE`/
`create_all`/`drop_all` concurrentes colisionaban entre sí, causando
deadlocks, tablas inexistentes a mitad de test y ejecuciones
anormalmente lentas (37m45s frente a los ~18min normales). Se modifica
`tests/conftest.py`: la fixture `app` deriva ahora un nombre de base de
datos único por checkout (sufijo = hash SHA1 de los 8 primeros
caracteres del path absoluto del proyecto) y crea esa base de datos si
no existe (conexión de mantenimiento con `psycopg2` a la base
`postgres`, ignorando `DuplicateDatabase`). Mismo checkout → misma base
de datos (se reutiliza entre ejecuciones), checkouts distintos → bases
de datos distintas (sin colisión posible). No requiere tocar `.env` ni
configuración manual. Compatible con CI (`.github/workflows/ci.yml`),
que ya fija `TEST_DATABASE_URL` a una base efímera propia — el sufijo
simplemente se añade a lo que ya esté configurado. Verificado con la
suite completa sin `--testmon`: 1078 passed, 0 regresiones.

Paso anterior, también fuera de la Fase 10 (a petición del usuario): el enlace
"Ver todos los detalles" de la landing pública apuntaba a `/como-funciona`,
que exige login (`@login_required`) — un visitante anónimo acababa en el
formulario de login en vez de ver el contenido. Se crea una página nueva
y pública, `main.funcionalidades` (`/funcionalidades`, sin
`@login_required`), con plantilla propia `main/funcionalidades.html` que
reutiliza el contenido de `como_funciona.html` (los mismos 9 pasos, con
un paso nuevo sobre la hoja de cambio digital) pero sin los enlaces a
páginas privadas (calendario, publicar, planilla, buscar cambios) —
sustituidos por un único CTA final a `auth.registro`/`auth.login`. Se
deja intacta `main.como_funciona` (onboarding post-login, ya cubierta
por `tests/test_onboarding.py`) y solo se actualiza el `href` de
"Ver todos los detalles" en `main/index.html`. Cubierto por 5 tests
nuevos en `tests/test_landing.py` (accesible sin login, contiene las
secciones clave, no enlaza a páginas privadas, no toca `current_user`).
Catálogo i18n: 9 cadenas nuevas añadidas a mano en
`messages.po`/`messages.pot` (mismo criterio que las entradas de deuda
técnica de más abajo), `pybabel compile` sin errores. No toca el flujo
de matching ni el modelo de datos.

Paso anterior, también fuera de la Fase 10: landing
pública ampliada. `main.index` (anónimo) ya solo mostraba el `.hero`
con título/CTA; se añaden dos secciones a `main/index.html` — "Así de
fácil" (resumen de 3 pasos, reutilizando `.onboarding-steps` de
`como_funciona.html`, con enlace "Ver todos los detalles" hacia esa
página) y "Por qué Turnero" (5 bullets de propuesta de valor). CSS
nuevo (`.landing-section`, `.landing-section-title`,
`.landing-section-link`, `.landing-features`) en `main.css`. Cubierto
por `tests/test_landing.py` (contenido presente para anónimos, enlace a
"Cómo funciona", ausente para usuarios autenticados, que van directos a
su hero sin las secciones nuevas). Catálogo i18n: 14 cadenas nuevas
añadidas a mano en `messages.po`/`messages.pot` (mismo criterio que la
entrada de deuda técnica de más abajo: un `extract`+`update` completo
sigue arrastrando el desfase histórico del catálogo), `pybabel compile`
sin errores. No toca el flujo de matching ni el modelo de datos.
Verificado con el cliente de test de Flask (200 OK, HTML bien formado);
sin verificación visual en navegador real por ser una sesión en
background.

Petición del usuario: grabar el motivo de denegación en el PDF, que la
supervisora también pueda firmar la hoja (autorizar/denegar), poder
reutilizar su firma guardada como ya hacen los participantes, y mostrar
el motivo de denegación en la tabla de "Supervisión de cambios".

Hecho hasta ahora: columna `firma_supervisora` en `DocumentoCambio`
(nullable, migración `7920cee19df7`) y `autorizar_documento`/
`denegar_documento` (`app/services/documento_cambio.py`) aceptan un
`imagen_firma` opcional que, si viene, se guarda ahí. Opcional a nivel de
servicio a propósito: no ata el servicio a HTTP y no rompe los muchos
tests que ya llaman a estas funciones directamente sin firma (flujos
internos); es la ruta HTTP la que de verdad la exige.

Hecho también: rutas `/autorizar` y `/denegar` (individuales) exigen
`imagen_firma` igual que ya exige `firmar_documento` a los
participantes, con la misma opción de "guardar esta firma"/"usar firma
guardada" (`current_user.firma_guardada`, ya genérico en `Usuario`
desde antes) — canvas propio en cada uno de los dos formularios de
`ver.html` (autorizar/denegar), mismo patrón visual que el resto
(`.firma-canvas` + `initFirmaForm`). Las acciones en bloque
(`bloque_aceptar`/`bloque_denegar`) no piden firma por documento
(inviable dibujar una por cada fila seleccionada): usan
`current_user.firma_guardada` si existe, y si no, bloquean la acción
entera pidiendo que la guarde antes (en `/perfil/cuenta` o firmando un
documento individual con "guardar firma" marcado).

Hecho también: plantilla del PDF (`documento_cambio/pdf.html`) rellena
el hueco real "INFORME POR PARTE DE LA SUPERVISORA DE LA UNIDAD:" del
impreso (coordenadas calibradas contra el escaneo, igual que el resto
de @frame de esta plantilla): motivo de denegación en las dos líneas en
blanco del informe, marca "X" en Favorable/Desfavorable según
`decision_supervisora`, fecha de la decisión y firma de la supervisora.
Todo el bloque queda vacío mientras `decision_supervisora == 'pendiente'`,
igual que el papel en blanco. Verificado visualmente generando PDFs de
prueba (autorizado y denegado) y rasterizándolos con `pdftoppm`.

Hecho también: columna "Motivo" en la tabla de "Supervisión de cambios"
(`documento_cambio/supervisora.html`), con `documento.motivo_denegacion`
visible por fila (vacía si no se ha denegado).

Catálogo i18n: `pybabel extract -k _l` (el proyecto usa `_l` de
Flask-Babel en varios formularios de `app/forms/`, aparte de `_`) más
`pybabel update` regeneró un diff enorme (~1300 líneas, 67 entradas
`fuzzy` mal emparejadas) porque el catálogo llevaba ya tiempo
desincronizado de `app/routes/auth.py` (los números de línea en los
comentarios `#:` no correspondían al archivo real, de alguna sesión
anterior que no volvió a compilar el catálogo) -- arreglar eso de raíz
no es parte de este cambio y mezclarlo habría hecho el diff imposible
de revisar. En su lugar, añadidas a mano las ~9 cadenas nuevas de esta
feature en `translations/messages.pot` y `translations/es/LC_MESSAGES/messages.po`
(mismo formato y ubicación relativa que ya usa el archivo), y
`pybabel compile` sin errores. Pendiente como deuda técnica aparte:
regenerar el catálogo completo con cuidado (revisando cada fuzzy a
mano) en su propio commit, no mezclado con una feature.

Feature completa: PDF con motivo de denegación, firma de la
supervisora (autorizar/denegar individual + acciones en bloque con
firma guardada), y motivo visible en la tabla de supervisión. 1067
tests unitarios/integración passing (11 nuevos de esta feature).

Antes de eso: "Nueva hoja de cambio" deja elegir entre esperar a la firma del compañero
(como hasta ahora) o firmar los dos ya mismo desde el mismo dispositivo,
para el caso de que estén rellenando el cambio juntos. Pensado también
para facilitar la adopción gradual por parte de jefes reticentes: ya
pueden usar la hoja de cambio electrónica como sustituto simple del papel
(cambios ordenados y fáciles de consultar) sin depender de que cuaje antes
la comprobación de factibilidad contra planillas. Sin siguiente paso
concreto pendiente en esta parte de la fase.

Antes de eso: añadida la anulación de cambios ya autorizados (deshace
planilla y, si viene de un match, reabre match/publicaciones) y la
selección en bloque en "Supervisión de cambios" (PDF combinado,
aceptar/denegar/anular en bloque).

Antes de eso: firma guardada — feedback del usuario tras probarla en
staging: la sección en `/perfil/cuenta` no se encuentra bien, se deja
donde está (no se mueve), pero además se ofrece guardar la firma en el
momento de firmar (ver siguiente entrada del changelog). Recién enviado a
staging, pendiente de feedback del usuario sobre esta segunda iteración.

Antes de eso: el usuario decidió quedarse con la vista de tabla:
"Supervisión de cambios" es ahora la única vista (una fila por cambio),
con filtros y navegación por mes/año.

Ya ejecutado contra el staging real (con confirmación explícita del
usuario): `scripts/seed_staging.py` (ampliación de UCO) y las variables
`DEMO_SUPERVISORA_LOGIN_EMAIL`/`_PASSWORD` en Railway (entorno staging).

Antes de eso: retomado el paso 10 (enganche con el motor de matching),
parcialmente: al confirmar un match directo **simétrico** (cambio↔cambio:
ambas partes ceden y reciben un turno con franja concreta, venga de
publicación automática o de "Me interesa"), la app crea y firma el
DocumentoCambio sola, sin ningún paso manual — el usuario dibuja su firma
en el mismo momento de pulsar "Confirmar" y, en cuanto confirma la otra
parte, el documento queda completo. `match_admite_documento_cambio`
(app/services/documento_cambio.py) es la condición: solo `directo_2` con
las 2 participaciones teniendo turno_cedido Y turno_aceptado con franja
concreta (no "cualquier turno"). Fuera de scope todavía, como ya estaba
decidido: **cadenas de 3/4 bandas y coincidencias asimétricas
(regalo/petición) siguen sin firma obligatoria ni documento automático**
— para esos casos, y para cambios sin match de por medio, sigue
disponible "Mis hojas de cambio > Nueva hoja de cambio" tal cual.

Contexto: petición del usuario en otra sesión en paralelo ("al confirmar
un cambio el usuario debe poder firmarlo también, así queda todo listo
por su parte"), resuelta primero en un branch aparte sobre `main` con un
modelo propio (columna `firma_data` en `MatchParticipacion` + PDF propio)
antes de descubrir que esta rama (`staging`) ya tenía construido un
sistema de hoja de cambio digital mucho más completo (`DocumentoCambio`,
supervisora, email, PDF fiel al impreso). Se descartó el modelo propio y
se reaprovechó solo la idea de "firmar en el momento de confirmar",
enganchándola al `DocumentoCambio` ya existente en vez de duplicar
firma/PDF.

Paso 11 completado (fusiona los pasos 1-3 del enganche): `match_admite_documento_cambio(match)`
y `crear_documento_cambio_desde_match(match)` (`app/services/documento_cambio.py`)
— crea el documento con `match_id` y participantes derivados de los
turnos del match, sin retipear nada; `POST /matches/<id>/confirmar`
exige firma para esos matches y, con ella, crea (si no existe) el
documento y llama a `firmar_documento`, reutilizando la lógica de firma
ya existente (no duplica notificación de "pendiente de firma": la de
`confirmar_participacion` ya cumple ese papel). `MatchCambio.documento_cambio`
(back_populates nuevo) para poder enlazarlo desde plantillas. Canvas de
firma en `dashboard.html` (mismo patrón visual que ya usaba
`/documentos-cambio`, reutiliza la clase `.firma-canvas` existente):
el botón "Confirmar" de un match que admite documento abre el modal en
vez de enviar el formulario directo; solo envía si se ha dibujado algo.
Enlace "Ver hoja de cambio" cuando el documento queda completo.

Al rebasar sobre el HEAD real de `staging` (que había avanzado con la
numeración de cambios por unidad mientras se hacía este trabajo),
`crear_documento_cambio_desde_match` necesitó rellenar también
`unidad_id`/`numero_unidad` (columnas NOT NULL añadidas después) — fix
de una línea, detectado por los tests existentes al re-ejecutar la
suite tras el rebase, no fue necesario tocar nada más.

Tests nuevos: `tests/test_documento_cambio_desde_match.py` (8, condición
de aplicabilidad + creación desde match), `tests/test_confirmar_con_documento.py`
(11, integración HTTP: firma obligatoria solo en simétricos, documento
se crea/firma/completa, cadenas y asimétricos sin cambios, reconfirmar
tras desconfirmar no duplica firma), 2 tests de plantilla en
`test_dashboard.py`, 2 tests E2E con Playwright
(`e2e/test_confirmar_firma_documento.py`) que dibujan de verdad en el
canvas — uno confirma con éxito y comprueba en BD que el documento queda
`pendiente_firmas` con 1 firma, el otro comprueba que sin dibujar nada
no se envía el formulario. Catálogo i18n actualizado (pybabel
extract/update/compile, 4 `#, fuzzy` corregidos a mano). 968 tests
unitarios/integración + 14/17 E2E passing — los 3 E2E que fallan
(`test_documento_cambio.py::test_hoja_de_cambio_golden_path_completa`,
`test_sintetica_golden_path.py::test_golden_path_cambio_a_3`,
`test_sintetica_staging.py::test_golden_path_staging`) **ya fallaban
igual en un checkout limpio de `origin/staging` sin ningún cambio de
esta rama** (verificado en un worktree temporal aparte antes de dar
por buena la rama) — el primero es un test desactualizado desde
`827cd00` (exige "Notas para ilog" a un usuario que no es supervisora,
la condición cambió y el test no se actualizó), los otros dos parecen
inestabilidad/entorno preexistente, no relacionados con este trabajo.

Siguiente paso: a definir con el usuario. Pendiente: los 3 E2E
preexistentes que fallan (ver arriba) siguen sin arreglar, quedaron
fuera de scope de este trabajo.

Cola de pendientes que el usuario pidió abordar seguidos, en el orden
que mejor convenga: (1) recomprobar factibilidad en la 2ª firma — HECHO,
(2) firma cruzada entre cuentas reales — HECHO, (3) número de cambio
junto a la fecha — HECHO, (4) mejorar el PDF — HECHO (el PDF ahora usa
el escaneo real del impreso como fondo a página completa, con los
campos en las mismas coordenadas y dimensiones que sus huecos en el
impreso — ver el "Paso anterior" correspondiente más abajo), (5)
listado de "mis hojas de cambio" — HECHO, (6) enviar los cambios por
email a los implicados — HECHO, (7) cuenta de supervisora con acceso a
todos los cambios — HECHO, (8) botón autorizar/denegar en la cuenta de
supervisora, con motivo obligatorio al denegar — HECHO. Además, dos
peticiones sueltas del usuario ya resueltas: motivo obligatorio al
denegar (visible para los implicados) y el email de hoja de cambio
completa ahora es opcional por usuario (toggle en
`/notificaciones`) — HECHO, y el aviso de autorización/denegación
incluye ahora los datos del cambio (quiénes lo hacen y qué día/turno
libra y trabaja cada uno), no solo el número de hoja/motivo — HECHO.
Pausado
explícitamente aquí a petición del usuario (2026-07-16): **(9) cadenas
a 3/4 bandas y juntes de noches y (10) enganche con el motor de
matching NO se implementan por ahora** — son bastante más grandes que
los anteriores (tocan el formulario de creación, hoy fijo a 2 personas;
la plantilla del PDF, hoy con 2 huecos de firma; y "juntes de noches"
no encaja con los campos turno_cede/turno_recibe actuales — es un
intercambio de una semana de noches, no un turno suelto). Antes de
retomarlos hace falta aclarar con el usuario cómo se construye una
cadena a 3 a mano y qué campos necesita un junte de noches. La nota
sobre "confirmar un match aparejado con firmar" (2026-07-16, ver el
propio texto de la conversación si hace falta el detalle completo) sigue
siendo válida para cuando se retome el paso 10.

## Paso anterior
fix(documento-cambio): el PDF ya no corta el texto de los campos contra
la línea impresa -- pedido explícito del usuario tras ver el resultado
del paso anterior ("el texto queda demasiado abajo"). Los 12 `@frame`
de campos de texto (no las firmas ni el número, que ya estaban bien)
suben 2mm (su `top` baja 2mm en la coordenada de página, que crece
hacia abajo). Sin test nuevo: es un ajuste visual de coordenadas, no de
comportamiento, igual que el resto de retoques de maquetación de esta
fase -- verificado con `pdftoppm` como los anteriores.

feat(documento-cambio): numero_unidad -- numeración absoluta por unidad,
no el id global de Postgres -- pedido explícito del usuario: "solo
puede haber un cambio #3 del 7 de julio de 2026", es decir, cada unidad
lleva su propia secuencia 1, 2, 3... como hacía la ayudante a mano,
independiente de cuántos cambios haya creado el resto de unidades de la
app. Nuevas columnas en `documento_cambio`: `unidad_id` (la del
creador, congelada al crear el documento) y `numero_unidad` (calculado
en `crear_documento_cambio` con `MAX(numero_unidad) WHERE unidad_id=...
+ 1`), con `UniqueConstraint(unidad_id, numero_unidad)` para que la
base de datos garantice la invariante aunque hubiera una condición de
carrera (aceptable en un MVP de bajo tráfico: ante colisión, lanza
`IntegrityError` en vez de crear un número duplicado en silencio).
Migración `b6770d428a60`, patrón de tres pasos (columnas ya con filas
reales en staging): nullable → backfill (unidad = la del creador;
numero_unidad = `ROW_NUMBER() OVER (PARTITION BY unidad_id ORDER BY
id)`) → NOT NULL + constraint. Backfill verificado a mano contra una
base de datos de prueba con filas intercaladas de dos unidades distintas
antes de aplicarlo. Todas las plantillas y notificaciones que mostraban
"Nº X" (`ver.html`, `lista.html`, `supervisora.html`, `pdf.html`, email
de hoja completa, notificación de autorizar/denegar) pasan de
`documento.id` a `documento.numero_unidad`; `documento.id` se mantiene
tal cual para las URLs y como semilla del hash de la firma, que no son
visibles para el usuario. 2 tests nuevos (secuencia independiente por
unidad; el id global puede ir por delante sin que se note en el número
mostrado) + 4 tests de `test_models_documento_cambio.py` actualizados
(construían `DocumentoCambio` a pelo, sin pasar por el servicio) · 947
tests en la suite ampliada.

feat(documento-cambio): el PDF generado reproduce el impreso real píxel
a píxel — antes el PDF dibujaba su propio layout con CSS (aproximado,
no coincidía con el impreso real del hospital). Ahora `pdf.html` pone
el escaneo del impreso (`app/static/img/hoja-cambio-fondo.png`, copia
de `hojacambios.png`) como fondo de página completa (`@page
{ background-image: ... }` de xhtml2pdf) y superpone cada dato dinámico
en un `@frame` propio, con las coordenadas y dimensiones exactas del
hueco que ocupa ese campo en el escaneo (medidas a mano sobre la imagen
con una rejilla de referencia, convertidas de píxeles a mm porque el
escaneo, 905×1280px, tiene la misma proporción que A4). Como el fondo
ya trae impresos el título, las etiquetas, las rejillas L-M-X-J-V-S-D y
el bloque de la supervisora, la plantilla quedó mucho más corta: ya no
dibuja nada de eso, solo el texto que varía por documento.

Detalle no obvio importante para no repetir el error: si la altura de
un `@frame` es insuficiente para el contenido (aunque sea de una sola
línea), xhtml2pdf/reportlab descartan ese contenido **en silencio, sin
ningún error** — no lo recortan, directamente no aparece. Costó una
ronda de tanteo con renders de prueba dar con una altura mínima segura
(~6mm a 9.5pt; se dejó 8mm de margen). Motivo por el que se añadió
`test_generar_pdf_documento_no_pierde_campos_con_nombres_largos`: extrae
el texto del PDF con `pypdf` y comprueba que un nombre de hospital/unidad
realista (basado en datos reales de staging) sigue apareciendo, como
red flag si se vuelve a estrechar algún frame por debajo del mínimo.

2 tests nuevos/ampliados en `test_servicio_documento_cambio.py`
(contenido esperado extraído del PDF con `pypdf`; nombres largos no
desaparecen). Verificado además visualmente, renderizando el PDF a PNG
con `pdftoppm` y comparándolo a ojo contra `hojacambios.png`.

## Paso anterior
fix(documento-cambio): las notas para ilog (`generar_notas_ilog`) solo
se calculan y se muestran en `ver.html` si `current_user.es_supervisora`
— antes cualquier participante del documento completo las veía también,
pero son un texto de uso interno para la ayudante de la supervisora, no
para los trabajadores. `Usuario.unidad_id` ya es una FK obligatoria de
uno solo (no hace falta cambio de modelo): cada cuenta de supervisora
ya estaba, y sigue estando, asignada a una única unidad. 2 tests
actualizados/nuevos en `test_rutas_documento_cambio.py` (el participante
ya no ve "Notas para ilog" tras la 2ª firma; la supervisora sí las ve).

## Paso anterior
feat(documento-cambio): el email de hoja de cambio completa es opcional
por usuario — nuevo campo `Usuario.notif_email_documento_cambio`
(Boolean, `server_default='true'`, migración `a18f63631b51`, seguro en
un solo paso al llevar `server_default`). `firmar_documento` solo llama
a `_enviar_email_completo` para los participantes que lo tengan
activado. Nuevo toggle independiente en `/notificaciones` (fuera del
bloque `{% if current_user.push_activo %}`, porque no depende del push:
un usuario puede tener el push desactivado y aun así querer el email, o
viceversa), con su propia ruta `POST /notificaciones/guardar-email` en
vez de mezclarlo con el formulario de push. 4 tests nuevos (servicio:
no se envía si está desactivado; rutas: activar/desactivar/no toca
push) · 78 tests en la suite ampliada · catálogo i18n actualizado.

## Paso anterior
feat(documento-cambio): motivo obligatorio al denegar — nuevo campo
`DocumentoCambio.motivo_denegacion` (Text, nullable, migración
`1181ee9b2dd8`), pedido explícito del usuario: los participantes deben
poder ver por qué se denegó, no solo que se denegó. La ruta `denegar`
exige un campo `motivo` no vacío en el formulario (si falta, redirige
con un aviso y el documento se queda en `pendiente`, no se deniega a
medias). El motivo se incluye en el texto de la notificación
(push+campana) y se muestra en `ver.html` a cualquiera de los dos
implicados, en un aviso destacado. 4 tests nuevos (motivo guardado,
notificación lo incluye, denegar sin motivo no deniega nada, el
participante lo ve en su página) · 71 tests en la suite ampliada ·
catálogo i18n actualizado.

## Paso anterior
feat(documento-cambio): botón autorizar/denegar en la cuenta de
supervisora — nuevos campos `DocumentoCambio.decision_supervisora`
(pendiente/autorizado/denegado, `server_default='pendiente'` por la
misma razón que `factibilidad_estado`), `supervisora_id` y
`fecha_decision_supervisora` (migración `8719b0fd144e`, deliberadamente
separados del campo `estado` existente para no mezclar el progreso de
firmas con la decisión de la supervisora — son dos máquinas de estados
independientes).

Nuevo `volcar_documento_a_planillas(documento)`: reutiliza
`añadir_turno`/`eliminar_turno` de `app/services/planilla.py` (mismos
helpers que ya usa `volcar_matches_a_planilla` para los matches del
motor de matching) y `_añadir_linea_nota` de `volcar_cambios.py` para
anotar el día — reaprovechando el propio `generar_notas_ilog` como
fuente del texto de la nota, en vez de redactarlo dos veces. Solo se
llama al **autorizar**, nunca al denegar.

`autorizar_documento`/`denegar_documento`: cambian
`decision_supervisora`, registran quién y cuándo, notifican (push +
campana) a ambos participantes con dos tipos de notificación nuevos
(`documento_cambio_autorizado`/`_denegado`, wiring mínimo en avisos()/
badge/avisos.html, mismo patrón que los tipos anteriores).

Rutas `POST /documentos-cambio/<id>/autorizar` y `/denegar`: 403 si
quien lo pide no es supervisora (o de otro grupo), 409 si el documento
no está `completo` o si ya se había decidido antes (evita autorizar dos
veces y volcar el cambio dos veces a la planilla). Botones visibles en
`ver.html` solo para la supervisora mientras esté pendiente; badge de
la decisión visible para todos una vez tomada, también añadido al
listado de supervisión.

7 tests nuevos (2 de servicio, 4 de rutas, incluida la doble
autorización) · 92 tests en la suite ampliada · catálogo i18n
actualizado.

## Paso anterior
feat(documento-cambio): cuenta de supervisora — nuevo campo
`Usuario.es_supervisora` (booleano, mismo patrón que `es_admin`,
migración `928e2599c80a`, `server_default='false'` seguro en un solo
paso). Se concede desde el panel de administración (formulario de
usuario, checkbox nuevo junto al de "Administrador" — no hay alta
autoservicio, igual que `es_admin`). Nueva ruta
`GET /documentos-cambio/supervisora`: 403 si `current_user.es_supervisora`
es falso; si no, lista TODAS las hojas de cambio de su grupo de
intercambio (join a través de `ParticipanteDocumentoCambio` → `Usuario`
→ `Unidad.grupo_intercambio_id`, no solo las suyas propias), mostrando
ambos participantes de cada una (a diferencia del listado personal, que
da por hecho que uno de los dos eres tú). `_get_documento_validado`
ampliado para que una supervisora también pueda abrir `ver`/`pdf` de
cualquier documento de su grupo, no solo los suyos. Enlace "Supervisión
de cambios" en el menú, solo visible si `es_supervisora`. 2 tests
nuevos (una supervisora ve cambios ajenos de su grupo; un usuario
normal recibe 403 al intentarlo) · 59 tests en la suite ampliada ·
catálogo i18n actualizado.

## Paso anterior
feat(documento-cambio): envío por email al completarse — reutiliza
`app/services/email.py` (Resend HTTPS API, ya usado para recuperar
contraseña) en vez de montar nada nuevo. Al firmar la última parte, se
envía un email a cada participante con un enlace a "Ver la hoja de
cambio" (mismo patrón que el email de recuperación de contraseña:
enlace + botón, no adjunto — el PDF se descarga desde la página, que ya
queda accesible permanentemente gracias al listado del paso anterior).
Nueva plantilla `email/documento_cambio_completo.html`. No se envía
nada al crear el documento ni con una sola firma, solo al completarse
del todo. 1 test nuevo (con `monkeypatch` sobre `enviar_email` para no
depender de la API real de Resend, comprueba que se envía a los dos
destinatarios y en el momento correcto) · 60 tests en la suite de
`documento_cambio`+`notificaciones` · catálogo i18n actualizado.

Nota: el intento de push anterior falló porque el hook de pre-push
corrió sobre el árbol de trabajo mientras este paso todavía estaba a
medias (test ya escrito, implementación aún no) — no era un bug real,
solo una carrera entre el push en segundo plano y la edición en curso.
El commit anterior (listado "mis hojas de cambio") sí llegó bien a
`staging` en ese mismo intento.

## Paso anterior
feat(documento-cambio): listado "mis hojas de cambio" — nueva ruta
`GET /documentos-cambio/` (`documento_cambio.lista`), muestra los
documentos donde el usuario logueado es alguno de los dos participantes
(join con `ParticipanteDocumentoCambio`), más recientes primero. Cada
fila: número, fecha, nombre del compañero, badge de estado
(completo/pendiente) y de factibilidad, enlace a "Ver" y, si está
completo, enlace directo al PDF. Nuevo `lista.html`, botón "Nueva hoja
de cambio" arriba. El enlace "Hoja de cambio" del menú ahora apunta
aquí en vez de directo a "Nueva" (antes no había ninguna forma de
volver a encontrar un documento salvo por el enlace de la notificación
o adivinando la URL). 1 test nuevo (comprueba que cada usuario solo ve
sus propios documentos) · 13 tests en rutas · catálogo i18n
actualizado.

## Paso anterior
fix(documento-cambio): mejoras de fidelidad del PDF — "Favorable"/
"Desfavorable" del bloque de la supervisora pasan a líneas separadas
(en el impreso real están apiladas, no en la misma línea, como tenía
antes). Se intentó también reproducir el patrón `_`/`N` de la rejilla
"CORRESPONDE A:" (boilerplate fijo del impreso, legado de juntes de
noches) añadiendo una segunda fila de datos con ese contenido, pero
`xhtml2pdf`/reportlab no calcula bien el ancho de columnas en cuanto
hay contenido real en varias filas de una tabla con una columna de
etiqueta ancha (el label se queda comprimido en una columna diminuta,
probado con `rowspan` y con anchos explícitos `width=` por columna, sin
éxito en ninguno de los dos intentos) — revertido a una sola fila en
blanco por rejilla, que sí renderiza bien, en vez de seguir invirtiendo
tiempo en un problema de una librería de terceros para un elemento que
además es boilerplate de una función (juntes de noches) todavía fuera
de alcance. Verificado visualmente con `pdftoppm` en cada iteración,
1 página confirmada con `pypdf`. Sin tests nuevos (cambio de
maquetación, no de comportamiento) · 23 tests existentes en verde.

## Paso anterior
feat(documento-cambio): número de cambio junto a la fecha — pedido
explícito del usuario para que la ayudante pueda ordenar los cambios
por orden cronológico exacto de creación, no solo por el día del cambio
(varios documentos del mismo día quedan así desambiguados). No hizo
falta ninguna columna nueva: `documento.id` (PK autoincremental de
Postgres) ya crece en el mismo orden que `fecha_creacion`, así que solo
se expone en la UI (`ver.html`, junto al título) y en el PDF (línea de
fecha, "Nº X — Madrid, ...", tal y como pidió: junto a la fecha). 1 test
nuevo · verificado visualmente con `pdftoppm`.

Nota de depuración (no es un bug real, para no repetir la confusión):
al probar `generar_pdf_documento` con un script suelto fuera de un
request real, `gettext` lanzó `RuntimeError: Working outside of request
context` porque `_get_locale` lee `request.accept_languages`. En
producción esto nunca pasa: el servicio solo se llama desde las rutas
de `documento_cambio.py`, siempre dentro de una request real. Para
probar manualmente con un script hay que usar
`app.test_request_context()`, no solo `app.app_context()`.

## Paso anterior
feat(documento-cambio): firma cruzada entre cuentas reales — cada
participante firma su propia parte desde su propia cuenta, ya no hace
falta pasar el móvil ni que el compañero tenga sesión iniciada en el
mismo dispositivo. `_get_documento_validado` ahora permite ver el
documento a cualquiera de sus participantes (antes solo al creador —
como el creador siempre es también un participante, no hizo falta
lógica aparte). La ruta `firmar` ahora exige
`participante.usuario_id == current_user.id` (403 si intentas firmar la
fila de otro) en vez de "solo el creador firma por cualquiera". `ver.html`
sustituye el antiguo "siguiente_participante" (pensado para mono-cuenta)
por `mi_participante`/`puedo_firmar`: el canvas de firma solo aparece si
el usuario logueado es quien todavía tiene que firmar su propia fila; si
ya firmó pero el documento no está completo, ve un mensaje de "esperando
a la otra parte".

Notificaciones: nueva columna `Notificacion.documento_cambio_id`
(nullable, migración `c2938aae9b98`) y dos tipos nuevos
(`documento_cambio_pendiente_firma`, `documento_cambio_completo`). Al
crear el documento se notifica al compañero (push + aviso en la
campana); al firmar, si falta alguien se le notifica que ya solo depende
de él/ella, y al completarse se notifica a ambos. Reutiliza
`enviar_push` (no `enviar_push_condicional`, que exige wiring profundo
por tipo en `push/sender.py` — más apropiado para tipos con lógica de
límite diario, que este no necesita) y respeta `usuario.push_activo`.
Wiring mínimo en la página de avisos existente (`avisos()`, contador de
la campana en `app/__init__.py`, nueva rama en `avisos.html`) en vez de
levantar un sistema de notificaciones aparte.

Textos de notificación con `gettext` (`_()`), seguiendo el precedente de
`admin.py` (mensaje de "contraseña restablecida"), no el de
`push/sender.py::_TEXTOS` (que están sin traducir pese a que `CLAUDE.md`
lo exige — deuda técnica preexistente, no arreglada aquí por no ser parte
de este paso).

e2e/test_documento_cambio.py actualizado para reflejar el flujo real:
Ana firma, cierra sesión, Pedro entra con su propia cuenta y firma la
suya — verificado con Playwright, firma real dibujada en ambos canvas,
sin errores de consola.

12 tests nuevos/actualizados en rutas y servicio · 57 tests en la suite
de `documento_cambio`+`notificaciones` · catálogo i18n actualizado.

## Paso anterior
feat(documento-cambio): recomprueba la factibilidad al completarse la
segunda firma, no solo al crear el documento — puede haber pasado
tiempo desde la creación y alguien haber publicado/cambiado su planilla
mientras tanto, dejando desactualizado el resultado guardado justo
cuando más importa (el momento de cerrar el documento). 1 test nuevo.

## Paso anterior
docs(especificacion): documenta la hoja de cambio digital en
`ESPECIFICACION.md` — nuevas entidades `DocumentoCambio`/
`ParticipanteDocumentoCambio`/`FirmaDocumentoCambio` en la sección 2,
reglas de negocio 11-14 (flujo aparte del matching automático,
mono-cuenta, factibilidad no bloqueante, fidelidad al impreso) en la
sección 3, CU10 en la sección 4, decisión técnica de `xhtml2pdf` (con
el porqué del incidente de WeasyPrint) en la sección 5, y 6 UAT nuevos
(UAT-8.1 a UAT-8.6) en la sección 6. También corregidas las dos
afirmaciones de la sección 1 ("no requiere aprobación de RRHH", "no
deja constancia oficial") que ya no eran exactas con esta
funcionalidad — matizadas para dejar claro que aplican al motor de
matching automático, con la hoja de cambio digital como excepción
explícita. Añadida nota en "Fuera de alcance del MVP" con los
pendientes de esta feature (firma cruzada real, cadenas 3/4, juntes de
noches, recomprobación en la segunda firma, enganche con matching).

## Paso anterior
feat(documento-cambio): comprobación de factibilidad contra planillas —
nuevo servicio puro `app/services/factibilidad_documento_cambio.py`
(`comprobar_factibilidad(documento)`), reutiliza las mismas reglas que
`compatibilidad_planilla.py` (`turnos_solapan`, `EstadoDiaPlanilla`,
`tiene_mes_publicado`) en vez de reinventarlas: para cada participante,
comprueba que trabaja de verdad el turno que dice ceder y que está
libre para el que dice recibir. Devuelve `'no_verificado'` si falta la
planilla publicada de alguien para alguno de los meses implicados (no
se puede comprobar), `'no_factible'` si hay planilla de ambos pero algo
no cuadra, `'factible'` si todo encaja.

Columna `DocumentoCambio.factibilidad_estado` (String, reemplaza al
booleano `factibilidad_verificada` que quedó del paso 1 sin usar nunca)
con `server_default='no_verificado'` — necesario en un solo paso porque
`documento_cambio` ya tenía filas reales en staging (probadas a mano
por el usuario), ver regla de migraciones NOT NULL de `CLAUDE.md`.
Migración `3a9f874609fe` generada con `flask db migrate`, un solo head.
`crear_documento_cambio` calcula y guarda el resultado al crear el
documento (no se recalcula más tarde, ver nota pendiente abajo).

`ver.html` muestra el resultado con tres estados visuales: verificado
(verde), no factible (aviso rojo destacado — "revisa los datos antes de
firmar"), no verificado (aviso neutro — "comprueba manualmente"). 6
tests nuevos (5 del servicio + 1 de integración en
`crear_documento_cambio`) · 28 tests en la suite de `documento_cambio` ·
catálogo i18n actualizado.

Pendiente (anotado para no perderlo, fuera de alcance de este paso): la
factibilidad solo se calcula una vez, al crear el documento — si la
planilla de alguien cambia mientras el documento sigue sin firmar, no
se recalcula. El plan original (ver conversación de diseño) contemplaba
recomprobar también al completar la segunda firma; no implementado
todavía por mantener el paso acotado.

## Paso anterior
fix(documento-cambio): el PDF desbordaba a una segunda página en
Railway — "LA SUPERVISORA DE LA UNIDAD," terminaba en la página 2,
reportado por el usuario tras el deploy. La maquetación se había
ajustado a ojo comparando capturas locales y, sin darme cuenta, ya
ocupaba ~96% de la altura útil de una A4 (medido a posteriori contando
píxeles en la captura del paso anterior) — sin margen para que una
diferencia mínima de métricas de fuente en otro entorno la hiciera
desbordar. Reducidos márgenes/paddings/tamaños de fuente en
`pdf.html` (`@page` de 2cm a 1.5cm, cuerpo de 11pt a 10pt, márgenes de
`.campo`/rejillas/firmas/supervisora recortados proporcionalmente) sin
cambiar el contenido ni la estructura. Verificado contando páginas del
PDF generado con `pypdf` (1 página, antes también daba 1 en local pero
sin margen) y visualmente con `pdftoppm` — ahora queda con ~30% de
espacio en blanco al final, margen real para absorber diferencias de
entorno. Sin tests nuevos (cambio puramente de maquetación, no de
comportamiento) · 14 tests existentes siguen en verde · push directo a
staging a petición del usuario.

## Paso anterior
fix(documento-cambio): sustituido WeasyPrint por xhtml2pdf — dos
intentos seguidos de arreglar las dependencias nativas de WeasyPrint en
Railway (`nixPkgs` y luego `aptPkgs` en `nixpacks.toml`) dieron el
mismo error exacto (`OSError: cannot load library 'libgobject-2.0-0'`),
lo que apunta a que `nixpacks.toml` ni siquiera se estaba aplicando en
el build de este proyecto (o el builder real no es Nixpacks) — sin
acceso al panel de Railway no hay forma de confirmarlo, y no tenía
sentido seguir adivinando configuración de build a ciegas gastando
ciclos de deploy del usuario. Cambio de estrategia: `xhtml2pdf` (usa
`reportlab` por debajo) es Python puro, sin ningún binding nativo/cffi,
así que esta categoría entera de fallo deja de ser posible
independientemente de qué builder use Railway. `nixpacks.toml` eliminado
(ya no hace falta). Plantilla `pdf.html` adaptada al subset de CSS de
xhtml2pdf: la maquetación de las firmas pasa de `display:flex` (no
soportado) a una tabla; los `border-bottom` en `<span>`/`<div>` vacíos
no se renderizaban (regresión visual detectada comparando capturas antes
de dar el paso por bueno) — sustituidos por `<u>` para los valores de
campo y `<hr>` para las líneas en blanco del bloque de la supervisora,
verificado que ambos si funcionan en xhtml2pdf con un PDF de prueba
aislado antes de tocar la plantilla real. Import de `xhtml2pdf` sigue
siendo perezoso (dentro de la función, no a nivel de módulo) como buena
práctica, aunque el riesgo concreto que lo motivó (crash de arranque por
dependencia nativa) ya no aplica con una librería pura Python.
Reverificado generando un PDF real con firma dibujada y convirtiéndolo a
imagen con `pdftoppm` — visualmente equivalente a la versión con
WeasyPrint, incluidos las firmas y las rejillas. 22 tests siguen en
verde sin cambios (el contrato de `generar_pdf_documento` no cambió,
solo la implementación interna).

## Paso anterior
fix(documento-cambio): `nixpacks.toml` con `nixPkgs` no arregló el 500
de "Generar PDF" — mismo `OSError: cannot load library
'libgobject-2.0-0'` que antes de añadirlo (confirmado en los logs de
Railway que pegó el usuario), pero esta vez el import perezoso funcionó
tal y como se diseñó: la app arrancó bien (gunicorn con sus 3 workers
arriba, sin crash-loop) y solo falló la petición a `/documentos-cambio/
<id>/pdf` con un 500 — justo el comportamiento buscado. Causa probable
de que `nixPkgs` no bastara: los paquetes Nix no quedan en el path que
usa el linker dinámico (`dlopen`/cffi) del runtime de Railway, solo en
el `PATH` de binarios. Cambiado `nixpacks.toml` a `aptPkgs` (instala en
rutas de sistema estándar `/usr/lib/...`, que es donde `dlopen` ya busca
sin configuración extra) con los mismos paquetes que recomienda la
documentación oficial de WeasyPrint para Debian/Ubuntu
(`libpango-1.0-0`, `libpangoft2-1.0-0`, `libpangocairo-1.0-0`,
`libcairo2`, `libgdk-pixbuf2.0-0`, `libglib2.0-0`, `shared-mime-info`,
`fonts-dejavu-core`). Pendiente confirmar en el próximo deploy si esto
sí resuelve el problema.

## Paso anterior
fix(documento-cambio): reintroducido el PDF (revertido el revert) con
dos cambios para que no vuelva a pasar lo de antes: (1) `from weasyprint
import HTML` movido de nivel de módulo a dentro de
`generar_pdf_documento()` — importar weasyprint ya no puede tirar abajo
el arranque completo de la app si algo de sus dependencias nativas falla
en el contenedor de destino, como mucho falla esa única ruta; (2) nuevo
`nixpacks.toml` que declara los paquetes de sistema Nix que WeasyPrint
necesita en tiempo de ejecución (`pango`, `cairo`, `gdk-pixbuf`, `glib`,
`harfbuzz`, `fontconfig`, `shared-mime-info`) para que Railway los
instale en el build. No
hay forma de probar un build de Nixpacks real desde este entorno de
desarrollo, así que el import perezoso es la red de seguridad real: si
`nixpacks.toml` no basta o le faltase algún paquete, el resto de la app
sigue funcionando y solo falla "Generar PDF" con un 500, en vez de
crashear todo el arranque otra vez.

## Paso anterior
revert(documento-cambio): deshecho el commit que generaba el PDF con
WeasyPrint — crasheaba el arranque completo de la app en Railway
(`staging`), no solo la ruta del PDF. `weasyprint` importa Pango/cairo/
gdk-pixbuf vía cffi con `dlopen` en tiempo de import (`from weasyprint
import HTML` en `app/services/documento_cambio.py`, importado a su vez
por el blueprint `documento_cambio` al arrancar `create_app`), y el
contenedor de Railway no tiene esas librerías de sistema instaladas
(`OSError: cannot load library 'libgobject-2.0-0'`), así que
`flask db upgrade` (primer paso del `Procfile`) fallaba antes de que la
app llegara a arrancar — bucle de crash total, confirmado con los logs
de Railway que pegó el usuario. Localmente SÍ funcionaba sin problemas
(este entorno de desarrollo ya tenía esas librerías preinstaladas), lo
que ocultó el problema hasta el deploy real — lección para la próxima
vez: cualquier dependencia con bindings nativos (cffi/ctypes) hay que
asumir que puede faltar en el entorno de producción aunque funcione en
local, y comprobarlo explícitamente (o probarlo primero en un entorno
lo más parecido posible a Railway) antes de dar por bueno un paso que
toque el arranque de la app.

Revert limpio con `git revert` (no se tocó nada a mano): quita
`weasyprint==69.0` de `requirements.txt`, la plantilla `pdf.html`, la
ruta `GET /documentos-cambio/<id>/pdf`, el botón "Generar PDF", el logo
recortado y los 3 tests del PDF. Deja el estado exactamente como al
final del paso 2b (rutas + firma con canvas, sin PDF), que es lo último
que el usuario había comprobado manualmente que funcionaba. 19 tests
passing (servicio + rutas + modelos de `documento_cambio`) · push directo
a `staging` para restaurar el servicio cuanto antes.

## Paso anterior
revert(documento-cambio): deshecho el commit que generaba el PDF con
WeasyPrint — crasheaba el arranque completo de la app en Railway
(`staging`), no solo la ruta del PDF. `weasyprint` importa Pango/cairo/
gdk-pixbuf vía cffi con `dlopen` en tiempo de import (`from weasyprint
import HTML` en `app/services/documento_cambio.py`, importado a su vez
por el blueprint `documento_cambio` al arrancar `create_app`), y el
contenedor de Railway no tiene esas librerías de sistema instaladas
(`OSError: cannot load library 'libgobject-2.0-0'`), así que
`flask db upgrade` (primer paso del `Procfile`) fallaba antes de que la
app llegara a arrancar — bucle de crash total, confirmado con los logs
de Railway que pegó el usuario. Localmente SÍ funcionaba sin problemas
(este entorno de desarrollo ya tenía esas librerías preinstaladas), lo
que ocultó el problema hasta el deploy real — lección para la próxima
vez: cualquier dependencia con bindings nativos (cffi/ctypes) hay que
asumir que puede faltar en el entorno de producción aunque funcione en
local, y comprobarlo explícitamente (o probarlo primero en un entorno
lo más parecido posible a Railway) antes de dar por bueno un paso que
toque el arranque de la app.

Revert limpio con `git revert` (no se tocó nada a mano): quita
`weasyprint==69.0` de `requirements.txt`, la plantilla `pdf.html`, la
ruta `GET /documentos-cambio/<id>/pdf`, el botón "Generar PDF", el logo
recortado y los 3 tests del PDF. Deja el estado exactamente como al
final del paso 2b (rutas + firma con canvas, sin PDF), que es lo último
que el usuario había comprobado manualmente que funcionaba. 19 tests
passing (servicio + rutas + modelos de `documento_cambio`) · push directo
a `staging` para restaurar el servicio cuanto antes.

Antes de reintentar el PDF: investigar si Railway usa Nixpacks (sin
`nixpacks.toml`/`Dockerfile` en el repo ahora mismo, así que autodetección
por defecto) y qué paquetes Nix equivalentes hacen falta (`pango`,
`cairo`, `gdk-pixbuf`, `glib`/`gobject`, `harfbuzz`, `fontconfig` como
mínimo) declarándolos en un `nixpacks.toml` nuevo — y/o hacer el `import
weasyprint` perezoso (dentro de la función, no a nivel de módulo) como
red de seguridad para que un fallo de esa dependencia no vuelva a tirar
abajo el arranque completo de la app, solo la ruta del PDF.

## Paso anterior
feat(documento-cambio): plantilla PDF fiel al impreso real + botón
"Generar PDF" — pedido explícito del usuario tras probar manualmente el
flujo de firma: quiere enseñar el PDF generado a sus jefes. Nueva
plantilla standalone `documento_cambio/pdf.html` (no extiende `base.html`,
es un documento HTML propio pensado para WeasyPrint, con CSS `@page`) que
reproduce el impreso `hojacambios.png` del Hospital La Paz: logo (recortado
de la cabecera del propio PNG con Pillow, guardado en
`app/static/img/logo-hospital-la-paz.png`), título, campos de
hospital/unidad/categoría/solicitante derivados del `Usuario` (no
duplicados en el modelo), datos del cambio, las dos rejillas L-M-X-J-V-S-D
en blanco (juntes de noches, fuera de alcance), fecha, las dos firmas
(las imágenes `data:image/png;base64,...` ya guardadas se embeben
directamente — WeasyPrint las soporta nativas) y el bloque de la
supervisora en blanco/estático, tal y como se decidió en el diseño de la
plantilla.

`generar_pdf_documento(documento)` en el servicio: usa
`documento.creado_por` como "LA INTERESADA" (quien solicita) y el otro
participante como "ACEPTA EL CAMBIO", busca sus firmas por `usuario_id`,
renderiza la plantilla con `render_template` y la convierte con
`WeasyPrint.HTML(string=html).write_pdf()` — se genera bajo demanda en
cada petición, no se persiste el binario en ningún sitio (evita el
problema de disco efímero en Railway que ya habíamos identificado).
Nueva ruta `GET /documentos-cambio/<id>/pdf` (403 si no eres el creador,
409 si el documento no está `completo` — decisión explícita del usuario:
el botón solo aparece cuando las dos firmas ya están recogidas, no como
borrador), devuelve el PDF con `Content-Disposition: attachment`.

Añadida dependencia `weasyprint==69.0` a `requirements.txt` — probada en
este entorno (renderiza sin problemas, no ha hecho falta instalar
paquetes de sistema aparte de los que ya trae la imagen). Verificado
generando un PDF real end-to-end (con firma dibujada de verdad, no un
placeholder) y convirtiéndolo a imagen con `pdftoppm` para inspección
visual — el resultado es fiel al impreso original, incluidas las firmas
renderizando correctamente en su sitio.

A petición del usuario, tests mínimos en vez de la suite completa en este
paso (3 tests nuevos: PDF válido con 2 firmas a nivel de servicio, 409 sin
completar, 200+descarga al completar) y push directo a `staging` sin pasar
por PR.

## Paso anterior
feat(documento-cambio): rutas, formulario y firma con canvas — nuevo
blueprint `documento_cambio` (`/documentos-cambio`): `GET/POST /nuevo`
(elige compañero de la misma categoría+grupo y los datos del turno;
reutiliza `crear_franjas_default` como ya hace `/publicar` para que el
selector de turnos no salga vacío en un grupo nuevo), `GET /<id>` (ver
datos + firmar + notas ilog cuando esté completo) y
`POST /<id>/firmar/<participante_id>` (403 si no es el creador —
fase mono-cuenta: solo quien creó el documento firma por las dos partes
desde su propio dispositivo — 409 si ese participante ya había firmado).
`app/static/js/firma-canvas.js`: canvas con eventos `pointerdown/move/up`
(cubre dedo/ratón/lápiz uniformemente), botón «Borrar», y en el submit
del formulario vuelca el trazo a `imagen_firma` como PNG en base64;
mismo fichero incluye `copiarAlPortapapeles` para los botones «Copiar»
de las notas ilog. Enlace «Hoja de cambio» añadido al nav. Catálogo i18n
actualizado (`pybabel extract/update/compile`, 26 entradas nuevas
corregidas a mano: `pybabel update` empareja mal los `msgid` nuevos con
similares existentes — mismo problema ya documentado en pasos previos de
esta fase de tipo "Fase 9").

Verificado en navegador real con Playwright (`e2e/test_documento_cambio.py`,
`--headed` opcional): flujo completo con dos usuarios (Ana/Pedro),
firma dibujada con `page.mouse` en el canvas (con `scroll_into_view_if_needed`
— si el canvas queda fuera del viewport, `page.mouse` no impacta el
elemento y la firma queda vacía, dando un `alert()` bloqueante sin que se
note por qué), sin errores de consola ni alertas inesperadas, y contenido
exacto de las 4 notas ilog comprobado. De paso se encontró y arregló un
bug ya existente (no introducido por este cambio, pero copiado sin querer
al escribir las plantillas nuevas a partir de `publicar.html`): las
plantillas usaban clases `alert`/`alert--*` que no existen en
`main.css` (solo `flash`/`flash--*` están definidas), y además
duplicaban el bloque de flash messages que `base.html` ya renderiza
globalmente — el mensaje aparecía dos veces, una con estilo (el de
`base.html`) y otra en texto plano sin caja. Corregido solo en las
plantillas nuevas de esta feature; `publicaciones/publicar.html` sigue
teniendo el mismo bug latente, no tocado por no ser parte de este paso
(anotado abajo para no perderlo).

9 tests nuevos de rutas (`test_rutas_documento_cambio.py`) + 1 e2e nuevo.
Contención puntual de BD compartida (`turnero_test`) con otro job en
paralelo durante la verificación — confirmado con BD privada temporal,
sin relación con el código; también se limpió un proceso `pytest`
huérfano propio, sobrante de dos intentos de `git push` cortados por
timeout antes de descubrir que el hook de pre-push solo tardaba ~1min
(testmon acota bien, no hace falta el baseline completo salvo la
primerísima vez).

## Paso anterior
feat(documento-cambio): servicio `crear_documento_cambio` (genera los dos
`ParticipanteDocumentoCambio` espejo), `firmar_documento` (registra la
firma, calcula `hash_documento` con sha256 sobre el contenido firmable, y
mueve el estado borrador→pendiente_firmas→completo según falten firmas) y
`generar_notas_ilog` (4 notas en lenguaje natural — una por trabajador y
día afectado — para que la ayudante las copie a la nota del día en ilog;
formato de fecha "D de mes" con lista de meses en español, mismo patrón ya
usado en `busquedas_guardadas.py`). 5 tests nuevos, todos en verde a la
primera · 901 tests passing (896 + 5 nuevos, no se ha vuelto a correr la
suite completa, solo el fichero nuevo — el resto de la suite no se ha
tocado desde el último run completo).

## Paso anterior
feat(documento-cambio): modelo de datos para la hoja de cambio digital —
`DocumentoCambio` (estado borrador/pendiente_firmas/completo/caducado,
`match_id` nullable para enlazar más adelante con `MatchCambio` cuando el
documento se genere desde el motor de matching), `ParticipanteDocumentoCambio`
(una fila por trabajador implicado, con el turno que cede y el que recibe;
no depende de `PublicacionCambio`/`TurnoCedido` porque en esta fase manual
no hay ninguna publicación de por medio) y `FirmaDocumentoCambio` (una fila
por firma, con `imagen_firma` para el trazo dibujado y `hash_documento`
como huella del contenido exacto firmado, para poder demostrar qué se
firmó aunque la plantilla cambie después). `UniqueConstraint` en
participante y firma (un usuario no puede aparecer dos veces en el mismo
documento ni firmar dos veces). Método `todos_han_firmado()` compara el
conjunto de usuarios participantes contra el conjunto de firmantes.
Migración `3f8d2428aa64` (3 tablas nuevas, todas las columnas `NOT NULL`
son seguras en un solo paso porque las tablas nacen vacías — no aplica el
patrón de 3 pasos). 9 tests nuevos en `test_models_documento_cambio.py` ·
896 tests passing (suite completa).

Pendiente (fuera del alcance de este paso, anotado para no perderlo):
`ESPECIFICACION.md` todavía dice "no deja constancia oficial del cambio
para terceros (no es un documento de RRHH)" — ese principio ya no es
exacto una vez que este documento exista, hay que actualizarlo cuando se
cierre el diseño completo de esta fase.

## Paso anterior
perf(db): `publicacion_cambio`, `usuario` y `unidad` no tenían más índice
que la PK (`\d publicacion_cambio` en producción lo confirmó), pese a que
`usuario_id`, `estado`, `es_sintetica` y `tipo` de `publicacion_cambio`,
`categoria_id` de `usuario` y `grupo_intercambio_id` de `unidad` son
justo las columnas que filtran todas las búsquedas del motor de matching
y el dashboard. Cuarto y último paso del plan de 4 para resolver los
cuelgues de producción (ver pasos anteriores). Fix: `index=True` en esas
6 columnas (`app/models/publicacion.py`, `app/models/usuario.py`,
`app/models/unidad.py`) y migración generada con `flask db migrate`
(nunca a mano) — `285a7610df2f_añade_índices_para_filtros_de_matching.py`,
`flask db heads` da un único head. Solo crea índices (`create_index`),
no toca datos ni columnas existentes, así que no aplica el patrón de 3
pasos de `NOT NULL`. Aplicada y verificada en local (`flask db upgrade`)
· 890 tests passing.

Con esto quedan completados los 4 pasos del plan. Pendiente de que el
usuario decida cuándo hacer push/deploy a producción (ninguno de los 4
commits se ha empujado todavía) y, tras el deploy, verificar en
`railway logs` que: (a) arrancan 3 workers de gunicorn, (b) `flask db
upgrade` aplica la migración de índices sin errores, y (c) no vuelven a
aparecer `WORKER TIMEOUT` en los días siguientes.

## Paso anterior
chore(deploy): `Procfile` pasa de `gunicorn run:app` (default: 1 worker
síncrono, sin `-w`) a `gunicorn --workers 3 --timeout 60 run:app`. Tercer
paso del plan de 4 para resolver los cuelgues de producción (ver pasos
anteriores): con 1 solo worker, cualquier request lento (el motor de
matching en el grupo de intercambio más activo, u otra cosa en el
futuro) congelaba la app entera para todos los usuarios, no solo para
quien la disparó — es la causa de que los 3 `WORKER TIMEOUT` de gunicorn
vistos en producción (2026-07-14/15) se sintieran como "toda la app va
lenta" en vez de "una acción en concreto tardó". Con 3 workers, ese mismo
request lento deja de bloquear al resto. 60s de timeout (antes 30s,
default de gunicorn) da margen mientras los pasos 1 y 2 ya aplicados
reducen el tiempo real. 3 workers es un valor conservador para el plan
de Railway actual; si tras el deploy aparece presión de memoria
(reinicios por OOM en los logs, no `WORKER TIMEOUT`), habría que subir de
plan antes de subir el nº de workers.

Pendiente: **no se ha desplegado ni empujado (push) todavía** — el commit
queda listo en local (rama `staging`) a la espera de que el usuario
confirme el push/deploy. La verificación de este paso (confirmar en
`railway logs` que arrancan 3 workers y que `/health` sigue respondiendo)
solo se puede hacer después de ese deploy.

## Paso anterior
perf(matching): las 5 búsquedas de matching que se lanzan en cada
publish/editar/contraoferta (`buscar_matches_para`, `buscar_cadenas_3_para`,
`buscar_cadenas_4_para`, `buscar_cadenas_parciales_4_para`,
`buscar_avisos_interes_para`, en `app/matching/service.py`) repetían cada
una su propia llamada a `_candidatas_base` (misma consulta + 2
`selectinload`) en vez de compartir un único cálculo — 5x consultas
redundantes por request. Segundo paso del plan de 4 para resolver los
cuelgues de producción (ver paso anterior). Fix: nueva función pública
`candidatas_activas_para(publicacion)` (antes lógica repetida al principio
de cada búsqueda) y parámetro opcional `candidatas=None` en las 5
funciones — si se pasa ya calculado se reutiliza, si no se calcula como
antes (así los tests unitarios existentes, que llaman con un solo
argumento, siguen funcionando sin cambios). Las 3 rutas que hacían este
patrón (`nueva`, `editar` y `contraoferta` en `app/routes/publicaciones.py`)
calculan ahora `candidatas` una vez y la pasan a las 5 búsquedas.
`buscar_sinteticas_que_coinciden_con` queda fuera: consulta sintéticas,
no candidatas normales. Nuevo test de regresión
(`test_publicar_calcula_candidatas_una_sola_vez` en
`test_integracion_matching.py`) que espía `_candidatas_base` con
`unittest.mock.patch.object(..., wraps=...)` y comprueba `call_count == 1`
tras un publish real vía el cliente HTTP — confirmado en rojo sin el fix
(5 llamadas) y en verde con el fix aplicado · 890 tests passing.

Quedan 2 pasos del plan: 3) gunicorn con varios workers en el `Procfile`
(red de seguridad de infraestructura: que un request lento no bloquee
toda la app, ya que solo hay 1 worker síncrono hoy) y 4) añadir los
índices que faltan en `publicacion_cambio`/`usuario`/`unidad` (hoy solo
tienen la PK).

## Paso anterior
perf(busquedas): corregido un N+1 en `notificar_busquedas_guardadas`
(`app/services/busquedas_guardadas.py`) — por cada `BusquedaGuardada`
candidata que coincidía con una publicación nueva, se hacía un
`db.session.get(Usuario, busqueda.usuario_id)` dentro del bucle, en vez
de reutilizar el `Usuario` que la propia consulta ya traía por el `join`.
Detectado investigando por qué la app en producción se ha vuelto notable
mente más lenta en los últimos días (a petición del usuario, sin ninguna
sospecha previa de dónde estaba el problema): los logs de Railway
mostraban 3 `WORKER TIMEOUT` de gunicorn en 48h (2026-07-14 12:23,
2026-07-15 00:29, 2026-07-15 14:16), y el stack trace del worker matado
apuntaba siempre a este mismo punto — `notificar_busquedas_guardadas`
llamada desde `crear_pub_sintetica`, que a su vez se llama hasta 13 veces
en un solo publish/editar en el grupo de intercambio más activo
(categoría 2 / grupo 5: 89 publicaciones "cambio" activas ahora mismo).
Como no hay más de 1 worker de gunicorn (`Procfile` sin `-w`), cada
timeout congelaba la app entera para todos los usuarios, no solo para
quien publicaba. Fix: `contains_eager(BusquedaGuardada.usuario)` en la
query de candidatas (ya hace `join` con `Usuario`) y uso directo de
`busqueda.usuario` en vez del `get()` redundante. Nuevo test
(`test_notificar_busquedas_guardadas_no_crece_con_n`) que cuenta
`SELECT`s ejecutados (nuevo fixture `query_counter` en `conftest.py`,
basado en el evento `after_cursor_execute` de SQLAlchemy) y comprueba que
no crecen con el número de búsquedas guardadas coincidentes — usando
usuarios *distintos* por búsqueda, ya que con el mismo usuario repetido
el identity map de SQLAlchemy habría ocultado el bug. Confirmado en rojo
sin el fix (12 selects con 5 búsquedas vs 8 con 1) y en verde con el fix
aplicado (igual en ambos casos) · 889 tests passing.

Este es el primer paso de un plan de 4 para resolver los cuelgues de
producción (ver `/home/portatil/.claude/plans/dreamy-noodling-glacier.md`
si sigue disponible, o pedir al usuario que lo recuerde): 2) reutilizar
`_candidatas_base` entre las 6 búsquedas de matching que se lanzan en
cada publish/editar (hoy se repite la misma consulta 6 veces), 3) gunicorn
con varios workers en el `Procfile` (red de seguridad de infraestructura:
que un request lento no bloquee toda la app), 4) añadir los índices que
faltan en `publicacion_cambio`/`usuario`/`unidad` (hoy solo tienen la PK).

## Paso anterior
fix(matching): las cadenas de 3 y 4 bandas (`crear_match_cadena_3`,
`crear_match_cadena_4` en `app/matching/service.py`) solo registraban en
`MatchParticipacion` el `turno_cedido_id` que cada banda cede a la
siguiente del ciclo, nunca el `turno_aceptado_id` que recibe de la
anterior — a diferencia de `crear_match_directo`, que ya resolvía ambos
lados con `_primer_aceptado_que_cubre`. Consecuencia: al confirmarse una
cadena, `confirmar_participacion` marcaba `resuelto` el turno cedido pero
nunca el aceptado, así que una publicación multi-turno que solo resolvía
parcialmente por una cadena volvía a estar activa (`parcialmente_resuelta`,
correcto) pero seguía mostrando como pendiente el día ya conseguido.
Reportado por el usuario en producción tras confirmar un cambio a 4 bandas
(publicación 818: recibió el 2026-08-07 de Blanca De la Calle vía el ciclo
Alejandro Vilches→Victoria Hernández-Mansilla→Blanca→Guillén→Alejandro;
`turno_aceptado` id 2104 seguía en `abierto` tras el cierre). Diagnosticado
leyendo en solo lectura la BD de producción (Railway) antes de tocar
código. Fix: ambas funciones calculan ahora también el `turno_aceptado`
que cada banda recibe (mismo helper `_primer_aceptado_que_cubre` que ya
usaba el match directo) y lo enlazan en la participación; no hace falta
tocar `confirmar_participacion`, que ya comprobaba
`turno_aceptado_id is not None`. 4 tests de regresión nuevos (2 por cadena:
cada participación tiene `turno_aceptado_id`, y caso de extremo a extremo
con publicación multi-turno que verifica que el turno conseguido queda
`resuelto` y el resto de turnos intacto) · 887 tests passing.

Pendiente: el `turno_aceptado` 2104 de la publicación 818 de producción
sigue con el dato viejo (`abierto`) porque el fix no es retroactivo — el
usuario no ha pedido corregirlo todavía, solo el fix de código. Si lo pide,
es un `UPDATE` de una fila puntual, no una migración de esquema.

## Paso anterior
fix(dashboard): investigado un reporte del usuario de que, en cadenas de
3/4 bandas, la tarjeta de "Pendientes" no reflejaba nuevas confirmaciones
de otros participantes al recargar. No se pudo reproducir ningún bug de
datos/plantilla: se comprobó con varios órdenes de confirmación (segundo
confirmador, el propio primer confirmador recargando tras la segunda
confirmación de otro) tanto con el cliente de test de Flask como contra
un servidor real (`flask run`) con sesiones HTTP independientes por
usuario (cookies separadas) — en todos los casos el HTML recargado ya
traía el ✓ correcto. Como la página del dashboard es dinámica y personal
(depende de qué haya confirmado cada participante) y no llevaba ninguna
cabecera anti-caché, se añade `Cache-Control: no-store` a la respuesta
de `main.index` como medida defensiva: si la causa real era caché del
navegador o de algún intermediario entre el usuario y Railway, queda
eliminada; si vuelve a reportarse, ya no puede deberse a eso. 4 tests
nuevos (2ª confirmación reflejada, primer confirmador ve la 2ª
confirmación de otro, cabecera no-store) · 884 tests passing.

feat(dashboard): en las tarjetas de match de cadenas de 3/4 bandas
(`cadena_3`/`cadena_4`), se añade una fila de "chips" que muestra a cada
participante con ✓ (confirmado, chip verde) u ○ (pendiente) — a petición
del usuario: cuando una parte confirma, las demás reciben aviso y el
cambio pasa a "Pendientes de confirmar", pero hasta ahora no se veía quién
de los 3/4 ya había confirmado y a quién había que esperar. Los datos ya
existían en el modelo (`MatchParticipacion.confirmado` por fila,
`otras_parts`/`mi_part` ya se pasaban a la plantilla), así que es solo
`dashboard.html` + CSS nuevo (`.match-confirmaciones`,
`.match-confirmaciones-item[--ok]`), sin cambios de backend. Se muestra
mientras el match no esté `confirmado_total` (en ese estado ya hay un
mensaje de "confirmado por todas las partes" que lo deja claro). No se
aplica a matches directos (2 bandas): ahí ya queda claro con el badge
existente ("Pendiente de tu confirmación" / "Esperando al otro usuario").
Verificado además del test HTTP con un smoke manual: servidor Flask real
contra una base Postgres temporal, cadena de 4 con una confirmación ya
hecha, `curl` autenticado a `/?estado=pendiente` confirma el HTML
esperado (✓ Ana, ○ Tú/María/Luis). Catálogo i18n actualizado (nuevo
`msgid "Tú"`, antes solo existía como parte de frases más largas como
"Tú libras:"). 1 test nuevo (`test_cadena_4.py`) · 880 tests passing.

refactor(dashboard): rediseño de cómo Activos muestra las publicaciones con
match — sustituye el enfoque anterior (botón "Editar" metido en la
match-card) por tarjetas separadas, a petición del usuario: la tarjeta de
la publicación original (editable, con sus turnos aún `abierto`) se sigue
mostrando en Activos aunque tenga un match `propuesto`, y junto a ella
aparece la tarjeta de ese match (sin botón "Editar" — solo
Confirmar/Rechazar). Pendientes (matches `confirmado_parcial`) mantiene su
comportamiento anterior sin cambios: sigue sin tarjeta de publicación
propia y conserva el botón "Editar" en la match-card, que era la única vía
de edición para ese caso.

En `app/routes/main.py`: eliminada `_query_con_match_activo` (excluía de
Activos toda pub con match `propuesto` o `confirmado_parcial`); tanto el
filtro de la pestaña Activos como el recuento de `_conteos_tabs` pasan a
excluir solo por `_query_pendientes` (`confirmado_parcial`), dejando que las
pubs con match `propuesto` se cuenten y muestren también como tarjeta
propia. En `dashboard.html`, el enlace "Editar" de la match-card en la rama
"pendiente de confirmar" ahora solo aparece si `match.estado ==
'confirmado_parcial'` (la rama "ya confirmado, esperando a los demás" es
exclusiva de Pendientes, así que mantiene su Editar sin condición).

Tests actualizados/nuevos en `test_dashboard.py`: renombrado el test que
verificaba la exclusión (ahora deja claro que es solo por
`confirmado_parcial`), nuevo test que comprueba que Activos muestra ambas
tarjetas para un match `propuesto` y que el botón Editar aparece una sola
vez (en la original, no en la de match), y ajustado el contador esperado
de la pestaña Activos (pasa de 1 a 2, ya que ahora son dos tarjetas).
Catálogo i18n actualizado (pybabel extract/update/compile) · 879 tests
passing.

fix(dashboard): una publicación con un match activo (`propuesto` o
`confirmado_parcial`), aunque sea parcial — por ejemplo, pedía varios días y
solo uno hizo match —, desaparecía por completo de "Mis cambios > Activos"
(y de "Pendientes"): la pestaña excluye la tarjeta de publicación editable
en cuanto existe cualquier match activo, y en su lugar solo se mostraba la
match-card, que no tenía botón "Editar". El usuario quedaba sin forma de
modificar la publicación aunque otros turnos suyos siguieran sin resolver.
Añadido enlace "Editar" (a `publicaciones.editar`, vía
`mi_part.publicacion_id`) en ambas ramas de acciones de la match-card en
`dashboard.html` (pendiente de confirmar y ya confirmada esperando a los
demás) — cubre tanto Activos (`propuesto`) como Pendientes
(`confirmado_parcial`). El backend (`editar_publicacion`) ya rechazaba y
recreaba los matches activos de la publicación al guardar cambios, así que
no hizo falta tocar la lógica de negocio. Dos tests nuevos en
`test_dashboard.py` (uno por cada estado de match) que comprueban que el
enlace de edición aparece en el HTML. Catálogo i18n actualizado (pybabel
extract/update/compile) · 876 tests passing.

feat(dashboard): el botón "Avisar por WhatsApp" que ya existía para los
matches `cadena_4` (con el texto completo de quién libra/trabaja cada día,
para reenviar a los otros 3) se extiende a `cadena_3` — antes ese bloque en
`dashboard.html` comprobaba `match.tipo == 'cadena_4'` explícitamente y
dejaba fuera las cadenas de 3 bandas. Ahora comprueba `es_cadena` (ya
definido arriba como `match.tipo in ('cadena_3', 'cadena_4')`) y el texto
del mensaje se adapta según `match.tipo` ("listo para cerrar entre los 3/4").
Nuevo test en `test_cadena_3.py` (mismo patrón que el ya existente en
`test_cadena_4.py`: verifica que aparece el botón wa.me y que el texto usa
el nombre de cada usuario en vez de "Tú libras/trabajas"). Catálogo i18n
actualizado (pybabel extract/update/compile).

feat(editar): el calendario tap-to-select de `/publicar` (elegir franja +
tocar días) se extiende a `/editar`, que hasta ahora seguía usando las
filas manuales "fecha + tipo de turno" con un botón "+ Añadir otro turno" —
inconsistente con el flujo de publicar y sin forma de tocar varios días de
un tirón. `app/static/js/calendario-turnos.js` gana la opción
`seleccionInicial` (array de `[fecha, franjaId]`) para precargar la
selección del widget con los turnos ya guardados de la publicación (usa
`'0'` para "cualquier turno" en aceptados); si no hay `prefillFecha`
explícito, el mes inicial visible pasa a ser el de la fecha más temprana
de esa selección en vez de siempre el mes actual. `editar.html` pasa de
las filas manuales a los mismos `<div id="cal-cedidos">`/`cal-aceptados`
que `publicar.html`, con los datos de precarga embebidos como JSON
(`<script type="application/json">`) — el backend no cambia: sigue
generando los mismos inputs ocultos `fecha_/franja_{prefix}_N` que ya
consumía `_extraer_turnos`, así que `editar_publicacion()` y su reemplazo
íntegro de turnos_cedidos/turnos_aceptados quedan intactos (mismo
comportamiento de siempre ante ediciones de publicaciones parcialmente
resueltas). Nuevo `e2e/test_editar_publicacion.py` (2 tests, mismo patrón
de `test_publicar.py`: precarga visible + varios días de un tirón).
Catálogo i18n actualizado (pybabel extract/update/compile). 876 tests
unitarios passing.

feat(auth): login persistente ("recuérdame" siempre activo, como una app) —
`login_user(usuario, remember=True)` en los tres puntos de entrada
(`registro`, `login`, `login/demo`) en vez del `login_user(usuario)` sin
"remember" que había. Flask-Login guarda entonces una cookie
`remember_token` independiente de la cookie de sesión (dura 365 días por
defecto), así que aunque el navegador/PWA se cierre y la cookie de sesión
(no permanente) desaparezca, la siguiente petición se re-autentica sola a
partir de la cookie "remember me" — sin tocar `user_loader` ni el modelo
`Usuario`. La única forma de perder la sesión sigue siendo la acción
explícita del usuario (`auth.logout`, que ya limpiaba la cookie vía
`session["_remember"]="clear"` de Flask-Login). Añadido también
`SESSION_COOKIE_SAMESITE`/`REMEMBER_COOKIE_SAMESITE = "Lax"` (base
`Config`) y `SESSION_COOKIE_SECURE`/`REMEMBER_COOKIE_SECURE = True` en
`ProductionConfig` (Railway sirve siempre sobre HTTPS). 4 tests nuevos en
`tests/test_auth_routes.py` (cookie se fija en login/login-demo/registro,
sesión sobrevive a perder la cookie de sesión simulando cierre de la app,
logout limpia la cookie) · 874 tests passing. Implementado en un worktree
sobre `staging`.

feat(matches): desconfirmar un match ya confirmado por el propio usuario,
por si cambia de idea antes de que el cambio quede cerrado del todo.
Nuevo `POST /matches/<id>/desconfirmar` + `desconfirmar_participacion()`
en `app/services/matches.py`: pone `confirmado=False`/`fecha_confirmacion=
None` en la participación propia y recalcula el estado del match —
`confirmado_parcial` si alguna otra parte sigue confirmada (relevante en
cadenas de 3+), o `propuesto` si nadie más lo está. Reutiliza
`_get_match_validado` (bloquea con 409 si el match ya está
`confirmado_total`/`rechazado`, igual que confirmar/rechazar); 409
también si el usuario no tenía nada que desconfirmar. Notifica a las
demás partes (`Notificacion` tipo `desconfirmacion` + push, reutilizando
la preferencia `notif_confirmacion_parcial`). Botón "Desconfirmar" en el
dashboard junto al aviso "Has confirmado. Esperando...". Catálogo i18n
actualizado (pybabel extract/update/compile). 11 tests nuevos (servicio +
ruta + caso de cadena a 3). 816 tests passing. Implementado en un
worktree sobre `staging`.

B19 en marcha: "ocasiones a 4" (cadena de intercambio A→B→C→D→A), siguiendo el
mismo patrón que la cadena a 3 (B13). Paso 1 completado: motor puro
`detectar_cadena_4` en `app/matching/engine.py`. Paso 2 completado: capa de
servicio `buscar_cadenas_4_para`/`crear_match_cadena_4` (triple bucle
anidado, ciclo completo, sin sintéticas todavía) en
`app/matching/service.py` · 12 tests en `tests/test_cadena_4.py` mirroring
`test_cadena_3.py`. Paso 3 completado: `buscar_cadenas_4_para`/`crear_match_cadena_4` enganchados
en las 3 rutas que ya disparan cadena_3 (`/publicar`, editar, contraoferta
— `app/routes/publicaciones.py`) · 1 test de integración de ruta nuevo.
Paso 4 completado: badge "¡Cambio a 4 bandas!" en `dashboard.html`,
generalizando los checks hardcodeados `match.tipo == 'cadena_3'` (ahora
`es_cadena = match.tipo in ('cadena_3','cadena_4')`) · 1 test de ruta
nuevo. Paso 5 completado: columna `sintetica_pub_intermedio_id` en
`PublicacionCambio` (nullable, guarda la banda real intermedia "B" de un
trío A→B→C ya cerrado cuando la sintética completa el hueco C→D→A;
siempre NULL en sintéticas de cadena_3) + migración `f182c4111872`
(`flask db heads` → 1 head; downgrade con nombre de constraint explícito
`fk_sintetica_pub_intermedio`, igual que `e8e3d3c815bd`). Paso 6
completado: capa de servicio para cadenas parciales de 4 (3 bandas reales
+ 1 hueco) en `app/matching/service.py` — `buscar_cadenas_parciales_4_para`
(mismo bucle que `buscar_cadenas_3_para` pero exige que el 3er eslabón NO
cierre, si no sería ya una cadena_3 completa), `crear_pub_sintetica`
extendida con `pub_intermedio` opcional (mismo cálculo cedido/aceptado que
cadena_3, solo depende de los 2 extremos del hueco), `crear_aviso_oportunidad_4`
(3 destinatarios, cada uno referencia al siguiente del ciclo),
`procesar_cadena_parcial_4` (combinador) y `crear_cadena_4_desde_sintetica`
· textos/prefs de push añadidos en `app/push/sender.py` · 12 tests en
`tests/test_sintetica_4.py` mirroring `test_pub_sintetica.py`. Nota de
entorno: la BD de test compartida (`turnero_test`) puede tener el esquema
desactualizado si hay otro job/worktree corriendo tests en paralelo con un
modelo distinto (create_all() no altera columnas en tablas ya existentes);
si aparecen errores "UndefinedColumn", usar una BD de test privada vía
`TEST_DATABASE_URL` para verificar antes de sospechar de un bug real.
Fix aplicado tras el paso 6: `buscar_cadenas_parciales_4_para` asumía que
la publicación consultada era siempre la primera banda (A); un camino
abierto A→B→C no tiene la simetría rotacional de un ciclo cerrado, así
que si publicaba último el intermedio o el final del trío, no se
detectaba. Ahora busca las 3 posiciones y devuelve el trío completo
`(pub_a, pub_b, pub_c)` en vez de asumir el rol de la publicación
consultada · 2 tests nuevos (detección desde el intermedio y desde el
final). Paso 7 completado: enganchado todo en `app/routes/publicaciones.py`
— `buscar_cadenas_parciales_4_para`/`procesar_cadena_parcial_4` en las 3
rutas que ya disparan cadena_3 (`/publicar`, editar, contraoferta); nuevo
helper `_resolver_sintetica(pub, sint)` que branchea entre
`crear_cadena_3_desde_sintetica`/`crear_cadena_4_desde_sintetica` según
`sint.sintetica_pub_intermedio_id`, usado en esas 3 rutas y en
`me_interesa` (que también generaliza el flash de éxito según
`match.tipo`) · 4 tests de integración nuevos (publicar cierra el hueco
generando la sintética, publicar el 4º cierra la cadena, «Me interesa»
sobre una sintética de cadena_4). 199 tests relacionados (sintética,
cadena, matching, publicar, contraoferta, me_interesa) passing. Siguiente
paso: ciclo de vida — `_cancelar_sinteticas_de`/`_eliminar_sinteticas_de`
en `app/services/publicaciones.py` deben incluir
`sintetica_pub_intermedio_id == pub_id` en el filtro OR, para que
cancelar/eliminar la publicación intermedia también cascada a la
sintética de cadena_4.

Paso 8 completado: `_cancelar_sinteticas_de`/`_eliminar_sinteticas_de`
(`app/services/publicaciones.py`) incluyen ahora
`sintetica_pub_intermedio_id == pub_id` en su filtro OR — antes, cancelar
o eliminar la banda intermedia de un trío no tocaba la sintética
dependiente (bug real confirmado por test: quedaba `abierta` al cancelar,
y `ForeignKeyViolation` al eliminar). 4 tests nuevos (cancelar cada una de
las 3 bandas reales, eliminar la intermedia sin error) · 64 tests
relacionados passing.

Paso 9 completado: etiqueta "Oportunidad a 4" distinguida de "Oportunidad
a 3" en calendario y buscador, según `sintetica_pub_intermedio_id` —
`resumen_publicaciones` (`app/services/calendario_mercado.py`) añade
`es_sintetica_4`; `app/routes/calendario.py` elige la etiqueta con ese
campo; `_cargar_sint_info` (`app/routes/main.py`) añade `pub_intermedio`;
`app/templates/main/cambios.html` branchea badge + mensaje ("Cambio a 4
con X, Y y Z") cuando hay banda intermedia. Catálogo i18n actualizado
(pybabel extract/update/compile). 6 tests nuevos (2 servicio, 2 ruta
calendario, 1 ruta cambios) · 106 tests relacionados passing. Siguiente
paso: preferencia de usuario para mostrar/ocultar oportunidades a 3 y a 4
por separado en el calendario (Ofertas/Peticiones).

Paso 10 completado: columnas `mostrar_oportunidad_3`/`mostrar_oportunidad_4`
en `Usuario` (booleanas, default True, server_default — mismo patrón de
un solo paso que `notif_*`) + migración `fe34f9af4a2b`. `_candidatas`/
`construir_calendario_mes` (`app/services/calendario_mercado.py`) aceptan
esos dos flags y excluyen las sintéticas del tipo correspondiente.
`app/routes/calendario.py` los lee de `current_user` al construir el
calendario, y expone `POST /calendario/preferencias` (checkboxes con
auto-submit `onchange`, sin página de ajustes separada — el control vive
directamente en la vista del calendario, junto al selector Ofertas/
Peticiones, tal y como pidió el usuario). Catálogo i18n actualizado. 6
tests nuevos (2 servicio, 3 ruta calendario, con `#, fuzzy` corregido a
mano tras `pybabel update` porque emparejó mal 2 msgid nuevos con una
traducción existente). **B19 completo: 854 tests unitarios passing.**
Nota: `.backlog` no está versionado en git (archivo local sin trackear
solo en el checkout original del usuario) — no se puede actualizar desde
este worktree; queda pendiente que el usuario tache a mano la línea
"cambios a 4". Alcance completo de B19 (visto con el usuario):
detección + confirmación de ciclos completos de 4, sintéticas/avisos para
cadenas parciales de 4 (3 bandas reales + 1 hueco) igual que ya hace la
cadena a 3, y una preferencia de usuario para mostrar/ocultar oportunidades
a 3 y a 4 por separado en el calendario (Ofertas/Peticiones).
feat(publicar): calendario tap-to-select para turnos cedidos/aceptados —
una usuaria pidió un modo más ágil de ofrecer/pedir muchos turnos en vez de
añadirlos uno a uno. Se validó primero un mockup interactivo (Artifact) con
el usuario antes de implementar. Sustituye las filas manuales "fecha + tipo
de turno" de `/publicar` por: elegir la franja (chip) y tocar los días de
un calendario mensual; se puede repetir el ciclo con otra franja para
mezclar tipos de turno en la misma publicación. Reutiliza `.planilla-cal`/
`.cal-celda`/`.cal-bandas-row`/`.cal-banda` (mismo patrón visual que
`/calendario` y `/planilla`) en vez de inventar un componente nuevo.

- El backend no cambia: el widget (`app/static/js/calendario-turnos.js`,
  clase `CalendarioTurnos`) genera los mismos inputs ocultos
  `fecha_{prefix}_N`/`franja_{prefix}_N` (renumerados de forma contigua en
  cada render) que ya parseaba `_extraer_turnos` en
  `app/routes/publicaciones.py`.
- Las franjas del selector son las mismas que ya devolvía la ruta
  (`FranjaHoraria` scoped por `grupo_intercambio_id`), así que las franjas
  personalizadas que un usuario crea desde "¿No encuentras tu tipo de
  turno?" aparecen como chip igual que Mañana/Tarde/Noche/Diurno 12h/
  Nocturno 12h — requisito explícito del usuario, cubierto sin lógica
  nueva, solo pasando los datos ya existentes al JS
  (`_franjas_a_json`, nuevo helper en `publicaciones.py`).
- Un día tocado con 2+ franjas se pinta con el mismo patrón de "bandas"
  que ya usa el calendario de mercado (`.cal-bandas-row`/`.cal-banda`),
  en vez de inventar un tratamiento visual nuevo para el caso multi-franja.
- Prefill desde `/calendario?fecha=&modo=` (Ronda 2, Paso 2): ya no es un
  `value=""` en un `<input>` estático (no existe tal input ahora); el mes
  correcto se abre solo y el día se marca con un aro naranja
  (`data-sugerida="true"`) hasta que el usuario confirma tocando una franja
  y ese día. Los 4 tests de integración de prefill (`tests/test_publicar.py`)
  se reescribieron para comprobar las constantes JS embebidas
  (`PREFILL_FECHA`/`PREFILL_MODO`) en vez del `value=""` que ya no existe;
  el test e2e de drill-down (`test_dia_vacio_ofrece_publicar_cambio`) se
  actualizó a la nueva aserción `data-sugerida="true"`.
- e2e reescritos para tocar franja+día en vez de `fill()`/`select_option()`
  sobre inputs que ya no existen: `e2e/test_publicar.py` (+1 test nuevo,
  `test_publicar_varios_turnos_de_una_franja_de_un_tap`, el caso de uso que
  motivó el cambio), `e2e/test_sintetica_golden_path.py` y
  `e2e/test_sintetica_staging.py` (este último no se ejecuta en local,
  actualizado igualmente por consistencia).
- Catálogo i18n actualizado (`pybabel extract/update/compile`); de paso
  puso al día ~26 strings pendientes de commits anteriores que nunca habían
  pasado por `pybabel update` (no relacionados con este cambio, solo
  arrastre de deuda técnica de i18n detectado al ejecutar el comando).
- 815 tests unitarios/integración + 29 tests e2e relevantes (backend
  `test_publicar.py` + los 4 e2e de publicar + drill-down + golden path 3
  bandas + auth) passing en ventanas sin contención. Nota: la BD Postgres
  local de test (`turnero_test`) es compartida entre sesiones/worktrees
  concurrentes de este entorno — se observaron `UndefinedTable`/
  `ObjectDeletedError`/deadlocks en `tests/test_turnos_unidad.py`,
  `tests/test_push.py`, `tests/test_publicar_junte.py` etc. al correr la
  suite completa mientras otra sesión ejecutaba pytest en paralelo contra
  la misma BD; confirmado no relacionado con este cambio (esos ficheros no
  se tocaron y las mismas pruebas pasan limpias en solitario). Mismo
  fenómeno ya documentado en una entrada anterior de este fichero.
- Trabajo hecho en worktree `worktree-calendario-multi-select` sobre
  `staging` (pedido explícito del usuario), pendiente de revisión/push.

Siguiente: decidir si este mismo widget se reutiliza en `editar.html` y
`contraoferta.html` (mismo patrón turno-row hoy) — fuera de alcance de
este paso, el usuario solo pidió el flujo de publicar.

---

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

fix(dashboard): las oportunidades a 4 no aparecían en la pestaña Activos
(reportado por el usuario, investigado conectando a la BD de producción).
Dos bugs de código confirmados y corregidos:
- `avisos_interes` en `app/routes/main.py` (sección de avisos de Activos)
  solo filtraba `tipo="aviso_oportunidad_3"`, a diferencia de la ruta
  `/avisos` que ya incluía ambos tipos — nunca mostraba un
  `aviso_oportunidad_4` aunque existiera. Añadido `aviso_oportunidad_4` al
  filtro.
- La tarjeta de publicación puente (`oportunidades_3` en el dashboard)
  incluye en su query tanto sintéticas de cadena_3 como de cadena_4 (no
  filtra por `sintetica_pub_intermedio_id`), pero la plantilla
  (`dashboard.html`) etiquetaba siempre "Oportunidad a 3 bandas" y solo
  mencionaba a los dos extremos, nunca al intermediario — una oportunidad
  a 4 era indistinguible de una a 3. Ahora la plantilla distingue
  `es_cadena_4` (vía `sint_info[...].pub_intermedio`), cambia badge/texto/
  mensaje de WhatsApp a "a 4" y menciona al intermediario en el header.
- 3 tests de regresión nuevos en `tests/test_sintetica_4.py`. 872 tests
  passing.

Investigada además una anomalía real en producción, sin causa confirmada:
la edición de la publicación 818 (usuario 7) generó 24 oportunidades a 4 y
12 a 3, pero ninguna de las 36 generó una `Notificacion` para el propio
usuario 7 (0 de 20 pares únicos esperados en el rol "C" del trío — el
usuario que hace la edición), mientras que los otros dos roles del mismo
lote sí se comportaron perfectamente (22/22 y 10/10 pares únicos
esperados, con deduplicación correcta). Se intentó reproducir con 5
variantes de fidelidad creciente contra una BD de test privada — llamada
directa a `crear_aviso_oportunidad_4`, ruta `/publicar` con varios tríos,
ruta `/editar` con sintéticas previas canceladas, y una réplica a escala
1:1 de los 24 tríos de producción (mismo patrón de repetición de
`pub_a`/intermedio) — y en los 5 casos el código funcionó correctamente
(100% de las notificaciones esperadas). No se ha podido determinar la
causa raíz; no se ha aplicado ningún cambio especulativo para no
enmascarar un problema real. Hipótesis más plausible sin confirmar: un
posible doble envío del formulario de edición (no hay protección contra
doble clic en `/publicaciones/<id>/editar`). Pendiente: decidir con el
usuario si se añade logging de diagnóstico temporal para capturar la
próxima ocurrencia, y/o protección anti-doble-envío en el formulario como
mitigación preventiva independiente de la causa.

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
- [x] feat(matches): desconfirmar un match ya confirmado por el propio usuario, por si cambia de idea antes de que el cambio quede cerrado del todo · `POST /matches/<id>/desconfirmar` + `desconfirmar_participacion()` reutiliza `_get_match_validado` (409 si el match ya está `confirmado_total`/`rechazado`, o si el usuario no había confirmado) · recalcula el estado del match a `confirmado_parcial` si otra parte sigue confirmada (cadenas de 3+) o a `propuesto` si no · notifica a las demás partes (`Notificacion` tipo `desconfirmacion` + push) · botón "Desconfirmar" en el dashboard · catálogo i18n actualizado · 11 tests nuevos · 816 tests passing
- [x] feat(publicar): calendario tap-to-select (elegir franja + tocar días) sustituye las filas manuales de `/publicar` · mockup Artifact validado con el usuario antes de implementar · backend sin cambios (mismos inputs ocultos `fecha_/franja_{prefix}_N`) · franjas dinámicas por grupo, incluidas las personalizadas por el usuario (chip automático) · multi-franja el mismo día con `.cal-bandas-row` reutilizado de `/calendario` · prefill desde `/calendario` pasa de `value=""` a resaltado `data-sugerida` · `app/static/js/calendario-turnos.js` nuevo · e2e reescritos (4+1 test nuevo en `test_publicar.py`, golden path, drill-down) · 18 tests backend + 11 e2e relevantes passing
- [x] feat(auth): login persistente ("recuérdame" siempre activo) — `login_user(..., remember=True)` en registro/login/login-demo + `SESSION_COOKIE_SAMESITE`/`REMEMBER_COOKIE_SAMESITE="Lax"` y `SESSION_COOKIE_SECURE`/`REMEMBER_COOKIE_SECURE=True` en producción · el usuario ya no pierde la sesión al cerrar el navegador/PWA, solo con logout explícito · 4 tests nuevos · 874 tests passing
- [x] feat(editar): el calendario tap-to-select de `/publicar` se extiende a `/editar`, sustituyendo las filas manuales "fecha + tipo de turno" · `calendario-turnos.js` gana la opción `seleccionInicial` para precargar la selección con los turnos ya guardados (mes inicial = el de la fecha más temprana precargada) · backend sin cambios (mismos inputs ocultos `fecha_/franja_{prefix}_N`) · 2 tests e2e nuevos (`e2e/test_editar_publicacion.py`) · catálogo i18n actualizado · 876 tests unitarios passing
- [x] fix(dashboard): una publicación con un match activo (`propuesto` o `confirmado_parcial`), aunque sea parcial, desaparecía por completo de "Mis cambios > Activos" y "Pendientes" en vez de seguir editable · añadido enlace "Editar" en la match-card para ese caso
- [x] refactor(dashboard): tarjetas separadas para publicación original y match en Activos, a petición del usuario, en vez del botón "Editar" metido en la match-card · 879 tests passing
- [x] feat(dashboard): las tarjetas de match de cadenas de 3/4 bandas muestran quién ya confirmó (✓, chip verde) y quién falta (○) — solo plantilla + CSS, el dato (`MatchParticipacion.confirmado`) ya existía · se muestra mientras el match no esté `confirmado_total` · catálogo i18n actualizado · 1 test nuevo · 880 tests passing
- [x] fix(dashboard): investigado el reporte de que la tarjeta de Pendientes no reflejaba nuevas confirmaciones de otros al recargar — no se pudo reproducir ningún bug de datos/plantilla (verificado con test client y con servidor real + sesiones HTTP independientes); se añade `Cache-Control: no-store` a `main.index` como medida defensiva ante caché de navegador/proxy, ya que la página es dinámica y personal y no llevaba cabecera anti-caché · 4 tests nuevos · 884 tests passing
- [x] fix(matching): `crear_match_cadena_3`/`crear_match_cadena_4` no registraban el `turno_aceptado_id` que cada banda recibe de la anterior en el ciclo (solo el `turno_cedido_id` que cede), así que al confirmarse una cadena el turno ya conseguido nunca se marcaba `resuelto` y seguía apareciendo como pendiente en la publicación reactivada · reportado por el usuario en producción (match cadena_4 confirmado, publicación 818) · fix reutiliza `_primer_aceptado_que_cubre` (ya usado por `crear_match_directo`) · 4 tests de regresión nuevos · 887 tests passing
- [x] Fase 10, paso 1: modelos `DocumentoCambio`/`ParticipanteDocumentoCambio`/`FirmaDocumentoCambio` para la hoja de cambio digital con firma (reproduce `hojacambios.png`, formulario "SOLICITUD DE CAMBIO DE TURNO O GUARDIA" del Hospital La Paz) · migración `3f8d2428aa64` · 9 tests nuevos · 896 tests passing
- [x] Fase 10, paso 2a: servicio `crear_documento_cambio`/`firmar_documento`/`generar_notas_ilog` · 5 tests nuevos
- [x] Fase 10, paso 2b: rutas + formulario + firma con canvas (`pointerdown/move/up`) + notas para ilog copiables · blueprint `documento_cambio`, enlace en nav · catálogo i18n actualizado · 9 tests de rutas + 1 e2e (Playwright, firma real dibujada) · verificado en navegador
- [x] Fase 10, paso 3: plantilla PDF fiel a `hojacambios.png` + botón "Generar PDF" (solo si `completo`) · `generar_pdf_documento`, bajo demanda · logo recortado del PNG real · WeasyPrint crasheó el arranque completo en Railway (dependencias nativas ausentes, dos intentos de nixpacks.toml no lo arreglaron) → sustituido por `xhtml2pdf` (Python puro, sin ese riesgo) · ajuste de maquetación tras desbordar a 2ª página en producción · verificado visualmente con `pdftoppm` en cada iteración
- [x] Fase 10, paso 4: comprobación de factibilidad contra planillas · servicio puro `comprobar_factibilidad` reutiliza las reglas de `compatibilidad_planilla.py` · columna `factibilidad_estado` (no_verificado/factible/no_factible) · aviso visual en `ver.html` según el resultado · 6 tests nuevos
- [x] Fase 10, paso 5: `ESPECIFICACION.md` actualizado con la hoja de cambio digital (entidades, reglas 11-14, CU10, decisión técnica xhtml2pdf, UAT-8.x)
- [x] Fase 10, paso 6: recomprobar factibilidad en la 2ª firma · 1 test
- [x] Fase 10, paso 7: firma cruzada entre cuentas reales · cada uno firma su propia fila desde su cuenta · notificaciones (push + campana) al crear y al firmar · migración `c2938aae9b98` · 12 tests + e2e actualizado
- [x] Fase 10, paso 8: el aviso de autorización/denegación de la supervisora (`documento_cambio_autorizado`/`documento_cambio_denegado`) incluía solo el número de hoja (y, al denegar, el motivo) pero no los datos del cambio — nuevo `_resumen_cambio(documento)` en `app/services/documento_cambio.py` añade, para cada participante, quién libra qué turno/día y quién trabaja qué turno/día a cambio, y se concatena al mensaje ya existente en `autorizar_documento`/`denegar_documento` · 2 tests nuevos (`test_servicio_documento_cambio.py`)
- [x] feat(avisos): el aviso de confirmación (`confirmado_total`) y de rechazo (`rechazo`) de un match del motor de matching (distinto del flujo de hoja de cambio del paso anterior) ahora se muestra también en `/avisos` con los datos del cambio — quiénes lo hacen y qué día/franja libra y trabaja cada participación — en vez de quedar invisible (esos dos tipos de `Notificacion` no entraban en la consulta de `/avisos`, solo generaban un push agregado sin detalle) · refactor: `_calcular_trabajas` se traslada de `app/routes/main.py` a `app/services/matches.py::calcular_trabajas` (lógica de dominio del match, no de la ruta) y se reutiliza desde ambos sitios · catálogo i18n actualizado (reutiliza los mismos msgid `libra:`/`trabaja:`/`cualquier turno` ya usados en el dashboard) · 2 tests nuevos · verificado con las suites de match/notificaciones/dashboard/cadenas (162 tests) limpias en una ventana sin contención de la BD de test compartida con otra sesión concurrente · 948 tests passing (suite completa, tras integrar con el trabajo paralelo de Fase 10)

- [x] chore(seed-staging): `scripts/seed_staging.py` amplía de forma aditiva la unidad real UCO·Hospital Universitario La Paz·Enfermería (además de crear su propio conjunto de usuarios como hasta ahora) · `app/services/demo.py` refactorizado para extraer `sembrar_contenido_bot(unidad, categoria, incluir_planillas=True)` reutilizable (antes solo servía a la unidad de demostración aislada) · `BOT_ACCOUNTS` pasa a público · nuevo generador puro `generar_rota()` (14 plantillas semanales `_COMBOS_ROTA`/`_PLANTILLA_ROTA`, 7 fases × 2 variantes de noche) que cubre julio-agosto-septiembre 2026 garantizando cobertura diaria de las 5 franjas, descanso obligatorio (`EstadoDiaPlanilla`+`SalienteDia`) al día siguiente de Noche/Nocturno 12h, y 2 días libres/semana por trabajador · supervisora `supervisora.uco@demo.turnero.com` (sustituye a cualquier supervisora previa del mismo grupo de intercambio, salvo que ya tenga hojas de cambio decididas referenciándola) · hojas de cambio (agosto-septiembre 2026) en sus 4 estados posibles (pendiente de firma / completa pendiente de la supervisora / autorizada / denegada) para cada usuario (>=2), emparejando usuarios a "media vuelta" de distancia en el roster (emparejar contiguos fallaba: comparten fase de rota, solo difieren en la variante de turno nocturno, así que nunca hay hueco de intercambio) · usa los servicios reales (`crear_documento_cambio`/`firmar_documento`/`autorizar_documento`/`denegar_documento`) envueltos en `current_app.test_request_context()` (necesario fuera de una request real: Flask-Babel/`url_for` lo requieren) · nunca borra ni toca usuarios ya existentes de esa unidad (aditivo e idempotente, con su propia comprobación independiente de `_ya_sembrado()`) · 18 tests nuevos (`tests/test_seed_staging_rota.py`, `tests/test_seed_staging_uco.py`) · 996 tests passing

- [x] fix(seed-staging): corrige colisión de emails entre la unidad de demostración aislada de producción (`flask seed-demo`, `DEMO_ENABLED=true` ya activo en staging) y la ampliación de UCO·La Paz·Enfermería — ambas reutilizaban los mismos `DEMO_ACCOUNTS`/`BOT_ACCOUNTS` de `app/services/demo.py`, y como `usuario.email` es único a nivel de toda la BD, `ampliar_uco_la_paz()` reventaba con un `IntegrityError` en cuanto la unidad demo ya existía (confirmado contra el staging real: la unidad "Urgencias de Demostración" ya tenía sembrados `demo1@turnero.com`/`bot.maria@demo.turnero.com`, y UCO seguía solo con sus 16 usuarios reales, sin rastro de la ampliación) · `sembrar_contenido_bot()` ahora acepta `cuentas_demo`/`cuentas_bot` opcionales · `scripts/seed_staging.py` define `UCO_DEMO_ACCOUNTS`/`UCO_BOT_ACCOUNTS` con emails propios (`uco.<email-base>@demo.turnero.com`) · test de regresión que ejecuta `reset_demo()` + `ampliar_uco_la_paz()` en la misma BD · 997 tests passing

- [x] feat(documento-cambio): "Tabla de cambios" — vista alternativa de `/documentos-cambio/supervisora` pensada para ordenador · una fila por hoja de cambio, columnas atómicas (Nº, fecha, cada trabajador con su cede/recibe por separado, firmas, factibilidad, decisión) y botones Ver/PDF al final de la fila · nueva ruta `GET /documentos-cambio/supervisora/tabla` (misma consulta que `supervisora`, extraída a `_documentos_del_grupo_supervisora()`) · nuevo `.container--wide` (`{% block main_class %}`) para que la tabla no quede encajonada en los 640px del `.container` normal · `.table-scroll` con scroll horizontal si aún así no cabe · enlace cruzado entre ambas vistas ("Ver como tabla"/"Ver como tarjetas") — no se retira `supervisora.html`, coexisten mientras el usuario decide cuál prefiere · verificado visualmente con Playwright (ambas vistas, con datos en los 4 estados) · 3 tests nuevos · 1000 tests passing

- [x] feat(documento-cambio): "Supervisión de cambios" pasa a ser una única vista de tabla (se retira la de tarjetas, `supervisora_tabla.html` se fusiona en `supervisora.html`) con filtros y navegación por mes/año · **regla nueva de negocio**: los cambios `pendiente_firmas` (aún sin las dos firmas) no le han "llegado" todavía a la supervisora — quedan excluidos de raíz de la consulta, no solo ocultos por un filtro; solo se listan documentos `completo` · filtros combinables por querystring (GET, bookmarkable): mes/año (por defecto el mes en curso), fecha exacta (si se indica, sustituye a mes/año), trabajador implicado (uno o dos — con dos, exige que sean justamente esas dos personas del mismo cambio), turno afectado (franja horaria — combinado con fecha exacta identifica un turno concreto: mismo día y misma franja, no dos condiciones independientes), estado de decisión (pendiente de decisión / aceptado / rechazado), factibilidad, número de hoja · todos los filtros implementados con subconsultas independientes (`DocumentoCambio.id.in_(...)`) en vez de un único JOIN con `ParticipanteDocumentoCambio`, para no acoplar entre sí condiciones que pueden recaer en participantes distintos del mismo documento · 9 tests nuevos/reescritos · 974 tests passing

- [x] feat(firma): firma guardada reutilizable — el usuario dibuja su firma una vez en `/perfil/cuenta` y puede firmar hojas de cambio y confirmaciones de match sin repetir el garabato · columna `usuario.firma_guardada` (Text, nullable, sin patrón de 3 pasos por no ser NOT NULL) · migración `8ea99af48f5f`, un solo head · rutas `POST /perfil/firma/guardar` (valida `data:image/`) y `POST /perfil/firma/eliminar` · nueva sección "Firma guardada" en `perfil_cuenta.html` (canvas para dibujar/guardar si no hay una, previsualización + botón eliminar si ya hay) reutilizando `firma-canvas.js` sin cambios de backend · `firma-canvas.js::initFirmaForm` ampliado con un botón opcional `.firma-usar-guardada` que rellena el input oculto con la firma guardada (`data-firma`) y envía el formulario sin exigir dibujo nuevo — el listener de `submit` ahora solo sobrescribe el input con el canvas si se dibujó algo, si no deja el valor ya puesto; si no hay ni dibujo ni valor previo, bloquea igual que antes · botón "Firmar con firma guardada" añadido en `documento_cambio/ver.html` (mismo mecanismo) y, con JS independiente (esa vista no usa `firma-canvas.js`), en el modal de confirmación de match de `dashboard.html` · ambas rutas de firmado existentes (`documento_cambio.firmar`, `matches.confirmar`) no se tocan: ya aceptaban cualquier `data:image/...` válido, venga de un dibujo nuevo o de la firma guardada · catálogo i18n actualizado (solo las cadenas nuevas, sin arrastrar otras ya pendientes de sincronizar) · 10 tests nuevos (modelo, rutas de guardar/eliminar, render condicional en `perfil_cuenta`/`ver.html`/`dashboard.html`) · 1010 tests passing

- [x] feat(firma): ofrece guardar la firma en el momento de firmar, no solo desde `/perfil/cuenta` — feedback del usuario tras probar en staging: la sección de `/perfil/cuenta` "no se encuentra bien" (se deja donde está, no se mueve/promueve) · cuando el usuario dibuja una firma nueva (no usa el botón de firma guardada) y **no tiene** `firma_guardada` todavía, aparece un checkbox "Guardar esta firma para futuras firmas", marcado por defecto · `documento_cambio.firmar` y `matches.confirmar` leen el campo `guardar_firma` del POST: si viene marcado y el usuario aún no tiene firma guardada, la guardan de paso (`if request.form.get("guardar_firma") and not current_user.firma_guardada`) — nunca sobrescribe una ya existente por esta vía, aunque el checkbox no debería llegar a mostrarse en ese caso · en `ver.html` el checkbox es un campo más del mismo `<form>` (sin JS extra) · en el modal de `dashboard.html` (compartido entre todas las tarjetas de match) el checkbox vive fuera del `<form>` de cada match, así que se añade un input oculto `.guardar-firma-input` por formulario y el handler de "Firmar y confirmar" copia el estado del checkbox ahí antes de enviar, igual que ya hacía con `.firma-input` · catálogo i18n actualizado (1 cadena nueva) · 10 tests nuevos (backend de ambas rutas + render condicional del checkbox en `ver.html`/`dashboard.html`) · 1027 tests passing

- [x] feat(documento-cambio): anular un cambio ya autorizado + selección en bloque en "Supervisión de cambios" · migración `93549d8020ab` (`anulado`, `anulado_por_id`, `fecha_anulacion`, `motivo_anulacion` en `documento_cambio`) · `anulado` es un dato aparte de `decision_supervisora`, que conserva el histórico ("esto se autorizó") · `puede_anularse(documento)` comprueba: ya autorizado y no anulado antes, ningún turno implicado ha pasado ya, y la planilla actual de cada participante sigue tal cual quedó tras autorizar (si otro cambio posterior la tocó, no se anula a ciegas) · `anular_documento()` deshace el volcado a planillas (espejo de `volcar_documento_a_planillas`) y, si el documento viene de un match del motor de matching (`match_id`), reabre ese match con `reabrir_match_de_documento()`: turnos vuelven a `abierto`, publicaciones recalculan estado, el match pasa a un estado nuevo `anulado` (distinto de `rechazado`, que es previo a la confirmación) · botón "Anular" en `ver.html` cuando aplica, motivo obligatorio, notifica a ambos implicados · selección en bloque en la tabla (checkboxes + "seleccionar todos", patrón `.fb-bulk-bar` ya usado en `admin/feedback`): un único `<form>` con varios botones `formaction` a 4 rutas (`bloque/pdf|aceptar|denegar|anular`), procesando cada id independientemente y reportando aplicados/omitidos en vez de fallar el lote entero · ids del formulario siempre filtrados contra el grupo de la supervisora antes de actuar · PDF en bloque fusiona con `pypdf` (nueva dependencia explícita en requirements.txt, antes solo transitiva de `xhtml2pdf`) en un único archivo · filtro nuevo "Anulado" en la tabla (excluido de `estado_decision=autorizado`, que ahora solo cuenta lo vigente) · 20 tests nuevos · 169 tests afectados passing (`pytest --testmon`)

- [x] feat(documento-cambio): "Nueva hoja de cambio" ofrece firmar los dos a la vez, no solo esperar a que el compañero firme luego desde su cuenta · casilla "Estamos juntos ahora mismo: firmar los dos ya" en `nuevo.html` que revela un segundo lienzo de firma (reutiliza `setupFirmaCanvas`, ahora exportado desde `firma-canvas.js`) · excepción explícita y deliberada a la firma cruzada habitual (cada uno firma solo lo suyo desde su cuenta) — mismo patrón "mono-cuenta" de la Fase 1 original, ahora como opción en vez de único modo · si se marca, `nueva()` valida que ambas imágenes de firma lleguen y llama a `firmar_documento` dos veces tras crear el documento, dejándolo `completo` en el mismo POST · reutiliza `firma_guardada` del creador si existe (no la del compañero, que no tiene sesión abierta) · pensado también para adopción gradual: los jefes reticentes ya pueden sustituir el papel por la hoja electrónica sin depender de que cuaje antes la comprobación de factibilidad (que ya era puramente informativa, no bloqueaba nada) · la idea de que la supervisora suba la planilla de toda la unidad (en vez de depender de que cada usuario suba la suya) sigue anotada en `.backlog`, no implementada · 4 tests nuevos · 59 tests afectados passing (`pytest --testmon`)

- [x] fix(documento-cambio): `/documentos-cambio/supervisora` usaba `.container--wide` (1200px) y obligaba a scroll horizontal en pantallas de escritorio; pasa a `.container--full` (max-width: none, mismo patrón ya usado en `/planilla/supervision`) para aprovechar toda la anchura disponible.
- [x] feat(planilla): en `/planilla/supervision`, clic en el nombre del trabajador resalta (amarillo) toda su fila para no perder la línea al revisar turnos cerca de fin de mes — toggle vía `classList`, sin persistencia (estado puramente de cliente, se pierde al recargar), varias filas pueden estar resaltadas a la vez.

- [x] fix(documento-cambio): `numero_unidad` es correlativo por unidad, no globalmente único, así que dos hojas de cambio de distintas unidades (o incluso reutilizado tras mucho tiempo en la misma) podían mostrar el mismo "Nº X" y confundir a quien lo lee. Todo punto donde se muestra el número de hoja al usuario (tabla de supervisión, `ver.html`, PDF, email de "hoja completa", notificaciones de autorizar/denegar/anular) ahora añade la fecha de creación (`cambio #%(numero)s del %(fecha)s`) para desambiguar · tests actualizados a juego (89 tests).
- [x] test(e2e): el golden path sintético (`test_golden_path_staging`) dejaba cuentas de prueba (Ana/Pedro/Carlos) huérfanas en staging en cada ejecución; se envuelve en try/finally con un nuevo helper `_eliminar_cuenta()` que borra las tres cuentas vía UI al terminar (best-effort: si el test falla a medio registro, el cleanup no oculta el fallo real).
- [x] fix(i18n): auditoría detectó que `app/routes/planilla.py` tenía ~20 `flash()` con mensaje literal (str/f-string) sin pasar por `_()`, y que `ETIQUETAS_ESTADO` estaba duplicado (con textos distintos: "No disponible" vs "No disponible para cambios") entre `planilla.py` y `planilla_supervision.py` · todos los `flash()` envueltos en `_()`, los f-strings convertidos a placeholders con nombre (`%(n)s`) siguiendo el patrón ya usado en `documento_cambio.py` · `ETIQUETAS_ESTADO` unificado en `app/models/planilla.py` con `lazy_gettext` (necesario porque es un diccionario a nivel de módulo: `_()` normal se evaluaría en el momento de importar, no por request) e importado desde ambas rutas · de paso, se encontró y corrigió un bug de shadowing: `_, num_dias = calendar.monthrange(...)` en 3 archivos que también importan `_` de `flask_babel` convertía `_` en variable local para el resto de esa función, rompiendo cualquier `_()` posterior (renombrado a `_primer_dia_semana`) · **medida preventiva** en `tests/test_i18n.py`: `test_flash_no_usa_literales_sin_traducir` escanea (vía `ast`) todos los `app/routes/*.py` y falla si algún `flash()` recibe un literal sin `_()`/`gettext()`; `test_no_se_reasigna_guion_bajo_en_archivos_con_gettext` falla si una función reasigna `_` en un archivo que lo importa de `flask_babel` — ambos tests fallaban (rojo) contra el código original antes del fix · catálogo de traducción regenerado (`translations/messages.pot`, `translations/es/LC_MESSAGES/messages.po` y `.mo`; se dejó fuera el `messages.pot` de la raíz, que es un artefacto obsoleto sin uso, no referenciado desde ningún script).

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
