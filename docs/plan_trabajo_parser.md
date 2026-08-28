# Plan de trabajo — Parser de mensajes de WhatsApp

> Análisis y justificación de diseño en `docs/analisis_parser.md`. Este documento es
> solo el **plan ejecutable**: qué hacer, en qué orden, y quién lo hace.

## Objetivo

Que un usuario pueda pegar el mensaje de WhatsApp que ya ha escrito y que la app
le deje el formulario de `/publicar` relleno, listo para confirmar.

**No objetivo:** que la IA publique por su cuenta. El único camino de escritura
sigue siendo `publicar_cambio()` tras confirmación explícita en el formulario.

## Cómo usar este documento

- 👤 = lo hace el usuario a mano (no lo puede hacer Claude Code)
- 🤖 = lo hace una sesión de Claude Code
- Marca `[x]` según avances. Este documento es el estado compartido entre sesiones.
- Al terminar cada fase, actualiza `PROGRESS.md` y haz commit (convención del proyecto).
- **Las puertas (🚦) son bloqueantes**: no pases a la fase siguiente sin cumplirlas.

---

## Fase 0 — Diagnóstico y corpus (manual, ~1 semana)

Esta fase hace dos cosas a la vez: contesta si el parser merece la pena **y**
produce el corpus anotado que la Fase 4 necesita de todas formas. No es un desvío.

### 0.1 — Medir la penetración real

- [ ] 🤖 Consultar en producción, para la unidad "Urgencias La Paz - Enfermería":
      usuarios registrados, activos últimos 30 días, publicadores únicos por semana,
      y retención de publicadores (cuántos publicaron ≥2 veces)
- [ ] 👤 Exportar/copiar los mensajes de petición de cambio del grupo de WhatsApp
      de una semana completa
- [ ] 👤 Contar remitentes únicos de esos mensajes
- [ ] 👤 Cruzar: de esos remitentes, **cuántos tienen cuenta activa en la app**

**Interpretación:**
- Mayoría *sin* cuenta → el problema es liquidez/captación, no fricción. El parser
  es prematuro. **Para aquí** y replantea.
- Mayoría *con* cuenta que aun así fue al WhatsApp → es fricción o hábito. Sigue.

### 0.2 — Semana de parser manual (Wizard of Oz)

- [ ] 👤 Durante 7 días, coger cada mensaje de cambio del WhatsApp y publicarlo a
      mano en la app (con permiso de la persona, o avisándola después)
- [ ] 👤 Anotar cada día: nº de mensajes procesados, nº que casaron, nº que casaron
      **en cadena de 3 o 4** (esto último es el diferencial frente al WhatsApp)
- [ ] 👤 Anotar también: cuáles fueron difíciles de interpretar y por qué

### 🚦 Puerta 0 — Decisión de construir

- [x] 👤 ¿Casó una proporción razonable de los cambios publicados a mano?
- [x] 👤 ¿Salió al menos **una** cadena de 3-4 que en el WhatsApp no habría existido?

Si ambas son "no", el cuello de botella no es meter el mensaje en la app.
**No construyas el parser**; anota la conclusión abajo en el registro de decisiones y para.

> ## ⛔ PUERTA 0 NO SUPERADA — 2026-08-16. Parser EN PAUSA.
>
> **Muestra manual de WhatsApp (21 cambios, 20 clasificados):** 2 sin cuenta,
> 2 desconocidos, 12 con cuenta que NO publicaron en la app, 4 con cuenta que sí.
> → El 80% de quien pide cambios **ya tiene cuenta**. El registro no es el cuello de botella.
>
> **Datos de producción, unidad 5 (Urgencias / La Paz / Enfermería, 118 usuarios):**
>
> | Métrica | Valor |
> |---|---|
> | Han publicado alguna vez | **84 / 118 (71%)** |
> | Publicaciones históricas (sin sintéticas) | 177 |
> | → caducadas | 92 (52%) |
> | → abiertas | 65 (37%) |
> | → **confirmadas** | **20 (11%)** |
> | Publicaciones últimos 7 d | 7 (6 publicadores) |
> | Activos semanales (proxy) | ~19 / 118 (16%) |
>
> Publicaciones por semana: 57 → 46 → 20 → 10 → 12 → 15 → 9 → 7 (caída monótona
> desde el lanzamiento del 22-jun). Publicadores nuevos agotados: 40, 24, 4, 4, 3, 4, 2, 2.
>
> **Conversión de matches por tipo (global):**
>
> | Tipo | Rechazados | Confirmados | Conversión |
> |---|---|---|---|
> | directo_2 | 33 | 10 | ~22% |
> | cadena_3 | 86 | 0 | 0% |
> | cadena_4 | 141 | 1 | 0,7% |
>
> **Conclusión:** el problema NO es fricción al publicar (71% ya publicó al menos
> una vez), es **retención**, causada por un embudo que convierte al 11%. El parser
> metería más publicaciones en un embudo que pierde el 89%. Ganancia estimada si
> funcionase perfecto: ~1,3 cambios cerrados más.
>
> **Diagnóstico y plan de remediación → `docs/diagnostico_cadenas.md`.**
>
> **Condición para reanudar esta fase:** que la conversión de publicación a cambio
> confirmado en la unidad 5 suba de forma sostenida por encima del ~25%. Con ese
> embudo, capturar las publicaciones que hoy se quedan en el WhatsApp sí compensa.
> Todo lo escrito por debajo de esta línea sigue siendo válido cuando se reanude.

### 0.3 — Corpus

- [ ] 👤 Recolectar 300-500 mensajes del grupo (los de la semana manual ya van anotados)
- [ ] 🤖 Escribir `scripts/anonimizar_corpus.py`: sustituye nombres propios por
      `[NOMBRE1]`, `[NOMBRE2]`, teléfonos y cualquier identificador
- [ ] 👤 Ejecutar la anonimización y **revisar a mano** que no queda ningún nombre
- [ ] 🤖 Añadir `tests/fixtures/corpus/` a `.gitignore` (el corpus real NO se commitea)
- [ ] 👤 Anotar a mano ~20 mensajes con su publicación correcta (semilla para el v0)
- [ ] 👤 Dividir el corpus: `dev.jsonl` (~60) y `test.jsonl` (el resto).
      **El test set no se mira hasta la Fase 5.**

Formato de cada línea:
```json
{"id": "w001", "texto": "cambio mi noche del 14 por cualquier mañana la semana que viene",
 "esperado": {"tipo": "cambio",
              "cedidos": [["2026-08-14", "Noche"]],
              "aceptados": [["2026-08-17", null]]}}
```

- [ ] 👤 Del dev set, elegir 8-15 ejemplos variados para usar como few-shot en el prompt
- [ ] 👤 Anotar el vocabulario real observado: motes de franjas, formas de escribir
      fechas, abreviaturas → `docs/vocabulario_corpus.md`

### 🚦 Puerta 0.3

- [ ] Corpus anonimizado, dividido en dev/test, con ≥20 anotados y fuera de git

---

## Fase 1 — Preparación técnica

- [ ] 🤖 Crear worktree: `git worktree add ../turnero-asistente -b feat/asistente-parser staging`
- [ ] 🤖 Añadir `anthropic` a `requirements.txt`
- [ ] 👤 Crear la API key en console.anthropic.com y ponerla en el `.env` local
- [ ] 👤 Poner un **límite de gasto mensual** en la consola de Anthropic (protección
      contra bucles o abuso)
- [ ] 🤖 Verificar que `.env` está en `.gitignore` y que la clave no aparece en ningún
      archivo versionado
- [ ] 🤖 Leer la clave desde config Flask (`ANTHROPIC_API_KEY`), nunca hardcodeada,
      nunca expuesta al cliente

---

## Fase 2 — Contrato de datos (TDD, sin red)

- [ ] 🤖 `app/services/asistente/__init__.py`
- [ ] 🤖 Test: `PropuestaPublicacion` valida una propuesta correcta
- [ ] 🤖 Test: rechaza tipo fuera de `TIPOS_PUBLICACION`
- [ ] 🤖 Test: rechaza fecha con formato inválido
- [ ] 🤖 Test: acepta `franja: null` en turnos aceptados (= cualquier franja)
- [ ] 🤖 Implementar `app/services/asistente/schema.py` (Pydantic):
      `TurnoPropuesto`, `PropuestaPublicacion` con `campos_faltantes: list[str]`
- [ ] 🤖 Commit

---

## Fase 3 — Resolvedor (TDD, sin red) ← el trabajo real

Convierte una `PropuestaPublicacion` en los argumentos de `publicar_cambio()`.
Todo determinista, todo testeable offline. Aquí van la mayoría de los tests.

- [ ] 🤖 Test: nombre de franja exacto → `franja_horaria_id` correcto
- [ ] 🤖 Test: la búsqueda de franja se limita al `grupo_intercambio` del usuario
      (una franja con el mismo nombre en otro grupo **no** debe resolver)
- [ ] 🤖 Test: normalización (mayúsculas, tildes, espacios) resuelve igualmente
- [ ] 🤖 Test: sinónimos del diccionario del proyecto resuelven ("mañanita" → "Mañana")
- [ ] 🤖 Test: franja desconocida → entra en `problemas`, NO se inventa un id
- [ ] 🤖 Test: `franja: null` en aceptados → `cualquier_franja=True`
- [ ] 🤖 Test: fecha en el pasado → `problemas`
- [ ] 🤖 Test: turnos duplicados → `problemas`
- [ ] 🤖 Test: propuesta con `campos_faltantes` no vacío no llega a resolverse
- [ ] 🤖 Test: el resultado pasa `_validar_turnos` y `validar_publicacion_cambio_dia`
- [ ] 🤖 Implementar `app/services/asistente/resolver.py`:
      `resolver_propuesta(propuesta, usuario, hoy) -> (cedidos, aceptados, problemas)`
- [ ] 🤖 Diccionario de sinónimos de franjas en un módulo aparte, alimentado por
      `docs/vocabulario_corpus.md`
- [ ] 🤖 Ejecutar tests (`anaconda3/bin/python3 -m pytest --testmon`)
- [ ] 🤖 Commit

### 🚦 Puerta 3

- [ ] Un id de franja **nunca** puede llegar a la BD sin haber sido resuelto contra
      el grupo del usuario autenticado. Verificado por test.

---

## Fase 4 — Cliente de la API

- [ ] 🤖 Test: `extraer_propuesta` con cliente falso devuelve la propuesta parseada
- [ ] 🤖 Test: error de la API → excepción controlada del dominio, no una `anthropic.*`
      escapándose a la capa web
- [ ] 🤖 Test: timeout → excepción controlada
- [ ] 🤖 Implementar `app/services/asistente/cliente.py` con `client` inyectable
      (`client=None` → `anthropic.Anthropic()`)
- [ ] 🤖 Llamada: `client.messages.parse()`, modelo `claude-opus-5`,
      `thinking={"type": "adaptive"}`, `output_format=PropuestaPublicacion`
- [ ] 🤖 Implementar `_construir_prompt(contexto)`: franjas del grupo (nombre + horas),
      fecha de hoy con día de semana, tipos válidos, reglas, few-shot del dev set
- [ ] 🤖 Marcar el bloque `system` con `cache_control: {"type": "ephemeral"}`
      (es idéntico para todo el grupo → ~0,1× a partir de la 2ª llamada)
- [ ] 🤖 **No** meter hora ni nada variable en el prompt de sistema: invalidaría la caché
- [ ] 🤖 Confirmar que **ningún test de la suite hace una llamada real** a la API
- [ ] 🤖 Commit

---

## Fase 5 — Evaluación

- [ ] 🤖 `scripts/eval_parser.py`: corre un corpus y compara contra `esperado`
- [ ] 🤖 Métricas: **exact match** (conjunto normalizado de turnos idéntico) y desglose
      de fallos (tipo / fecha / franja / turno de más / turno de menos)
- [ ] 🤖 Métrica crítica aparte: **tasa de error silencioso** — propuestas completas,
      plausibles y equivocadas. Un "no lo entiendo" es barato; publicar el turno
      equivocado con confianza es caro.
- [ ] 🤖 Usar la Batch API (`/v1/messages/batches`) para las pasadas completas: 50% más
      barato, la latencia da igual
- [ ] 👤 **Fijar los umbrales AHORA, antes de ver ningún resultado.**
      Propuesta: ≥90% exact match y <2% error silencioso.
      → umbrales acordados: `_____ % exact match`, `_____ % error silencioso`
- [ ] 🤖 Primera pasada sobre el **dev set**
- [ ] 🤖/👤 Iterar el prompt contra el dev set hasta superar los umbrales
      (ajustar reglas, añadir/cambiar few-shot, precisar el manejo de rangos como
      "la semana que viene")
- [ ] 🤖 Pasada **única** sobre el test set

### 🚦 Puerta 5 — Decisión de sacar a producción

- [ ] Umbrales superados **en el test set** (no en el dev set)
- [ ] Si no se superan: ir a la **Fase 5B**. Ojo — cada vuelta al test set lo
      contamina un poco; si necesitas muchas, aparta un tercer conjunto virgen.

---

## Fase 5B — Si la precisión es insuficiente

No apliques palancas a ciegas. El error más caro aquí es cambiar el prompt por
intuición, ver que sube 2 puntos por ruido, y creer que has arreglado algo.
**Diagnostica antes de tocar nada.**

### 5B.1 — Diagnóstico (obligatorio antes de cualquier cambio)

- [ ] 🤖 Clasificar **todos** los fallos del dev set por tipo:
      tipo de publicación / fecha / franja / turno de más / turno de menos /
      error silencioso. Sacar un histograma.
- [ ] 🤖 Identificar el modo de fallo dominante. Normalmente el 60-80% de los
      errores son **un solo patrón**. Arreglar ese vale más que diez retoques sueltos.
- [ ] 🤖 Separar fallos **del modelo** de fallos **del resolvedor**: coger 20 fallos
      y mirar el JSON crudo. Si el JSON era correcto y `resolver_propuesta` lo
      estropeó, no es un problema de IA.
- [ ] 🤖 Arreglar primero todos los fallos del resolvedor: son Python determinista,
      se arreglan con un test, no cuestan tokens y no pueden regresionar.
- [ ] 👤 Revisar 30 fallos a mano y marcar cuáles son **anotación incorrecta** o
      **mensaje genuinamente ambiguo**. Un corpus real tiene ambos.

### 5B.2 — Medir el techo humano

Si dos personas no se ponen de acuerdo en cómo publicar un mensaje, no puedes
exigirle al modelo que acierte. Ese es tu techo real.

- [ ] 👤 Pedir a alguien del grupo que anote 30 mensajes del dev set a ciegas
- [ ] 👤 Medir el acuerdo con tu anotación
      → acuerdo humano-humano: `_____ %`
- [ ] 👤 Si el acuerdo humano está por debajo de tu umbral, **el umbral está mal**,
      no el parser. Ajústalo y anótalo en el registro de decisiones.

### 5B.3 — Palancas, en orden de coste creciente

Aplica **una cada vez** y vuelve a medir en el dev set. Si aplicas tres a la vez
no sabrás cuál funcionó.

- [ ] 🤖 **Regla explícita en el prompt** para el modo de fallo dominante
      ("la semana que viene" = lunes a domingo siguientes; los rangos no incluyen
      el día de hoy; etc.). Lo más barato y suele ser lo más efectivo.
- [ ] 🤖 **Few-shot dirigido**: añadir 3-5 ejemplos del dev set que sean exactamente
      del modo de fallo dominante. No añadir ejemplos genéricos "por si acaso":
      un prompt más largo con ejemplos irrelevantes empeora.
- [ ] 🤖 **Mover trabajo del modelo al resolvedor**. Si falla expandiendo rangos,
      deja de pedirle fechas expandidas: que devuelva `{"rango": "semana_siguiente"}`
      y expande tú en Python. Cada cosa que le quitas es superficie de error que
      desaparece. Esta suele ser la palanca más rentable.
- [ ] 🤖 **Preprocesado determinista** del texto antes de enviarlo: quitar emojis,
      normalizar espacios, recortar saludos y despedidas.
- [ ] 🤖 **Partir la tarea en dos llamadas**: primero clasificar el tipo, luego
      extraer los turnos con un prompt especializado por tipo. Duplica coste y
      latencia; úsalo solo si el diagnóstico dice que el tipo se confunde a menudo.
- [ ] 🤖 **Comprobar truncamiento**: si algunas respuestas se cortan, `max_tokens`
      se está quedando corto (recuerda que en Opus 5 el thinking y el texto comparten
      ese presupuesto). Subirlo es gratis salvo en tokens realmente usados.
- [ ] 🤖 **Probar otro modelo**. `claude-fable-5` si Opus 5 se queda corto en los
      mensajes difíciles. Nunca bajar de modelo para ahorrar sin medir antes.

### 5B.4 — Si el problema es el error silencioso

Este es el fallo grave: propuestas completas, plausibles y equivocadas. Aquí **no
persigas precisión, persigue abstención**. Que el parser diga "no lo entiendo"
es un resultado aceptable; que publique el turno equivocado con aplomo, no.

- [ ] 🤖 Endurecer las reglas del prompt hacia la abstención: ante cualquier duda,
      `campos_faltantes` en vez de adivinar
- [ ] 🤖 Añadir ejemplos few-shot de mensajes ambiguos **cuya respuesta correcta es
      abstenerse**. Sin estos, el modelo nunca aprende que abstenerse es una opción.
- [ ] 🤖 Añadir al esquema un campo de confianza por turno y descartar los bajos
      en el resolvedor
- [ ] 🤖 Aceptar bajar el exact match a cambio de bajar el error silencioso: es una
      mejora real aunque el número principal empeore

### 5B.5 — Reducir el alcance en vez de mejorar el modelo

Si tras las palancas baratas sigues lejos del umbral, casi siempre es mejor
**hacer menos, bien** que todo, regular.

- [ ] 🤖 Segmentar el eval: medir precisión por complejidad del mensaje
      (1 turno cedido / varios / rangos / condicionales)
- [ ] 🤖 Si los mensajes simples van muy bien y los complejos mal, **lanza solo los
      simples**: si el mensaje no encaja en el caso fácil, el parser se abstiene y
      manda al formulario normal. Cubrir el 70% del volumen con 95% de acierto es
      mucho mejor producto que el 100% con 75%.
- [ ] 🤖 **Prefill parcial**: si solo hay certeza sobre los turnos cedidos, rellenar
      solo esos y dejar el resto al usuario. Medio formulario correcto vale más que
      ninguno.
- [ ] 👤 Recortar tipos soportados: empezar solo por `cambio`, dejar
      `regalo`/`peticion`/`junte` para más adelante

### 5B.6 — Higiene de la iteración

- [ ] 🤖 Cada cambio se mide **en el dev set**, nunca en el test set
- [ ] 🤖 Guardar el resultado de cada iteración en la tabla de abajo: sin registro,
      a la quinta vuelta no recordarás qué probaste
- [ ] 🤖 Fijar la versión del prompt en el repo y versionarla, para poder volver atrás
- [ ] 👤 Si has tocado el test set más de 2-3 veces, apartar 100 mensajes vírgenes
      del corpus como conjunto final de validación

### 🚦 Puerta 5B — Cuándo parar de insistir

- [ ] Si tras **3 iteraciones** con las palancas de 5B.3 sigues lejos del umbral,
      el problema no es el prompt. Las opciones reales son: reducir alcance (5B.5),
      bajar el umbral con justificación (5B.2), o aceptar que el mensaje libre no
      es un buen input para este dominio y no lanzar.
- [ ] Registra la decisión abajo. No entres en un bucle indefinido de retoques.

### Registro de iteraciones del prompt

| # | Fecha | Cambio aplicado | Exact match (dev) | Error silencioso (dev) |
|---|-------|-----------------|-------------------|------------------------|
| 0 |       | baseline        |                   |                        |
| 1 |       |                 |                   |                        |
| 2 |       |                 |                   |                        |
| 3 |       |                 |                   |                        |

---

## Fase 6 — Ruta e interfaz

- [ ] 🤖 Test: `POST /asistente/parsear` requiere login
- [ ] 🤖 Test: propuesta válida → redirect al prefill de `/publicar` con los datos
- [ ] 🤖 Test: propuesta con `problemas` → formulario vacío + aviso al usuario
- [ ] 🤖 Test: fallo de la API → formulario vacío + aviso, sin error 500
- [ ] 🤖 Test: se respeta el rate limit por usuario
- [ ] 🤖 Implementar `app/routes/asistente.py` y registrar el blueprint
- [ ] 🤖 Reutilizar el mecanismo de prefill existente (ver `_leer_prefill_calendario()`
      en `app/routes/publicaciones.py`) — **no** crear una pantalla de confirmación nueva
- [ ] 🤖 Modal con `<textarea>` + botón en la vista de publicar
- [ ] 🤖 Spinner con texto honesto: la llamada tarda 3-8 s
- [ ] 🤖 **Todo el texto nuevo con `_()`** (regla i18n del proyecto, sin excepciones)
- [ ] 🤖 `pybabel extract` + `pybabel update` + traducir el `.po` + `pybabel compile`
- [ ] 🤖 Rate limit por usuario (propuesta: 20 parseos/día)
- [ ] 🤖 `try/except` global: cualquier fallo → formulario vacío. El asistente nunca
      puede impedir publicar.
- [ ] 🤖 Commit

---

## Fase 7 — Trazabilidad y despliegue

- [ ] 👤 Decidir si se guardan los parseos (texto original + propuesta generada).
      Recomendado durante las primeras semanas: cuando alguien diga "publicó mal mi
      cambio", vas a querer ver qué pegó y qué devolvió el modelo.
      → decisión: `_______________`
- [ ] 🤖 Si sí: modelo `ParseoAsistente` + migración **con `flask db migrate`**
      (nunca a mano), patrón de tres pasos si hay columnas `NOT NULL`
- [ ] 🤖 `flask db heads` → debe mostrar exactamente `1 (head)`
- [ ] 🤖 Si se guarda texto de usuarios: política de caducidad (p. ej. borrado a 30 días)
      + tarea de limpieza
- [ ] 👤 Actualizar la política de privacidad: se envía texto introducido por el usuario
      a un proveedor externo (Anthropic) para su procesamiento
- [ ] 🤖 Aviso visible en el modal de que el texto se procesa con IA
- [ ] 👤 Configurar `ANTHROPIC_API_KEY` en Railway
- [ ] 🤖 Abrir PR contra `staging`
- [ ] 👤 Probar en staging con 10 mensajes reales
- [ ] 👤 Merge y despliegue

---

## Fase 8 — Medir si sirvió de algo

Sin esto no sabrás si el trabajo valió la pena.

- [ ] 🤖 Evento de analytics: parseo iniciado / propuesta aceptada sin editar /
      propuesta editada antes de publicar / abandonada
- [ ] 👤 Baseline **antes** del lanzamiento: publicaciones diarias en tu unidad
      → baseline: `_____ pub/día`
- [ ] 👤 A las 2 semanas: comparar publicaciones diarias
      → resultado: `_____ pub/día`
- [ ] 👤 Revisar el % de propuestas editadas antes de publicar. Si es alto, el parser
      acierta poco en la práctica aunque el eval dijera lo contrario.
- [ ] 👤 Preguntar en el grupo a 5 personas que lo hayan usado

### 🚦 Puerta 8

- [ ] Si a las 2 semanas las publicaciones no han subido de forma apreciable, la
      hipótesis de fricción era falsa. Regístralo y no sigas invirtiendo aquí.

---

## Registro de decisiones

Anota aquí las decisiones que se tomen sobre la marcha, con fecha.

| Fecha | Decisión | Motivo |
|-------|----------|--------|
| 2026-08-16 | **Parser en pausa indefinida** | Puerta 0 no superada. El cuello de botella no es la fricción al publicar (71% de la unidad ya publicó alguna vez) sino la conversión: solo el 11% de las publicaciones acaba en cambio confirmado. Ver bloque de Puerta 0. |
| 2026-08-16 | Prioridad: arreglar la conversión de las cadenas | Las cadenas son el 83% de los rechazos y han producido 1 cambio cerrado en toda la vida de la app. Ver `docs/diagnostico_cadenas.md`. |

## Notas y hallazgos

-
