# Plan: supervisoras multi-unidad + creación por admin con invitación por email

> Documento de trabajo para una sesión de implementación aparte. Sigue el método TDD y de commits atómicos de `CLAUDE.md`. Cada paso de este plan = un commit (rojo→verde→refactor + `PROGRESS.md`).

## Contexto (decisiones ya tomadas, no hace falta redebatir)

**Problema 1 — una supervisora solo puede gestionar su propia unidad.**
Hoy `Usuario.es_supervisora` es un booleano y todas las rutas de `app/routes/planilla_supervision.py` usan directamente `current_user.unidad` (la unidad "hogar" del usuario, la misma que usa para su propio calendario/matching). No existe ningún concepto de "unidades que superviso" distinto de "mi unidad".

**Decisión:** añadir una tabla de relación N:M `unidad_supervisada` (`usuario_id`, `unidad_id`), independiente de `Usuario.unidad_id`. `Usuario.unidad_id`/`categoria_id` siguen siendo obligatorios y representan la unidad/categoría propia del usuario (se usan en matching, planilla personal, etc.) — no se tocan. Las unidades supervisadas son una lista aparte que puede incluir 0, 1 o varias unidades, y no tiene por qué incluir la unidad propia.

Al migrar los datos existentes: cada usuario con `es_supervisora=True` recibe una fila en `unidad_supervisada` apuntando a su `unidad_id` actual, para no perder acceso a nadie.

**Problema 2 — cómo se crean cuentas de supervisora y cómo obtienen contraseña.**
Hoy el admin las crea desde `/admin/usuarios/nuevo` (formulario `AdminUsuarioForm`) tecleando él mismo la contraseña en texto plano — mala práctica (el admin conoce y debe transmitir la contraseña por un canal aparte).

**Decisión:** reutilizar el mecanismo de invitación ya existente para "recuperar contraseña" (`app/services/password_reset.py::generar_token_reset` + `app/services/email.py::enviar_email`, usado en `auth.recuperar_contrasena`/`auth.restablecer_password`). Al crear una cuenta de supervisora desde admin, no se pide contraseña: se genera una aleatoria interna (no comunicada a nadie) con `set_password(secrets.token_urlsafe(32))` y se envía un email de invitación con un enlace de "establece tu contraseña" (mismo flujo/plantilla que restablecer, con texto adaptado). Esto solo afecta a la creación de supervisoras; la creación de usuarios normales por admin (excepcional, ya que el alta habitual es autoregistro vía `/registro`) mantiene el campo contraseña tal cual — no forma parte de este plan.

**Quién puede crear supervisoras:** solo usuarios `es_admin=True`, vía el panel `/admin/usuarios` ya existente (no se crea un panel nuevo). Solo se añade el selector multi-unidad y se cambia el flujo de contraseña cuando `es_supervisora=True`.

---

## Paso 1 — Modelo: tabla `unidad_supervisada` + migración

- Nuevo modelo `app/models/unidad_supervisada.py` (o tabla de asociación simple `db.Table`) con `usuario_id` (FK a `usuario.id`), `unidad_id` (FK a `unidad.id`), PK compuesta o `UniqueConstraint(usuario_id, unidad_id)`.
- En `Usuario`: relación `unidades_supervisadas = db.relationship("Unidad", secondary=..., ...)`.
- Registrar el modelo en `app/models/__init__.py`.
- Test: crear usuario, asociarle 2 unidades vía la relación, comprobar que `usuario.unidades_supervisadas` las devuelve y que `unidad.supervisoras` (backref, si se añade) devuelve el usuario.
- Migración con `flask db migrate` (tabla nueva → no requiere el patrón de 3 pasos, es una tabla vacía). Añadir en el `upgrade()` un `op.execute(...)` que rellene `unidad_supervisada` con `(id, unidad_id)` para todo usuario con `es_supervisora = true`, y en `downgrade()` simplemente `drop_table`.
- Verificar `flask db heads` → debe dar exactamente 1 head.

## Paso 2 — Servicio: helpers de supervisión multi-unidad

- Nuevo módulo `app/services/supervision.py` (o añadir a uno existente si tiene sentido) con:
  - `unidades_supervisadas_de(usuario) -> list[Unidad]` (orden por nombre).
  - `puede_supervisar(usuario, unidad) -> bool`.
- Tests unitarios de estas dos funciones (con y sin acceso).

## Paso 3 — Rutas `planilla_supervision.py`: selector de unidad

- Añadir parámetro `unidad_id` (querystring, `GET`) a `index()`, `reglas()` y a los POST (`ajustar`, `turno_eliminar`, `turno_editar` — como campo oculto del formulario, no querystring, para que el redirect vuelva a la unidad correcta).
- `_exigir_supervisora()` pasa a `_unidad_supervisada_o_403(unidad_id)`: valida con `puede_supervisar` y hace `abort(403)` si no. Si no se pasa `unidad_id`, usar la primera unidad supervisada (o la unidad propia si está entre ellas, para no cambiar el comportamiento por defecto de las supervisoras actuales de una sola unidad).
- Sustituir todos los `unidad = current_user.unidad` por la unidad resuelta.
- Tests: supervisora con 2 unidades ve turnos/reglas de ambas por separado; no puede ver ni modificar una tercera unidad ajena (403); supervisora de 1 sola unidad (caso legacy) sigue funcionando igual que hoy sin pasar `unidad_id`.

## Paso 4 — Plantilla: selector de unidad en la vista de supervisión

- `templates/planilla_supervision/index.html` (y `reglas.html`): si `current_user.unidades_supervisadas` tiene más de 1 elemento, mostrar un `<select>`/tabs que recargue la página con `?unidad_id=`. Si solo tiene 1, no mostrar el selector (sin cambio visual para el caso actual).
- Prueba manual en navegador (no solo tests): crear una supervisora con 2 unidades de prueba y confirmar que el cambio de unidad funciona y que los datos mostrados (turnos, trabajadores, reglas) corresponden a la unidad seleccionada.

## Paso 5 — Formulario admin: asignar unidades a la supervisora

- `AdminUsuarioForm` (`app/forms/admin.py`): añadir campo `unidades_supervisadas` tipo `SelectMultipleField` (coerce=int), poblado dinámicamente igual que `categoria_id`. Mostrar/ocultar en el template `admin/usuario_form.html` según el checkbox `es_supervisora` (JS simple, igual que ya se hace probablemente con otros campos condicionales — revisar patrón existente en ese template antes de añadir uno nuevo).
- En `usuario_nuevo()` y `usuario_editar()` (`app/routes/admin/usuarios.py`): si `es_supervisora` es `True`, exigir al menos 1 unidad seleccionada (error de validación si no); guardar las filas en `unidad_supervisada`. Si se desmarca `es_supervisora`, limpiar las unidades supervisadas.
- Tests de las rutas admin: crear supervisora con 2 unidades → se guardan las 2; editar para quitar una → se refleja; crear supervisora sin marcar ninguna unidad → error de validación, no se crea.

## Paso 6 — Contraseña por invitación en vez de campo directo

- Servicio `app/services/password_reset.py`: reutilizar `generar_token_reset` tal cual (ya genérico, no requiere cambios).
- Nueva función en `app/services/registro.py` (o donde viva `eliminar_usuario_admin`, junto a las demás funciones de gestión admin): `crear_supervisora_con_invitacion(usuario)` — hace `usuario.set_password(secrets.token_urlsafe(32))`, genera el token de reset y llama a `enviar_email` con una plantilla nueva `email/invitacion_supervisora.html` (copiar `email/recuperar_password.html` adaptando el texto: "Se ha creado una cuenta de supervisora para ti en Turnero. Pulsa el enlace para establecer tu contraseña").
- En `usuario_nuevo()` (`app/routes/admin/usuarios.py`): si `form.es_supervisora.data`, no usar `form.password.data` (dejar de exigirlo) — en su lugar llamar a `crear_supervisora_con_invitacion` tras el `db.session.add`/`commit` inicial. Si NO es supervisora, mantener el flujo actual (password obligatorio tecleado por admin).
- Ajustar `AdminUsuarioForm`/template: el campo contraseña se oculta (JS) y dejar de ser obligatorio cuando `es_supervisora` está marcado; mostrar en su lugar un aviso "se enviará un email de invitación a {email}".
- Tests: crear supervisora nueva sin contraseña → cuenta creada, `check_password` con cualquier valor falla (no hay contraseña conocida), se ha "enviado" un email (mockear `enviar_email` y comprobar que se llama con el destinatario correcto y que el enlace apunta a `auth.restablecer_password` con un token válido para ese usuario).
- Reutilizar la vista `auth.restablecer_password` ya existente — no requiere cambios, ya funciona para cualquier usuario con un token válido.

## Paso 7 — Limpieza y prueba manual end-to-end

- Repasar que ningún sitio del código siga asumiendo "una supervisora = una unidad" (buscar `current_user.unidad` en contextos de supervisión — grep antes de cerrar).
- Prueba manual: como admin, crear una supervisora con 2 unidades → comprobar que llega (o se loggea, según config de email en dev) la invitación, establecer contraseña vía el enlace, iniciar sesión como esa supervisora y verificar que puede alternar entre sus 2 unidades en `/planilla/supervision/`.
- `pytest --testmon`, y antes de abrir PR, suite completa.

---

## Notas / asunciones a confirmar con el usuario antes o durante la implementación

- Se asume que una supervisora **no necesita** dejar de tener una `unidad_id`/`categoria_id` propia obligatoria — sigue siendo, formalmente, "de" una unidad para el resto de la app (perfil, locale, etc.), aunque no trabaje turnos ahí. Si en la práctica las supervisoras nunca deben aparecer como personal intercambiable, ese es un tema aparte (fuera de alcance de este plan).
- No se contempla en este plan un rol "supervisora de todo el hospital" (todas las unidades de un hospital automáticamente) — la asignación es explícita unidad a unidad. Si en el futuro hace falta, se puede añadir un atajo "seleccionar todas las unidades de X hospital" en el propio formulario admin, sin cambios de modelo.
- El envío de email de invitación depende de que `app/services/email.py::enviar_email` ya esté configurado y funcionando en producción (se usa hoy para recuperar contraseña) — no se planea infraestructura de email nueva.
