# CLAUDE.md — Convenciones y método de trabajo

> Este archivo define **cómo** se desarrolla este proyecto. El **qué** (requisitos, modelo de dominio, reglas de negocio, casos de uso y UAT) está en `ESPECIFICACION.md`. Consulta siempre `ESPECIFICACION.md` antes de implementar cualquier funcionalidad.

## El proyecto en una frase
PWA (web app instalable) para que personal sanitario intercambie turnos entre compañeros de su misma categoría y unidad. Detalle completo en `ESPECIFICACION.md`.

## Stack
- Backend: Python + Flask
- Frontend: HTML/CSS/JS con Jinja2 (sin frameworks JS pesados)
- Base de datos: PostgreSQL
- Despliegue: Railway
- PWA: manifest + service worker + Web Push

## Internacionalización (i18n) — OBLIGATORIO desde el primer commit
El MVP se construye solo en español, pero la app debe diseñarse desde el principio para soportar varios idiomas sin refactor posterior, ya que está planeada su escalabilidad a otros países (ver `ESPECIFICACION.md`).

**Mecanismo:** [Flask-Babel](https://python-babel.github.io/flask-babel/), el estándar de facto para i18n en Flask, basado en el sistema `gettext`.
- Los textos se marcan en el código con `gettext()` (o su alias `_()`) y en las plantillas Jinja con `{{ _('texto') }}`.
- Las traducciones se extraen a un catálogo (`pybabel extract`), se inicializan por idioma (`pybabel init -l <idioma>`) y se compilan (`pybabel compile`) generando los archivos `.po` (editables) y `.mo` (compilados) por idioma, en una carpeta `translations/` en la raíz del proyecto.
- Flask-Babel se inicializa una vez en la app (`Babel(app)`) y resuelve automáticamente el idioma activo según la función `locale_selector` que se configure.

**Reglas:**
- **Ningún texto de interfaz se escribe directamente en las plantillas o en el código Python sin pasar por `gettext`/`_()`.** Todo texto visible para el usuario (botones, mensajes, etiquetas, notificaciones push) se marca para traducción desde el primer commit, aunque el MVP solo tenga el catálogo en español completo. Añadir un idioma nuevo después debe ser solo generar y traducir un nuevo catálogo `.po`, nunca tocar plantillas ni lógica.
- El idioma activo (`locale`) se determina por usuario (guardado en su perfil), no solo por sesión o cabecera del navegador, ya que personas de distintos países convivirán en la misma instancia de la app.
- Dependencia a añadir: `Flask-Babel` (vía pip).

---

## Método de trabajo (OBLIGATORIO)

### 1. Test-Driven Development (TDD)
Todo el código de producción se escribe siguiendo el ciclo **rojo-verde-refactor**:
1. **Rojo:** escribe primero un test que describa el comportamiento deseado y que falle.
2. **Verde:** escribe el código mínimo necesario para que el test pase.
3. **Refactor:** mejora el código manteniendo todos los tests en verde.

Reglas:
- No se escribe código de producción sin un test que lo justifique.
- Framework de tests: pytest.
- Prioriza los tests sobre la lógica de negocio crítica: el motor de matching y las reglas de negocio (condiciones de coincidencia, resolución parcial, visibilidad por categoría/grupo, confirmación, caducidad).
- Los UAT de `ESPECIFICACION.md` son el criterio de aceptación de cada funcionalidad.

### 2. Clean Code
- Nombres descriptivos y honestos para variables, funciones y clases.
- Funciones pequeñas que hacen una sola cosa.
- Evita la duplicación (DRY).
- Separa responsabilidades con claridad (p. ej., el motor de matching es un módulo aislado, sin acoplarse a la capa web ni a la de persistencia).
- Comenta el "por qué", no el "qué"; el código debe explicarse por sí mismo.
- Nada de código muerto ni de soluciones más complejas de lo que el MVP necesita.

### 3. Control de versiones con Git
- Todo el desarrollo se versiona con git desde el primer paso.
- Commits atómicos: un commit por paso completado (ver sección 4).
- Mensajes de commit claros, en presente y con prefijo de tipo. Ejemplos:
  - `feat: añade publicación de cambio multi-turno`
  - `test: cubre la condición de match directo 1 a 1`
  - `refactor: extrae el motor de matching a su propio módulo`
  - `chore: configura la conexión a PostgreSQL`

### 4. Desarrollo por pasos con persistencia (CRÍTICO)
El desarrollo se estructura en **pasos pequeños**, cada uno terminado en un commit. Esto permite reanudar el trabajo **sin pérdidas** si el ordenador se apaga o se agotan los tokens a mitad.

Un "paso" es una unidad de trabajo pequeña y coherente (idealmente: un test + su implementación + refactor). Cada paso sigue SIEMPRE este ciclo:
1. Trabaja el paso con TDD (rojo → verde → refactor).
2. Asegúrate de que **todos** los tests pasan.
3. Actualiza `PROGRESS.md`: marca el paso como completado y registra cuál es el siguiente paso.
4. Haz **un único commit** que incluya el código, los tests y el `PROGRESS.md` actualizado.

El **primer paso** del proyecto debe incluir inicializar el repositorio git y crear el `PROGRESS.md` inicial.

Mantén los pasos suficientemente pequeños como para que cada uno quepa con holgura en una sesión. Es preferible muchos commits pequeños que pocos grandes: cuanto más frecuente sea el commit, menos trabajo se pierde ante una interrupción.

---

## Seguimiento del progreso: `PROGRESS.md`
Mantén en la raíz un archivo `PROGRESS.md` que sea la **fuente de verdad** del estado del desarrollo. Debe contener, como mínimo:
- La fase y el paso actuales.
- La lista de pasos ya completados (checklist).
- El siguiente paso concreto a abordar.
- Notas pendientes: decisiones tomadas, asunciones hechas, dudas a consultar.

Como el `PROGRESS.md` se actualiza dentro del commit de cada paso, el último commit siempre refleja el estado real del proyecto.

Estructura orientativa de `PROGRESS.md`:
```
# Estado del desarrollo

## Fase actual
Fase X — <nombre>

## Paso actual / siguiente paso
<descripción del próximo paso concreto>

## Pasos completados
- [x] Fase 0, paso 1: ...
- [x] Fase 0, paso 2: ...
- [ ] Fase 1, paso 1: ...

## Notas / decisiones / asunciones pendientes
- ...
```

---

## Cómo reanudar el trabajo (al empezar cada sesión)
1. Lee este `CLAUDE.md`.
2. Lee `PROGRESS.md` para saber en qué paso se quedó el desarrollo y cuál es el siguiente.
3. Revisa `git log` para ver los últimos commits y `git status` para ver si hay cambios sin confirmar.
   - Si el árbol de trabajo está limpio: continúa con el siguiente paso indicado en `PROGRESS.md`.
   - Si hay cambios sin confirmar (interrupción a mitad de un paso): ejecuta los tests para entender el estado, decide si completar o descartar esos cambios, y deja el repositorio en un estado consistente antes de seguir.
4. Continúa desde ahí, sin rehacer trabajo ya hecho.

---

## Migraciones de base de datos — OBLIGATORIO

La app tiene datos reales en producción. Una migración mal escrita crashea el deploy para todos los usuarios.

**Regla:** siempre que añadas una columna `NOT NULL` a una tabla que puede tener filas en producción, usa el patrón de tres pasos. Alembic genera el código incorrecto por defecto — corrígelo manualmente antes de hacer commit:

```python
# ✗ MAL — falla en producción si hay filas existentes
batch_op.add_column(sa.Column('tipo', sa.String(20), nullable=False))

# ✓ BIEN — tres pasos
# 1. Añadir como nullable
batch_op.add_column(sa.Column('tipo', sa.String(20), nullable=True))
# 2. Rellenar filas existentes con el valor por defecto lógico
op.execute("UPDATE tabla SET tipo = 'valor_default' WHERE tipo IS NULL")
# 3. Convertir a NOT NULL
batch_op.alter_column('tipo', nullable=False)
```

Esto aplica a cualquier columna nueva con `NOT NULL` y sin `server_default`. Si la tabla está vacía en producción (nueva en este deploy), el patrón de un solo paso es seguro.

### Crear migraciones — OBLIGATORIO

**Nunca crear el archivo de migración a mano desde cero.** Alembic escribe el `down_revision` correcto automáticamente; si lo escribes a mano te arriesgas a apuntar a un nodo que no es el head actual, lo que genera múltiples cabezas y crashea el deploy.

Flujo correcto:

```bash
# 1. Modifica el modelo en app/models.py
# 2. Genera el esqueleto (Alembic detecta el head actual y lo pone en down_revision)
flask db migrate -m "descripción breve"
# 3. Revisa y edita el cuerpo de upgrade()/downgrade() si hace falta
#    (p. ej. aplicar el patrón de tres pasos para columnas NOT NULL)
# 4. Verifica que la cadena sigue siendo lineal
flask db heads   # debe mostrar exactamente 1 head
```

Si por cualquier razón creas el archivo manualmente, ejecuta `flask db heads` antes de hacer commit y asegúrate de que el resultado es exactamente `1 (head)`. El hook de pre-commit lo comprobará automáticamente si hay archivos de migración en el staging area, y el hook de pre-push lo comprobará siempre.

---

## Principios de diseño irrenunciables
(Detalle completo en `ESPECIFICACION.md`; aquí, como recordatorio permanente:)
- **Extensibilidad del matching:** el MVP resuelve solo coincidencias 1 a 1, pero el modelo de datos y la interfaz del motor de matching deben permitir cadenas de 3, 4 o más bandas en el futuro sin rediseño.
- **Resolución parcial:** una publicación puede ceder varios turnos; cada uno se resuelve por separado y la publicación solo se cierra cuando todos están resueltos.
- **Visibilidad restringida:** un usuario solo ve y casa con publicaciones de su misma categoría profesional y su mismo grupo de intercambio.
- **Confirmación obligatoria:** ningún match se cierra automáticamente; todas las partes deben confirmar.
- **Simplicidad de MVP:** prioriza velocidad y validación sobre robustez a gran escala. No sobre-ingenierices.
