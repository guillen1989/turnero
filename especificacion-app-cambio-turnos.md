# App de Cambio de Turnos entre Sanitarios — Especificación Base

## 1. Visión y alcance

**Qué es:** Una app móvil (iOS y Android) que permite a los trabajadores sanitarios de una unidad publicar turnos que quieren ceder, junto con los turnos que aceptarían a cambio. La app detecta automáticamente coincidencias entre publicaciones (1 a 1, y también cadenas de 3 bandas) y notifica a los implicados para que confirmen el cambio.

**Para quién:** Personal sanitario (inicialmente enfermería) organizado por unidades dentro de hospitales. La app soporta múltiples hospitales y múltiples unidades, de forma independiente entre sí.

**Qué NO es (fuera de alcance del MVP):**
- No sustituye al cuadrante oficial del hospital ni lo gestiona; solo conoce las publicaciones de cambio, no el calendario completo de cada trabajador.
- No requiere aprobación de un supervisor ni de RRHH para que un match del motor de matching (secciones 2-4) se cierre: sigue siendo un acuerdo informal, cerrado entre los propios trabajadores sin intervención de nadie más.
- El motor de matching en sí no deja constancia oficial del cambio para terceros. La excepción es la **Hoja de cambio digital** (ver entidades `DocumentoCambio` en la sección 2, regla de negocio 11 y CU10): un flujo aparte, iniciado y rellenado a mano por los propios trabajadores, pensado para generar el mismo justificante que hoy se entrega en papel a la ayudante de la supervisora — con ese flujo sí queda constancia (un PDF firmado por ambas partes).
- No gestiona altas/bajas administrativas de unidades: el registro es libre y auto-gestionado por los propios usuarios.

**Principio de diseño clave:** Además de las coincidencias 1 a 1, el motor de matching detecta y cierra ciclos de 3 bandas (ver regla de negocio 3 y CU9). El modelo de datos y la lógica de matching siguen diseñados para poder extender el algoritmo a cadenas de 4 o más bandas sin rehacer la arquitectura, aunque eso queda fuera del alcance actual.

---

## 2. Modelo de dominio

### Entidades principales

**Hospital**
- id, nombre

**Unidad**
- id, nombre (ej. "Urgencias", "Traumatología 1")
- hospital_id
- grupo_intercambio_id *(ver abajo — permite que varias unidades compartan pool de cambios)*

**GrupoDeIntercambio**
- id
- Conjunto de unidades entre las que SÍ se permite cambiar turno (ej. Traumatología 1, 2 y 3 pertenecen al mismo grupo). Una unidad pertenece a un único grupo de intercambio. Por defecto, una unidad forma un grupo de uno solo (solo cambia consigo misma).

**Categoría profesional**
- id, nombre (ej. "Enfermería", "Auxiliar de enfermería", "Médico/a", "Celador/a")
- *(El cambio solo es válido entre usuarios de la misma categoría)*
- **Gestión:** la app parte de una **lista cerrada predefinida** (semilla) de categorías, compartida globalmente para toda la app (común a todos los hospitales). El usuario elige su categoría de esa lista durante el registro. Si su categoría no está en la lista, puede **añadir una nueva**, y esa categoría se **incorpora a la lista compartida** para que el resto de usuarios la seleccionen en lugar de volver a crearla. La selección de una categoría existente es siempre la vía principal; añadir una nueva es la excepción para categorías ausentes. Conviene una comprobación ligera para evitar duplicados obvios (p. ej., comparar ignorando mayúsculas/espacios antes de crear una nueva).
- Lista semilla orientativa (Claude Code puede ajustarla): Médico/a, Enfermería, Auxiliar de enfermería (TCAE), Celador/a, Matrón/a, Fisioterapeuta, Técnico/a (laboratorio/radiología), Farmacéutico/a.

**Usuario**
- id, nombre, email, teléfono
- unidad_id
- categoria_id
- *(unidad_id + categoria_id determinan con quién puede cambiar: mismo grupo de intercambio + misma categoría)*

**FranjaHoraria** (configurable por unidad)
- id, unidad_id (o grupo_intercambio_id), nombre (ej. "Mañana", "Tarde", "Noche", o cualquier nombre libre), hora_inicio, hora_fin
- *(cada unidad define sus propias franjas; no están fijas a nivel de toda la app)*

**Turno**
- id, fecha, franja_horaria_id
- *(un turno concreto es la combinación fecha + franja, dentro del contexto de una unidad/grupo)*

**PublicaciónDeCambio**
- id, usuario_id, fecha_creación, estado (abierta / parcialmente_resuelta / confirmada / cancelada / caducada)
- turnos_que_cede: lista de Turno que el usuario quiere quitarse (puede ser uno o varios)
- turnos_que_acepta: lista de Turno que el usuario aceptaría trabajar a cambio (puede ser uno o varios)
- *(Una publicación agrupa TODOS los turnos que un usuario quiere cambiar en un momento dado, no una publicación por turno. Cada turno individual dentro de la publicación puede resolverse de forma independiente — ver regla de negocio 2bis — sin afectar a los demás turnos de la misma publicación.)*
- *(Nota de diseño: cada publicación se modela como una oferta general — "cedo [X1, X2], acepto cualquiera de [Y1, Y2, Y3]" — lo que permite al motor de matching recombinarlas en cadenas de 3+ sin cambiar el modelo de datos)*
- **es_sintética** (booleano, por defecto falso) + **sintética_pub_a_id** / **sintética_pub_b_id**: una publicación puede ser generada automáticamente por el propio sistema (no por un usuario) para representar el "hueco" que cerraría un ciclo de 3 bandas entre otras dos publicaciones reales A y B (ver regla de negocio 3). No aparece como propia de nadie en el dashboard del usuario propietario; solo se ofrece a terceros compatibles en el buscador. Se cancela automáticamente si A o B se cancelan, editan o caducan.

**Match / Coincidencia**
- id, tipo (directo_2 / cadena_3 / cadena_n — `cadena_n` con n>3 queda fuera del alcance actual)
- publicaciones_implicadas: lista de PublicaciónDeCambio (2 para directo, 3 para cadena_3)
- estado (propuesto / confirmado_parcial / confirmado_total / rechazado)
- confirmaciones: registro de qué usuarios han confirmado y quiénes faltan

**Notificación**
- id, usuario_id, match_id, tipo, fecha, leída (sí/no)

**DocumentoCambio** (hoja de cambio digital — ver regla de negocio 11 y CU10)
- id, estado (borrador / pendiente_firmas / completo / caducado), fecha_creación, creado_por_id, factibilidad_estado (no_verificado / factible / no_factible)
- match_id (nullable): se rellenaría si el documento se generase automáticamente desde un Match ya confirmado por el motor de matching; en la fase actual siempre está vacío, porque el documento se rellena a mano, en un flujo aparte del matching automático de las secciones 2-4.
- *(Reproduce digitalmente la hoja de papel "Solicitud de cambio de turno o guardia" que hoy se entrega a la ayudante de la supervisora, incluyendo firma dibujada de ambas partes y generación de PDF)*

**ParticipanteDocumentoCambio**
- id, documento_id, usuario_id, turno_cede_fecha, turno_cede_franja_id, turno_recibe_fecha, turno_recibe_franja_id
- Una fila por cada trabajador implicado en el documento (2 en la fase actual — sin cadenas a 3/4 ni juntes de noches; el modelo admite más filas sin rediseño para cuando se soporten).

**FirmaDocumentoCambio**
- id, documento_id, usuario_id, fecha_firma, imagen_firma (trazo dibujado con el dedo sobre un canvas, guardado como imagen), hash_documento (huella del contenido exacto firmado, para poder demostrar qué se firmó aunque la plantilla del PDF cambie después)
- Una fila por cada firma recogida (2 en la fase actual).

### Reglas de pertenencia / visibilidad
- Un usuario solo puede ver y generar matches con usuarios de su **misma categoría profesional** y dentro de su **mismo grupo de intercambio** (su unidad u otras unidades vinculadas).

---

## 3. Reglas de negocio

1. **Quién puede cambiar con quién:** mismo grupo de intercambio (unidad o unidades vinculadas) + misma categoría profesional. Sin excepciones en el MVP.

2. **Condición de match directo (2 personas):** Publicación A coincide con Publicación B si:
   - Al menos uno de los turnos que **cede** A está en los turnos que **acepta** B, **Y**
   - Al menos uno de los turnos que **cede** B está en los turnos que **acepta** A.
   - Si hay varios turnos posibles en cualquiera de los dos lados, basta con que coincida uno cualquiera de cada lado; no es necesario que coincidan todos.

2bis. **Resolución parcial:** Una publicación puede ceder varios turnos a la vez. Cuando uno de esos turnos queda resuelto mediante un match confirmado, ese turno concreto se cierra, pero el resto de turnos de la misma publicación siguen abiertos y disponibles para futuros matches. La publicación en su conjunto solo pasa a estado "confirmada" cuando TODOS sus turnos a ceder han sido resueltos; mientras tanto permanece en estado "parcialmente_resuelta".

3. **Condición de match en cadena (3 personas):** A cede algo que B acepta; B cede algo que C acepta; C cede algo que A acepta (cierre del ciclo). El sistema detecta estos ciclos automáticamente entre las publicaciones abiertas, por dos vías complementarias:
   - **Detección directa:** cada vez que se publica o edita una publicación tipo "cambio", el sistema busca entre las publicaciones activas del mismo grupo/categoría si existe algún par que, junto con la nueva, cierre un ciclo de 3 bandas. Si lo encuentra, crea el match `cadena_3` inmediatamente, sin intervención del usuario.
   - **Publicaciones sintéticas (caso de solape unilateral entre solo 2 personas):** cuando A y B tienen coincidencia en un solo sentido (A puede dar a B lo que B quiere, pero no al revés, o viceversa) no hay match directo, pero falta solo un tercero para cerrar el ciclo. En ese caso el sistema genera automáticamente una **publicación sintética** (no publicada por ningún usuario) que representa exactamente lo que ese tercer usuario C necesitaría ofrecer para cerrarlo, y notifica a A y B de la oportunidad. Esa sintética aparece en el buscador de cualquier tercer usuario compatible. Si un tercero C la ve, puede aceptarla con un único gesto ("me interesa"), que genera automáticamente su publicación real con los turnos correspondientes y cierra el ciclo. Pero **el ciclo también se detecta si C nunca ve la sintética** y simplemente publica su propio cambio por su cuenta: el mismo chequeo de detección directa (arriba) compara su nueva publicación contra las sintéticas existentes y cierra el ciclo igualmente.
   - En ambos casos, cerrar el ciclo crea un match `cadena_3` sujeto a la misma regla de confirmación obligatoria (regla 4) que un match directo: nadie queda cerrado hasta que las tres partes confirman.

4. **Confirmación obligatoria:** Ningún match se cierra automáticamente. Cada usuario implicado debe confirmar explícitamente "acepto este cambio" dentro de la app. El match solo queda **confirmado** cuando TODAS las partes implicadas han confirmado.

5. **Rechazo sin penalización:** Cualquier implicado puede rechazar un match propuesto en cualquier momento antes de la confirmación total, sin consecuencias. Al rechazar, el match se descarta y las publicaciones implicadas vuelven a estado "abierta", siguiendo activas para futuros matches.

6. **Caducidad:** Una publicación caduca automáticamente cuando la fecha del turno que se quiere ceder ya ha pasado. No hay fecha límite manual.

7. **Cancelación manual:** El usuario puede cancelar su propia publicación en cualquier momento, siempre que no tenga ya un match confirmado.

8. **Múltiples publicaciones simultáneas:** Un usuario puede tener varias publicaciones abiertas a la vez (varios turnos distintos que quiere ceder).

9. **Tras una confirmación total:** Las publicaciones implicadas pasan a estado "confirmada" y se retiran de la búsqueda de nuevos matches. No se genera ningún registro visible para terceros (RRHH/supervisor); es un acuerdo informal entre los usuarios.

10. **Notificaciones:** Se envía notificación push a un usuario cuando:
    - Se detecta un nuevo match potencial sobre alguna de sus publicaciones abiertas.
    - Otra parte de un match confirma su parte (para informar del avance).
    - Un match en el que estaba implicado es rechazado por otra parte.

11. **Hoja de cambio digital, flujo aparte del matching automático:** un usuario puede generar y firmar digitalmente una hoja de cambio equivalente a la de papel, sin pasar por el motor de matching de las reglas 1-10 (no hace falta que exista una publicación ni un match). En la fase actual (mono-cuenta): las dos firmas se recogen desde el mismo dispositivo — quien crea el documento se lo pasa físicamente al compañero para que firme — sin que este último necesite tener sesión iniciada en la app.

12. **Sin bloqueo por falta de verificación:** el documento se puede crear, rellenar y firmar aunque la app no pueda comprobar su factibilidad contra la planilla (por ejemplo, si algún implicado no tiene su planilla del mes publicada). El documento queda marcado como "no verificado" en vez de bloquearse, para no impedir su uso mientras la adopción de planillas no sea universal entre el personal.

13. **Comprobación de factibilidad, informativa, no bloqueante:** cuando ambos implicados tienen su planilla publicada para los meses de las fechas del cambio, la app comprueba automáticamente que cada uno trabaja de verdad el turno que dice ceder y está libre para el que dice recibir (mismas reglas que la comprobación de compatibilidad de planilla usada al publicar un cambio normal). El resultado (factible / no_factible / no_verificado) se muestra de forma visible junto al documento, pero no bloquea la firma en ningún caso — la decisión final es de los propios trabajadores.

14. **Documento fiel al impreso oficial:** el PDF generado reproduce el formulario en papel real del hospital (mismo encabezado, campos y disposición), incluyendo el bloque para el informe de la supervisora, que la app deja en blanco por no formar parte del flujo digital.

---

## 4. Casos de uso

### CU1 — Registro de usuario
Un trabajador se registra con email/teléfono, indica su hospital, su unidad y su categoría profesional. Si la unidad o el hospital no existen aún en la app, puede crearlos (alta libre, sin validación administrativa). La categoría profesional se elige de una lista cerrada compartida; si la suya no está en la lista, puede añadir una nueva, que pasa a formar parte de la lista compartida para el resto de usuarios.

### CU2 — Publicar un cambio
Ana, enfermera de Urgencias, selecciona el turno que quiere ceder (ej. mañana del 25/06) y uno o varios turnos que aceptaría a cambio (ej. tarde del 26/06, noche del 28/06). Publica la oferta, que queda visible para el resto de enfermeras de Urgencias (o unidades de su grupo de intercambio).

### CU3 — Detección de match directo
Pedro, también enfermero de Urgencias, publica que se ofrece a trabajar la mañana del 25/06 y que a cambio quiere librar la tarde del 26/06 (uno de los turnos que Ana ofrece). La app detecta automáticamente la coincidencia y notifica tanto a Ana como a Pedro.

### CU4 — Confirmación de match
Ana y Pedro reciben la notificación, revisan el match propuesto y cada uno confirma desde la app. Cuando ambos han confirmado, el match pasa a "confirmado" y ambas publicaciones se cierran.

### CU5 — Rechazo de match
Si Ana, al ver el match propuesto, decide que ya no le interesa, lo rechaza. Pedro recibe una notificación de que el match se ha descartado. La publicación de Ana sigue abierta y disponible para otros matches.

### CU6 — Cancelación de publicación
Ana decide que ya no necesita cambiar el turno y cancela su publicación manualmente, siempre que no tenga un match ya confirmado.

### CU7 — Caducidad automática
Si nadie confirma un match con Ana antes del 25/06, la publicación de Ana caduca automáticamente al pasar esa fecha y desaparece de las búsquedas activas.

### CU8 — Match en cadena de 3 entre publicaciones ya existentes
Ana cede mañana del 25, acepta tarde del 26. Andrea cede tarde del 27, acepta mañana del 25. Pedro publica que cede tarde del 26 y acepta tarde del 27, sin haber visto las publicaciones de Ana ni de Andrea. Al publicar, el sistema detecta automáticamente el ciclo Ana→Andrea→Pedro→Ana entre las tres publicaciones y notifica a los tres de un posible cambio a tres bandas, donde cada uno deberá confirmar igualmente su parte.

### CU9 — Match en cadena de 3 vía publicación sintética
Ana cede mañana del 25 y acepta tarde del 26. Andrea cede tarde del 26 y acepta mañana del 25... pero solo en parte: en realidad Andrea cede tarde del 27 y acepta mañana del 25 (no coincide con lo que cede Ana). Hay solape en un solo sentido: Ana puede dar a Andrea lo que quiere, pero Andrea no tiene nada que Ana acepte. El sistema no puede cerrar un match directo, pero detecta que falta solo un tercero y genera automáticamente una publicación sintética (invisible como "propia" para nadie) que representa lo que ese tercero necesitaría ofrecer. Ana y Andrea reciben un aviso de "oportunidad a 3 bandas". Más tarde, Pedro busca cambios y ve esa publicación sintética marcada como oportunidad a 3 bandas; pulsa "me interesa", el sistema crea automáticamente su publicación real y cierra el ciclo Ana→Andrea→Pedro→Ana sin que Pedro tenga que rellenar el formulario de publicación a mano.

### CU10 — Generar y firmar una hoja de cambio digital
Claudia acuerda con Juan, verbalmente, cambiarle el turno de mañana del 7 de julio por el de mañana del 28 de julio. En vez de rellenar la hoja de papel, Claudia crea una hoja de cambio digital desde la app, indicando el compañero y los turnos. La app comprueba automáticamente si el cambio es factible contra las planillas de ambos (cuando están publicadas) y lo indica en la pantalla, sin bloquear nada. Claudia firma dibujando con el dedo en el móvil, le pasa el móvil a Juan, que firma también. Con las dos firmas, el documento queda "completo": Claudia puede generar el PDF firmado (idéntico al impreso del hospital) para enseñárselo a quien haga falta, y la app genera automáticamente las notas en lenguaje natural que la ayudante de la supervisora necesita copiar en la nota de cada día en ilog (una por trabajador y día afectado).

---

## 5. Decisiones técnicas

- **Tipo de app:** Web app instalable (PWA — Progressive Web App). Se instala desde el navegador ("añadir a pantalla de inicio") en iOS y Android, sin pasar por App Store ni Google Play. Esto permite distribución y actualizaciones instantáneas sin revisión de tienda.
- **Backend:** Python con Flask.
- **Frontend:** HTML/CSS/JS sencillo, server-rendered con plantillas de Flask (Jinja2) para mantener el MVP simple y rápido de construir.
- **Base de datos:** relacional (a concretar con Claude Code — PostgreSQL es la opción natural en Railway).
- **Despliegue:** Railway.
- **Notificaciones push:** mediante Web Push API (notificaciones push web estándar, compatibles con PWA). Aviso importante: en iOS el soporte de Web Push tiene más limitaciones que en Android (requiere iOS 16.4+ y que el usuario haya instalado la PWA en pantalla de inicio); se acepta esta limitación para el MVP, revisable en el futuro si se necesita migrar a app nativa.
- **Prioridad del MVP:** velocidad de desarrollo y validación de la idea por encima de robustez para producción a gran escala.
- **Motor de matching:** módulo puro e independiente dentro del backend Flask (`app/matching/engine.py` + `app/matching/service.py`), que resuelve matching 1 a 1 y ciclos de 3 bandas (directos y vía publicación sintética), diseñado para poder añadir detección de ciclos de 4 o más bandas más adelante sin rehacer el modelo de datos.
- **Generación del PDF de la hoja de cambio:** `xhtml2pdf` (Python puro, sin dependencias nativas de sistema), generado bajo demanda en cada petición sin persistir el binario (evita depender de almacenamiento persistente en Railway). Elegido tras un incidente en producción con `WeasyPrint` (necesita Pango/cairo/gdk-pixbuf vía cffi, ausentes en el contenedor de Railway y no resueltos tras dos intentos de declarar los paquetes de sistema en `nixpacks.toml`) — al ser Python puro, `xhtml2pdf` no puede volver a fallar por esa causa.

---

## 6. User Acceptance Tests (UAT)

Formato: Dado [contexto] / Cuando [acción] / Entonces [resultado esperado].

### Registro y alta

**UAT-1.1 — Registro de un nuevo usuario**
- Dado que no existo como usuario en la app,
- Cuando me registro con mi email, indico mi hospital, unidad y categoría profesional,
- Entonces se crea mi cuenta y quedo asociado a esa unidad y categoría.

**UAT-1.2 — Alta de hospital/unidad nuevos**
- Dado que mi hospital o mi unidad no existen aún en la app,
- Cuando los creo durante mi registro,
- Entonces quedan disponibles en la app y puedo asociarme a ellos sin necesitar aprobación de nadie.

**UAT-1.3 — Selección de categoría de la lista existente**
- Dado que mi categoría profesional ya está en la lista compartida,
- Cuando me registro,
- Entonces la selecciono de la lista y quedo asociado a esa categoría existente (no se crea una nueva).

**UAT-1.4 — Alta de categoría no presente en la lista**
- Dado que mi categoría profesional no está en la lista compartida,
- Cuando añado una categoría nueva durante el registro,
- Entonces esa categoría se incorpora a la lista compartida y queda disponible para que otros usuarios la seleccionen, en lugar de tener que volver a crearla.

### Publicación de cambios

**UAT-2.1 — Publicar un cambio con un solo turno**
- Dado que soy un usuario registrado,
- Cuando publico que quiero ceder un turno concreto y especifico uno o varios turnos que aceptaría a cambio,
- Entonces la publicación queda visible para los usuarios de mi misma categoría y grupo de intercambio.

**UAT-2.2 — Publicar un cambio con varios turnos a ceder**
- Dado que quiero cambiar dos turnos distintos míos,
- Cuando los incluyo en una misma publicación,
- Entonces ambos turnos quedan registrados dentro de esa única publicación, cada uno con su propio estado de resolución.

**UAT-2.3 — Visibilidad restringida por categoría y unidad**
- Dado que soy enfermera de Urgencias en el Hospital La Paz,
- Cuando publico un cambio,
- Entonces solo lo ven enfermeras (mi categoría) de Urgencias o de unidades de mi mismo grupo de intercambio — no lo ve, por ejemplo, un auxiliar, ni una enfermera de otro hospital sin relación.

### Detección de match

**UAT-3.1 — Match directo 1 a 1**
- Dado que Ana publica que cede la mañana del 25/06 y acepta la tarde del 26/06,
- Y Pedro publica que cede la tarde del 26/06 y acepta la mañana del 25/06,
- Cuando el sistema procesa las publicaciones,
- Entonces se genera un match entre Ana y Pedro, y ambos reciben una notificación push.

**UAT-3.2 — Sin match si no hay coincidencia en ambos sentidos**
- Dado que Ana cede la mañana del 25/06 y acepta la tarde del 26/06,
- Y Pedro cede la noche del 27/06 y acepta la mañana del 25/06,
- Cuando el sistema procesa las publicaciones,
- Entonces NO se genera ningún match (el turno que cede Pedro no coincide con lo que acepta Ana).

**UAT-3.3 — Match con varias opciones por cada lado**
- Dado que Ana acepta a cambio "tarde del 26/06 O noche del 28/06",
- Y Pedro cede "tarde del 26/06" entre otros turnos,
- Cuando hay coincidencia en al menos una opción de cada lado,
- Entonces se genera el match, sin necesidad de que coincidan todas las opciones.

**UAT-3.4 — Resolución parcial de una publicación multi-turno**
- Dado que Ana tiene una publicación con dos turnos a ceder (mañana del 25/06 y noche del 27/06),
- Cuando se confirma un match solo para el turno del 25/06,
- Entonces ese turno se marca como resuelto, la publicación pasa a estado "parcialmente_resuelta", y el turno del 27/06 sigue abierto buscando match.

### Confirmación y rechazo

**UAT-4.1 — Confirmación de ambas partes cierra el match**
- Dado que existe un match propuesto entre Ana y Pedro,
- Cuando ambos confirman su parte desde la app,
- Entonces el match pasa a estado "confirmado", y los turnos implicados se retiran de la búsqueda activa de nuevos matches.

**UAT-4.2 — Falta una confirmación, el match queda pendiente**
- Dado que existe un match propuesto entre Ana y Pedro,
- Cuando solo Ana confirma su parte,
- Entonces el match permanece en estado "confirmado_parcial" hasta que Pedro también confirme.

**UAT-4.3 — Rechazo sin penalización**
- Dado que existe un match propuesto entre Ana y Pedro,
- Cuando Ana rechaza el match,
- Entonces el match se descarta, Pedro recibe una notificación del rechazo, y ambos turnos vuelven a estado "abierta" para seguir buscando otros matches — sin ninguna penalización para Ana.

### Cancelación y caducidad

**UAT-5.1 — Cancelación manual de una publicación**
- Dado que tengo una publicación abierta sin match confirmado,
- Cuando la cancelo manualmente,
- Entonces deja de estar visible para otros usuarios y no genera más notificaciones.

**UAT-5.2 — No se puede cancelar un turno ya confirmado**
- Dado que uno de los turnos de mi publicación ya tiene un match confirmado,
- Cuando intento cancelar la publicación,
- Entonces el sistema no permite cancelar la parte ya confirmada (puede seguir permitiendo cancelar los turnos restantes que aún estén abiertos, si los hay).

**UAT-5.3 — Caducidad automática**
- Dado que un turno publicado para ceder tiene fecha 25/06,
- Cuando llega o pasa esa fecha sin que se haya confirmado ningún match,
- Entonces ese turno (y la publicación, si era el único pendiente) pasa a estado "caducada" automáticamente, sin acción manual del usuario.

### Cadenas a 3 bandas

**UAT-7.1 — Detección de cadena a 3 bandas entre publicaciones ya existentes**
- Dado que Ana cede la mañana del 25 y acepta la tarde del 26; Andrea cede la tarde del 27 y acepta la mañana del 25,
- Cuando Pedro publica que cede la tarde del 26 y acepta la tarde del 27 (sin haber visto las publicaciones de Ana ni Andrea),
- Entonces el motor de matching detecta el ciclo cerrado entre las tres publicaciones al momento de publicar, y los tres usuarios reciben notificación de un posible cambio a tres bandas, donde cada uno debe confirmar su parte individualmente para cerrarlo.

**UAT-7.2 — Aviso de oportunidad a 3 bandas por solape unilateral**
- Dado que Ana cede la mañana del 25 y acepta la tarde del 26, y Andrea cede la tarde del 27 y acepta la mañana del 25 (Ana puede cubrir a Andrea, pero Andrea no tiene nada que Ana acepte),
- Cuando el sistema procesa ambas publicaciones,
- Entonces no se genera un match directo, pero el sistema crea una publicación sintética con el hueco que cerraría el ciclo, y Ana y Andrea reciben un aviso de "oportunidad a 3 bandas".

**UAT-7.3 — Cierre de la cadena mediante "me interesa" sobre la sintética**
- Dado que existe la publicación sintética del UAT-7.2,
- Cuando Pedro, compatible por categoría y grupo de intercambio, la encuentra en el buscador y pulsa "me interesa",
- Entonces el sistema crea automáticamente la publicación real de Pedro con los turnos correspondientes, cierra el match `cadena_3` entre Ana, Andrea y Pedro, y cancela la publicación sintética.

**UAT-7.4 — Cierre de la cadena aunque el tercero no haya visto la sintética**
- Dado que existe la publicación sintética del UAT-7.2,
- Cuando Pedro publica su propio cambio de forma independiente (cede tarde del 26, acepta tarde del 27) sin haber visto ni interactuado con la sintética,
- Entonces el sistema detecta igualmente la coincidencia con la sintética al procesar la nueva publicación de Pedro, y cierra el match `cadena_3` entre Ana, Andrea y Pedro automáticamente.

### Notificaciones

**UAT-6.1 — Notificación ante nuevo match potencial**
- Dado que tengo una publicación abierta,
- Cuando otro usuario publica algo que genera un match con la mía,
- Entonces recibo una notificación push informándome del match potencial.

**UAT-6.2 — Notificación ante avance de confirmación**
- Dado que estoy implicado en un match propuesto,
- Cuando la otra parte confirma su parte del match,
- Entonces recibo una notificación informándome de que falta solo mi confirmación.

### Hoja de cambio digital

**UAT-8.1 — Generar el documento sin planilla, sin bloquear**
- Dado que ni yo ni mi compañero tenemos la planilla del mes publicada,
- Cuando creo una hoja de cambio digital con él,
- Entonces el documento se crea igualmente, marcado como "factibilidad no verificada", y puedo seguir hasta la firma sin que nada me lo impida.

**UAT-8.2 — Factibilidad correcta con planillas publicadas**
- Dado que ambos tenemos la planilla del mes publicada, y de verdad trabajo el turno que digo ceder y estoy libre para el que digo recibir (y lo mismo mi compañero),
- Cuando creo la hoja de cambio,
- Entonces el documento se marca como "factible".

**UAT-8.3 — Aviso de no factibilidad sin bloquear la firma**
- Dado que ambos tenemos la planilla publicada, pero según ella yo no trabajo el turno que digo ceder,
- Cuando creo la hoja de cambio,
- Entonces el documento se marca como "no factible" con un aviso visible, pero puedo firmarlo igualmente si decido continuar.

**UAT-8.4 — Firma mono-cuenta de las dos partes**
- Dado que he creado una hoja de cambio con mi compañero,
- Cuando dibujo mi firma y luego le paso el móvil para que dibuje la suya,
- Entonces el documento queda con las dos firmas registradas y pasa a estado "completo", sin que mi compañero necesite tener sesión iniciada en la app.

**UAT-8.5 — Generar el PDF solo cuando está completo**
- Dado que la hoja de cambio todavía no tiene las dos firmas,
- Cuando intento generar el PDF,
- Entonces la app no lo permite (la opción de generar PDF solo aparece cuando el documento está "completo").

**UAT-8.6 — Notas para ilog**
- Dado que la hoja de cambio está completa,
- Cuando la abro,
- Entonces veo cuatro notas de texto listas para copiar (una por cada trabajador y día afectado), redactadas en el mismo estilo que se usa hoy a mano en ilog.

### Fuera de alcance del MVP (a validar en fase futura)

Cadenas de 4 o más bandas: el modelo de datos y el motor de matching están diseñados para soportarlas sin rediseño, pero el algoritmo de detección de ciclos de N>3 publicaciones no está implementado.

Hoja de cambio digital — pendiente de fase futura: firma cruzada entre cuentas reales (hoy las dos firmas se recogen desde el mismo dispositivo); cadenas a 3/4 bandas y juntes de noches dentro del propio documento; recomprobación de factibilidad en el momento de la segunda firma (hoy solo se calcula una vez, al crear el documento); enganche automático con el motor de matching vía `match_id` para generar el documento directamente desde un match ya confirmado.
