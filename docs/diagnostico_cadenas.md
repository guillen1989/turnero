# Diagnóstico: por qué no se cierran las cadenas

> Abierto el 2026-08-16 a raíz del análisis de producción que dejó el parser en pausa
> (ver `docs/plan_trabajo_parser.md`, bloque "Puerta 0 no superada").

## Resumen

Las cadenas de 3 y 4 son el diferencial de la app frente al WhatsApp y **son el
principal motivo de que la gente la abandone**: generan mucho ruido y casi ningún
cambio cerrado.

La buena noticia, tras hablar con los compañeros: el motor de matching **no está
roto**. Está proponiendo cadenas que son inválidas por dos razones concretas que
hoy no conoce. Las dos son modelables.

---

## Los datos (producción, 2026-08-16)

### Conversión de matches por tipo (global, histórico)

| Tipo | Rechazados | Propuestos | Confirmados | Conversión |
|---|---|---|---|---|
| **directo_2** | 33 | 5 | 10 + 3 parcial | **~22%** |
| cadena_3 | 86 | 3 | 0 (1 parcial) | **0%** |
| cadena_4 | 141 | 6 | 1 | **0,7%** |

Las cadenas son **229 de 275 rechazos (83%)** y han producido **un (1)** cambio
cerrado en toda la vida de la app.

### Embudo de publicaciones (unidad 5, 118 usuarios)

| Desenlace | N | % |
|---|---|---|
| caducada | 92 | 52% |
| abierta | 65 | 37% |
| **confirmada** | **20** | **11%** |

### Ruido generado (unidad 5, últimos 30 días)

| Notificación | Enviadas | Leídas | % lectura |
|---|---|---|---|
| nuevo_match | 881 | 368 | 42% |
| rechazo | 580 | 96 | **17%** |
| aviso_oportunidad_4 | 475 | 192 | 40% |
| aviso_oportunidad_3 | 74 | 40 | 54% |
| **Total aprox.** | **~2.010** | | |

≈17 notificaciones por persona/mes. Media de 30 `match_found` por usuario activo,
con 13 usuarios recibiendo 20 o más. La tasa de lectura del 17% en los avisos de
rechazo indica que la gente ya ha desconectado de las notificaciones.

### Curva de abandono (unidad 5, publicaciones/semana)

```
22 jun  57   ← lanzamiento (40 publicadores nuevos)
29 jun  46
06 jul  20
13 jul  10
20 jul  12
27 jul  15
03 ago   9
10 ago   7
```

Adopción inicial buena (**84 de 118 = 71% publicó al menos una vez**), retención mala.

---

## Causas identificadas

Origen: conversaciones con compañeros de la unidad (2026-08-16). No son hipótesis
de escritorio, son el motivo que da la propia gente que rechaza.

### Causa 1 — Publicaciones obsoletas (fantasmas)

Un usuario de la cadena **ya había conseguido su cambio por otra vía** (normalmente
el WhatsApp) pero no actualizó ni canceló su publicación en la app. La cadena se
propone contando con alguien que ya no está disponible, y muere.

**Por qué importa más de lo que parece:**
- Afecta a **todas** las unidades, **todo** el año, y también a los matches directos.
- El impacto crece con la longitud de la cadena: si cada publicación tiene una
  probabilidad *p* de estar obsoleta, una cadena de 4 necesita que **cuatro**
  publicaciones estén vigentes a la vez. Con p=25%, una cadena de 4 tiene ~32% de
  probabilidad de ser viable frente al ~56% de un directo. Esto solo explica ya
  buena parte de la diferencia entre `directo_2` y `cadena_4`.
- Hay un **bucle vicioso**: la gente resuelve en WhatsApp → no actualiza la app →
  las cadenas se rompen → la app parece inútil → más gente va al WhatsApp. Es el
  mismo bucle que hacía parecer que el problema era la fricción al publicar.

**Es el problema de mayor impacto y el más barato de atacar.**

### Causa 2 — Veteranos y sustitutos (verano, solo esta unidad)

En Urgencias La Paz Enfermería, **durante el verano**, la empresa no acepta cambios
entre personal veterano y sustitutos. Muchas cadenas de 3-4 mezclan ambos tipos y
por tanto no son viables aunque el motor las vea perfectas.

**Alcance (importante para no sobre-modelar):**
- Solo en verano. El resto del año todas las cadenas serían factibles.
- Solo en esta unidad. No aplica a los demás servicios.
- ⚠️ **A confirmar:** si la restricción es sobre *cualquier* cambio veterano↔sustituto,
  también invalida los `directo_2`, no solo las cadenas. Preguntar antes de implementar
  — cambia dónde va la comprobación.

---

## Preguntas abiertas

- [ ] 👤 ¿La restricción veterano/sustituto aplica también a cambios directos 1-a-1?
- [ ] 👤 ¿Qué define exactamente "veterano" vs "sustituto"? (tipo de contrato, antigüedad,
      ¿lo sabe el propio usuario sin ambigüedad?)
- [ ] 👤 ¿Fechas exactas del periodo de verano? ¿Las fija la empresa o son aproximadas?
- [ ] 👤 ¿Hay otras unidades con restricciones análogas que aún no conocemos?
- [ ] 👤 ¿Qué proporción de los rechazos atribuyen los compañeros a cada causa?
      (con 5-8 personas basta para tener una idea)
- [ ] 🤖 ¿Se puede cuantificar la causa 1 retroactivamente? Proxy posible: antigüedad
      de las publicaciones implicadas en cadenas rechazadas frente a las confirmadas.

---

## Plan de trabajo

### Fase A — Instrumentar (primero, es lo que falta para decidir bien)

Ahora mismo se diagnostica a ciegas: no se registra por qué se rechaza un match ni
si la gente abre la app.

- [ ] 🤖 **Capturar el motivo de rechazo.** Al rechazar un match, pedir motivo con
      opciones cerradas: *"ya conseguí el cambio"* / *"no me sirven esos turnos"* /
      *"no puedo cambiar con esa persona"* / *"otro"*. Campo nuevo en `match_cambio`
      o en `match_participacion` (migración con `flask db migrate`, nunca a mano).
- [ ] 🤖 **Acción automática:** si el motivo es "ya conseguí el cambio", cerrar la
      publicación del usuario en el acto. Convierte un rechazo en limpieza de datos.
      Es la mejora con mejor relación impacto/esfuerzo de todo el documento.
- [ ] 🤖 Registrar evento de sesión/visita (hoy `event` solo guarda acciones de dominio,
      así que "usuarios activos" no se puede medir).
- [ ] 🤖 Dejar 2 semanas de datos antes de sacar conclusiones sobre proporciones.

### Fase B — Frescura de las publicaciones (causa 1)

- [ ] 🤖 Botón **"ya lo he conseguido"** bien visible en la publicación y en la
      notificación de match. Un toque, sin pasar por el formulario de edición.
- [ ] 🤖 **Recordatorio de vigencia**: a los N días de una publicación abierta,
      preguntar *"¿sigue en pie?"* con dos botones. Sin respuesta tras M días → caduca.
      Fijar N y M con los datos de antigüedad de las publicaciones que sí se confirmaron.
- [ ] 🤖 Antes de proponer una cadena, **priorizar publicaciones recientes o
      confirmadas como vigentes** frente a las antiguas sin señal de vida.
- [ ] 👤 Decidir si la caducidad automática actual es demasiado larga
      → caducidad actual: `_____ días` → propuesta: `_____ días`
- [ ] 🤖 Medir después: % de publicaciones abiertas con más de N días sin actividad,
      antes y después.

### Fase C — Restricción veterano/sustituto (causa 2)

Ojo con sobre-ingenierizar: es una regla de **una** unidad durante **unos meses**.

- [ ] 👤 Contestar las preguntas abiertas de arriba antes de escribir código
- [ ] 🤖 Añadir `tipo_vinculacion` al usuario (o al vínculo `usuario_unidad`, que es
      donde vive la relación con la unidad y la categoría). Migración con el patrón
      de tres pasos si es `NOT NULL` — la tabla tiene filas en producción.
- [ ] 🤖 Regla de compatibilidad **activable por unidad**: reutilizar el mecanismo
      de `feature_flag_unidad` que ya existe, en vez de inventar uno nuevo.
- [ ] 🤖 Para la estacionalidad, empezar por lo simple: un interruptor que la
      supervisora activa en junio y desactiva en septiembre. Nada de calendarios ni
      rangos de fechas hasta que se demuestre que hace falta.
- [ ] 🤖 Tests: con la regla activa, un match que mezcla tipos no se propone; con la
      regla inactiva, sí. Cubrir cadena_3, cadena_4 y (según respuesta) directo_2.
- [ ] 🤖 Aplicar la comprobación en el motor de matching, no en la capa web
- [ ] 👤 Recoger el dato de tipo de vinculación de los 118 usuarios de la unidad
      (¿autodeclarado en el perfil? ¿lo carga la supervisora?)

### Fase D — Reducir el ruido

Aunque se arreglen las causas 1 y 2, ~2.000 notificaciones al mes en una unidad de
118 personas es insostenible y ya ha entrenado a la gente para ignorarlas.

- [ ] 🤖 Revisar si el aviso de `rechazo` (580 envíos, 17% de lectura) aporta algo.
      Probablemente sea el primero que hay que quitar o agrupar.
- [ ] 🤖 Agrupar propuestas: un resumen diario en lugar de una notificación por match
- [ ] 🤖 Techo de propuestas por usuario y día
- [ ] 🤖 No proponer cadenas por debajo de un umbral de calidad/viabilidad
- [ ] 👤 Decidir si las cadenas siguen anunciándose mientras las causas 1 y 2 no
      estén resueltas, o se silencian temporalmente

### 🚦 Puerta de salida

- [ ] Conversión de publicación → cambio confirmado en la unidad 5 por encima del **25%**
      de forma sostenida (baseline actual: **11%**)
- [ ] Conversión de cadenas por encima del **10%** (baseline actual: **0-0,7%**)
- [ ] Publicaciones semanales estables o al alza (baseline actual: 7/semana y bajando)

Alcanzado esto, reabrir `docs/plan_trabajo_parser.md`: con un embudo que funciona,
capturar lo que hoy se queda en el WhatsApp sí compensa.

---

## Registro de decisiones

| Fecha | Decisión | Motivo |
|-------|----------|--------|
| 2026-08-16 | Abrir este diagnóstico y priorizarlo sobre el parser | Las cadenas son el 83% de los rechazos y ~0% de conversión; son la causa principal del abandono |
| 2026-08-16 | Causas identificadas por conversación con compañeros, no por análisis de datos | Los datos mostraban el *qué*; el *porqué* lo dieron los usuarios |

## Notas y hallazgos

- El motor de matching parece correcto: propone cadenas válidas según su modelo. El
  problema es que su modelo desconoce (a) si una publicación sigue vigente y (b) las
  restricciones de compatibilidad entre personas.
- La causa 1 y el "problema del WhatsApp" son el mismo bucle visto desde dos lados.
- Dato a favor de seguir invirtiendo: `directo_2` convierte al 22% y el 71% de la
  unidad llegó a publicar. El producto funciona cuando propone algo viable.
