# Análisis: implementación del parser de mensajes (Opción 1 del asistente de IA)

## Lo primero: no se "entrena", y eso cambia la estrategia

No hay fine-tuning aquí. Los mensajes no entrenan nada — sirven para tres cosas distintas, y conviene separarlas desde el principio:

1. **Descubrir el vocabulario real** del grupo: cómo llama la gente a las franjas ("mañanita", "la larga", "noche de finde"), cómo escribe las fechas, qué abreviaturas usa. Esto lo lees tú y lo metes en el prompt de sistema.
2. **Few-shot examples**: 8-15 mensajes con su salida correcta, incrustados en el prompt. Esto es lo que más sube la precisión en tareas de extracción.
3. **Eval set**: mensajes anotados con la publicación correcta, que usas para *medir*. Aquí sí, cuantos más mejor.

**Sí, mete muchos más de 60.** 300-500 es mejor que 60 sin discusión. Pero el cuello de botella no es recolectarlos, es **anotarlos**: un corpus sin la respuesta correcta anotada no mide nada. Anotar 400 mensajes a mano es un fin de semana perdido.

El atajo que funciona: escribe el parser v0 con 20 mensajes anotados a mano, córrelo sobre los 400, y **corrige** las salidas en vez de anotarlas desde cero. Corregir es 5-10× más rápido. Ojo con el sesgo: al revisar tiendes a aprobar lo que el modelo dijo. Revisa con mentalidad de auditor, mensaje contra propuesta, sin mirar si el modelo tenía "buena pinta".

Y **divide el corpus en dos desde el minuto uno**:
- **dev set** (~60): lo miras todo lo que quieras, de aquí salen los few-shot examples y aquí iteras el prompt.
- **test set** (el resto, 200-400): **no lo miras** hasta que creas que has terminado. Si iteras el prompt mirando el test set, acabas con un prompt sobreajustado a esos ejemplos concretos y una precisión medida que es mentira.

Un few-shot example nunca sale del test set.

### Aviso serio antes de tocar nada

Esos mensajes los escribieron tus compañeros, hablan de sus turnos, y llevan nombres reales. Sanitarios, datos identificables, España → RGPD. Antes de que un solo mensaje entre en el repo o en un prompt:

- **anonimiza**: sustituye nombres por `[NOMBRE1]`, `[NOMBRE2]`. Escribe un script, no lo hagas a ojo.
- **no commitees el corpus crudo**. Ni siquiera anonimizado, si tienes dudas: `tests/fixtures/mensajes_whatsapp/` en `.gitignore` y un puñado de ejemplos sintéticos escritos por ti para los tests que sí van al repo.
- el parser debe funcionar con nombres anonimizados, porque en producción el texto llegará con nombres reales y no quieres que el prompt dependa de conocer a nadie.

Es tu decisión hasta dónde llevar esto, pero anonimizar es barato y no hacerlo es un problema difícil de deshacer.

---

## Implementación, paso a paso

La clave del orden: **la mitad del trabajo no necesita la API en absoluto** y es 100% testeable offline. Haz esa mitad primero.

### Paso 0 — worktree
```bash
rtk git worktree add ../turnero-asistente -b feat/asistente-parser staging
```

### Paso 1 — corpus anonimizado
Formato JSONL, un mensaje por línea:
```json
{"id": "w001", "texto": "cambio mi noche del 14 por cualquier mañana la semana que viene", "esperado": {"tipo": "cambio", "cedidos": [["2026-08-14", "Noche"]], "aceptados": [["2026-08-17", null], ["2026-08-18", null]]}}
```
Sin código todavía. Solo recolectar, anonimizar y anotar 20 a mano.

### Paso 2 — el contrato (TDD, sin API)
`app/services/asistente/schema.py` con los modelos Pydantic (`PropuestaPublicacion`, `TurnoPropuesto`, `campos_faltantes`). Tests: que valide lo válido y rechace lo inválido.

### Paso 3 — el resolvedor (TDD, sin API) ← **aquí está el trabajo real**
`app/services/asistente/resolver.py`:

```python
def resolver_propuesta(propuesta, usuario, hoy):
    """Convierte una PropuestaPublicacion en los argumentos de publicar_cambio.
    Devuelve (turnos_cedidos, turnos_aceptados, problemas)."""
```

Responsabilidades:
- nombre de franja → `franja_horaria_id`, buscando **solo** entre las `FranjaHoraria` del `grupo_intercambio` del usuario. Normaliza (minúsculas, sin tildes), acepta sinónimos de un diccionario que tú controlas, y si no casa → `problemas`.
- fechas relativas → fechas absolutas contra `hoy` y la planilla del usuario.
- rechaza cualquier cosa fuera del vocabulario. **Nunca confíes en un id que venga del modelo.**

Esto se testea con pytest normal, sin red, sin coste, determinista. Es donde van la mayoría de tus tests.

### Paso 4 — el cliente (TDD con doble)
`app/services/asistente/cliente.py`, con la llamada real inyectable:

```python
def extraer_propuesta(texto, contexto, client=None):
    client = client or anthropic.Anthropic()
    resp = client.messages.parse(
        model="claude-opus-5",
        max_tokens=2000,
        thinking={"type": "adaptive"},
        system=[{"type": "text", "text": _prompt(contexto),
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": texto}],
        output_format=PropuestaPublicacion,
    )
    return resp.parsed_output
```

En los tests unitarios pasas un doble. **Ningún test de la suite llama a la API**: sería lento, caro y no determinista, y `--testmon` lo dispararía en cada cambio.

### Paso 5 — el eval (script aparte, no en la suite)
`scripts/eval_parser.py`. Corre el corpus, compara contra `esperado`, y reporta:

- **exact match**: ¿el conjunto normalizado de turnos coincide entero?
- desglose de fallos: tipo incorrecto / fecha incorrecta / franja incorrecta / turno de más / turno de menos.
- y por separado, la métrica que de verdad importa: **tasa de error silencioso** — propuestas que salen completas y plausibles pero están mal. Un mensaje que el parser marca como "no lo entiendo" es barato; uno que publica el turno equivocado con confianza es caro.

Para pasar 400 mensajes, usa la **Batch API** (`/v1/messages/batches`): 50% más barato y te da igual esperar. Una ronda completa de eval te sale por céntimos.

Fija un umbral antes de empezar a mirar los números — p. ej. "≥90% exact match y <2% de error silencioso en el test set, o no sale a producción".

### Paso 6 — ruta y UI
Modal para pegar el texto → POST → `extraer_propuesta` → `resolver_propuesta` → si hay `problemas`, los muestras y mandas al formulario vacío; si no, prefill de `/publicar` reutilizando el mecanismo de `_leer_prefill_calendario()`. El usuario confirma en el formulario de siempre. `publicar_cambio` sigue siendo el único camino de escritura.

Todo el texto nuevo de UI con `_()`, como siempre.

### Paso 7 — límites
Rate limit por usuario (p. ej. 20 parseos/día), timeout, y un `try/except` que ante cualquier fallo mande al formulario vacío en vez de romper. El asistente nunca debe ser un punto de fallo para publicar.

---

## El orden que te ahorra tiempo

Pasos 1-3 primero, completos. Cuando el resolvedor esté sólido, el paso 4 son 50 líneas y el prompt lo iteras contra el eval en tardes sueltas. Si empiezas por la llamada a la API acabarás peleándote con el prompt para arreglar cosas que en realidad tenía que arreglar el resolvedor.

Empieza por recolectar y anonimizar el corpus — es lo único que no puedo hacer yo y bloquea todo lo demás.
