# Plan de trabajo — Recogida del motivo de rechazo

> Fase A de `docs/diagnostico_cadenas.md`. Es el primer paso del plan de remediación:
> sin este dato se sigue diagnosticando a ciegas.

## Objetivo

Que cada rechazo de un match deje constancia de **por qué**, para saber en qué
proporción las cadenas mueren por publicaciones obsoletas, por restricciones de
compatibilidad o por matches simplemente malos.

## Por qué esto primero

Hoy `estado='rechazado'` no distingue nada. Peor: `rechazar_match()` se llama desde
**cuatro sitios** y solo uno es un rechazo humano:

| Origen | Llamada | ¿Es rechazo del usuario? |
|---|---|---|
| `app/routes/matches.py:82` | el usuario pulsa rechazar | **Sí** |
| `app/services/publicaciones.py:107` | cascada al cancelar/editar/eliminar publicación | No |
| `app/services/registro.py:367` | flujo de registro/planilla | No |

⚠️ **Consecuencia:** las estadísticas actuales de rechazo están contaminadas. Los 275
rechazos globales mezclan decisiones humanas con cascadas del sistema. Distinguirlos
es parte de este trabajo y probablemente cambie la lectura del diagnóstico.

---

## Los motivos

| Motivo | Código | Qué produce |
|---|---|---|
| **"Ya he conseguido este cambio por otro sitio"** | `ya_conseguido_propio` | **Acción**: cierra su propia publicación en el acto |
| **"Otro de la cadena ya consiguió su cambio"** | `ya_conseguido_otro` | **Diagnóstico**: mide el peso de las publicaciones fantasma |
| "No me sirven esos turnos" | `turnos_no_sirven` | Diagnóstico: calidad del match |
| "No puedo cambiar con esa persona" | `incompatible_persona` | Diagnóstico: detecta la causa 2 (veterano/sustituto) |
| "Otro" + texto libre opcional | `otro` | Cajón de sastre; revisar periódicamente |

### Decisión: no se pregunta *quién*

Decidido el 2026-08-16. El motivo `ya_conseguido_otro` **no** pide identificar a la
persona señalada.

**Lo que se gana:** ninguna dinámica de señalar compañeros. En una unidad de 118
personas que trabajan juntas, un mecanismo de reportes entre pares es una fuente de
roces que no compensa. Además el flujo de rechazo queda en un solo toque.

**Lo que se pierde:** el motivo deja de ser accionable. No se puede limpiar la
publicación fantasma concreta, porque no se sabe cuál es. Queda como **señal
agregada**: si este motivo resulta ser mayoritario, confirma que el problema de
frescura de datos es el dominante y justifica invertir en la Fase B del diagnóstico
(recordatorios de vigencia para todo el mundo, sin señalar a nadie).

Es un intercambio consciente: menos calidad de dato a cambio de cero coste social.

> **Alternativa descartada por ahora** (queda anotada por si cambia la decisión):
> disparar la pregunta de vigencia a **todos** los participantes de esa cadena
> excepto quien rechaza. Mantiene el anonimato completo — nadie señala a nadie — y
> sigue siendo accionable. El coste es más notificaciones en una unidad ya saturada
> (~2.000/mes hoy). Si tras la Fase 5 este motivo domina, merece la pena reconsiderarlo.
> - [ ] 👤 Reconsiderar tras ver los datos de la Fase 5

---

## Decisiones de diseño

### 1. Ningún motivo actúa sobre la publicación de un tercero

Sin pregunta de "quién", esto es automático: la única acción sobre datos es cerrar
la publicación **del propio usuario** que declara haber conseguido el cambio ya.

### 2. Distinguir rechazo humano de cascada del sistema

`rechazar_match()` gana parámetros con valor por defecto, de modo que las tres
llamadas automáticas siguen funcionando sin cambios pero quedan registradas como
`rechazo_origen='automatico'`.

### 3. El motivo es obligatorio para el rechazo humano

Si es opcional, la mayoría lo saltará y el dato no servirá. Un solo toque, cinco
opciones, sin pasos adicionales.

---

## Modelo de datos

`MatchParticipacion` es una fila por publicación implicada en el match, con
restricción única `(match_id, publicacion_id)`. Ahí es donde vive el rechazo de una
persona concreta sobre un match concreto.

Nota: `MatchParticipacion` **no tiene `usuario_id`**; el usuario se alcanza vía
`publicacion.usuario_id`. No añadir columna redundante.

Columnas nuevas, **todas nullable** (migración de un solo paso, segura con filas en
producción — no aplica el patrón de tres pasos):

| Columna | Tipo | Uso |
|---|---|---|
| `motivo_rechazo` | `String(40)`, nullable | código cerrado del motivo |
| `motivo_detalle` | `String(200)`, nullable | texto libre, solo para "otro" |
| `rechazo_origen` | `String(20)`, nullable | `usuario` / `automatico` |
| `fecha_rechazo` | `DateTime`, nullable | cuándo |

Constantes de motivo en el módulo del modelo, junto a las que ya existen:

```python
MOTIVOS_RECHAZO = (
    "ya_conseguido_propio",
    "ya_conseguido_otro",
    "turnos_no_sirven",
    "incompatible_persona",
    "otro",
)
```

---

## Plan de trabajo

### Fase 1 — Modelo y migración

- [ ] 🤖 Añadir las cuatro columnas y `MOTIVOS_RECHAZO` a `app/models/match.py`
- [ ] 🤖 `flask db migrate -m "motivo de rechazo en match_participacion"`
      (**nunca escribir el archivo a mano**)
- [ ] 🤖 Revisar el `upgrade()` generado: todas nullable, sin `NOT NULL`
- [ ] 🤖 `flask db heads` → debe devolver exactamente `1 (head)`
- [ ] 🤖 Commit

### Fase 2 — Servicio (TDD)

- [ ] 🤖 Test: `rechazar_match(match, uid)` sin motivo → `rechazo_origen='automatico'`
      (las 3 llamadas existentes siguen funcionando sin tocarlas)
- [ ] 🤖 Test: con motivo → se guarda motivo, origen `usuario` y `fecha_rechazo`
- [ ] 🤖 Test: motivo fuera de `MOTIVOS_RECHAZO` → error
- [ ] 🤖 Test: motivo `ya_conseguido_propio` → la publicación **del que rechaza**
      pasa a cerrada
- [ ] 🤖 Test: motivo `ya_conseguido_otro` → se registra el motivo y **no** se toca
      ninguna publicación
- [ ] 🤖 Test: `motivo_detalle` solo se guarda con el motivo `otro`
- [ ] 🤖 Ampliar `rechazar_match(match, usuario_id, motivo=None, detalle=None)`
- [ ] 🤖 Verificar que sigue **sin commitear internamente** (ver commit 393c3db: hacerlo
      provocaba `ObjectDeletedError`)
- [ ] 🤖 Commit

### Fase 3 — Interfaz

- [ ] 🤖 Test: rechazar sin elegir motivo → no se procesa
- [ ] 🤖 Test: `otro` → aparece el campo de texto libre
- [ ] 🤖 Test: `ya_conseguido_propio` → tras rechazar, su publicación aparece cerrada
- [ ] 🤖 Modal de rechazo con los 5 motivos, en la vista de match
- [ ] 🤖 **Todos los textos con `_()`** — motivos, avisos, botones
- [ ] 🤖 `pybabel extract` → `update` → traducir `.po` → `compile`
- [ ] 👤 Revisar la redacción de los 5 motivos: deben ser inequívocos para alguien
      que los lee con prisa en el móvil, a mitad de turno
- [ ] 🤖 Commit

### Fase 4 — Medir

- [ ] 🤖 Añadir el desglose de motivos al panel `/analytics`
- [ ] 👤 Esperar **2 semanas** de datos antes de sacar conclusiones sobre proporciones
- [ ] 👤 Anotar el reparto de motivos:
      → `ya_conseguido_propio: ___%` · `ya_conseguido_otro: ___%` ·
      `turnos_no_sirven: ___%` · `incompatible_persona: ___%` · `otro: ___%`
- [ ] 👤 Recalcular la conversión de cadenas **excluyendo** los rechazos automáticos,
      que hasta ahora contaminaban la cifra

**Cómo leer el resultado:**

| Si domina… | Significa | Siguiente inversión |
|---|---|---|
| `ya_conseguido_*` (los dos juntos) | Frescura de datos | Fase B del diagnóstico: recordatorios de vigencia |
| `incompatible_persona` | Restricciones no modeladas | Fase C del diagnóstico: veterano/sustituto |
| `turnos_no_sirven` | El motor propone mal | Revisar el algoritmo de matching |
| `otro` | Los motivos están mal planteados | Leer los textos libres y rehacer la lista |

### 🚦 Puerta de salida

- [ ] Se conoce el reparto real de motivos sobre ≥50 rechazos humanos
- [ ] Los rechazos automáticos ya no contaminan las métricas
- [ ] Decidido, con datos, si la siguiente inversión es la Fase B (frescura) o la
      Fase C (compatibilidad) del diagnóstico

---

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Un paso más al rechazar aumenta la fricción | Un solo toque, sin pasos condicionales salvo el texto libre de "otro" |
| `ya_conseguido_otro` no permite limpiar nada | Aceptado: es señal agregada. Si domina, se ataca con vigencia general (Fase B) |
| La gente elige el primer motivo por inercia | Ordenar los motivos por frecuencia esperada; revisar en la Fase 4 si hay sesgo hacia el primero |

## Registro de decisiones

| Fecha | Decisión | Motivo |
|-------|----------|--------|
| 2026-08-16 | Incluir el motivo "otro usuario ya consiguió el cambio" | Captura información que el sistema no puede obtener de otra forma: quien abandona su publicación no vuelve a actualizarla |
| 2026-08-16 | **No preguntar quién** en ese motivo | Evita la dinámica de señalar compañeros en una unidad de 118 personas que trabajan juntas. Se acepta perder capacidad de acción a cambio de cero coste social |
| 2026-08-16 | Distinguir `rechazo_origen` usuario/automático | `rechazar_match()` se llama desde 4 sitios y 3 son cascadas del sistema; las métricas actuales están contaminadas |
