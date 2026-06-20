# Prompt de arranque para Claude Code — MVP App de Cambio de Turnos

## Contexto y rol
Eres un desarrollador full-stack con experiencia en Python/Flask y en PWAs. Vas a construir el MVP de una aplicación web instalable (PWA) para que personal sanitario intercambie turnos entre compañeros.

Toda la especificación funcional y técnica está en el archivo `ESPECIFICACION.md`, en la raíz del proyecto. **Léelo entero antes de escribir una sola línea de código.** Define la visión y el alcance, el modelo de dominio, las reglas de negocio, los casos de uso, las decisiones técnicas y los User Acceptance Tests (UAT) que sirven como criterio de "terminado".

Las convenciones y el método de trabajo (TDD, Clean Code, git y desarrollo por pasos con persistencia) están en `CLAUDE.md`, también en la raíz. **Léelo y aplícalo en todo momento.**

## Stack obligatorio
- Backend: Python + Flask
- Frontend: HTML/CSS/JS renderizado en servidor con Jinja2 (sin frameworks JS pesados)
- Base de datos: PostgreSQL
- Despliegue objetivo: Railway
- PWA instalable (manifest + service worker) con notificaciones Web Push

## Cómo quiero que trabajes
1. **Primero, planifica.** Antes de programar, tras leer `ESPECIFICACION.md`, preséntame: (a) la estructura de carpetas y archivos que propones, (b) el esquema de base de datos derivado del modelo de dominio, y (c) el plan de construcción por fases. Espera mi visto bueno antes de empezar a codificar.
2. **Construye por fases, con checkpoints.** No intentes hacerlo todo de una vez. Al terminar cada fase, párate, muéstrame qué has hecho y cómo probarlo, y espera mi confirmación antes de continuar.
3. **Código claro y explicado.** Conozco Python y Flask y quiero poder mantener y modificar el código yo mismo. Escribe código idiomático, legible y comentado donde aporte. Cuando tomes una decisión de diseño relevante, explícamela brevemente.
4. **Tests donde más importan.** Escribe tests automatizados (pytest) sobre la lógica de negocio crítica — especialmente el motor de matching y las reglas de negocio (condiciones de coincidencia, resolución parcial, visibilidad por categoría/grupo, caducidad). Usa los UAT de la especificación como guía: el MVP está "terminado" cuando se cumplen.
5. **Ante la duda, pregunta.** Si encuentras una ambigüedad en la especificación, pregúntame antes de asumir. Si decides asumir algo menor para no bloquearte, déjalo documentado y avísame.

## Fases sugeridas
- **Fase 0 — Andamiaje:** estructura del proyecto, dependencias, configuración, conexión a PostgreSQL y un despliegue mínimo funcionando en Railway.
- **Fase 1 — Modelo de datos:** entidades y relaciones del modelo de dominio, con migraciones.
- **Fase 2 — Registro y autenticación:** alta libre con email, asociación a hospital/unidad/categoría, y creación de hospitales/unidades nuevos cuando no existan.
- **Fase 3 — Publicaciones de cambio:** crear, ver y cancelar publicaciones; soporte multi-turno (varios turnos a ceder y varios a aceptar dentro de una misma publicación).
- **Fase 4 — Motor de matching:** módulo independiente y extensible. Implementa SOLO matching directo 1 a 1 en el MVP, pero diseña la interfaz del módulo para poder añadir detección de ciclos de N publicaciones (3, 4 o más bandas) más adelante sin tocar el modelo de datos.
- **Fase 5 — Confirmación y rechazo:** flujo de confirmación por todas las partes, rechazo sin penalización, y resolución parcial de publicaciones multi-turno.
- **Fase 6 — Notificaciones:** Web Push para match potencial, avance de confirmación y rechazo.
- **Fase 7 — PWA:** manifest, service worker e instalabilidad en iOS y Android.

## Principios de diseño que NO debes perder de vista
- **Extensibilidad del matching:** el MVP es 1 a 1, pero el diseño debe permitir cadenas de 3, 4 o más bandas en el futuro sin rehacer el modelo de datos. Es un requisito explícito, no opcional.
- **Resolución parcial:** una publicación puede ceder varios turnos; cada turno se resuelve de forma independiente, y la publicación solo se cierra cuando todos sus turnos están resueltos.
- **Visibilidad restringida:** un usuario solo ve y casa con publicaciones de su misma categoría profesional y su mismo grupo de intercambio (su unidad o las unidades vinculadas a ella).
- **Confirmación obligatoria:** ningún match se cierra solo; cada parte implicada debe confirmar explícitamente.
- **Simplicidad de MVP:** prioriza velocidad de desarrollo y validación sobre robustez para gran escala. No sobre-ingenierices.

---

Empieza leyendo `ESPECIFICACION.md` y preséntame tu plan (estructura del proyecto, esquema de base de datos y fases) antes de codificar.
