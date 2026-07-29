# Plan: publicar Turnero en Google Play Store

> Cada fase está pensada para completarse en una o varias sesiones independientes.
> Marca la casilla al terminar cada paso y anota en `PROGRESS.md` (o en este
> mismo archivo, sección "Notas de ejecución" al final) cualquier decisión o
> dato generado (nombre de paquete, huella SHA-256, URLs de listing, etc.) que
> haga falta en fases posteriores. Muchos pasos de este plan **no son de
> código** (cuenta de Google Play, subir capturas, rellenar formularios): no
> tienen TDD ni tests, pero sí requieren acción humana fuera de Claude Code en
> varios puntos — están marcados explícitamente como **[ACCIÓN HUMANA]**.

## Contexto técnico (leer antes de empezar cualquier fase)

- **Camino elegido: TWA (Trusted Web Activity), no una app nativa ni React
  Native/Capacitor.** La app ya es una PWA funcional (`app/routes/pwa.py`,
  `app/static/sw.js`, manifest dinámico) — una TWA envuelve esa PWA en un
  shell Android mínimo que la muestra a pantalla completa vía Chrome Custom
  Tabs, sin reescribir nada del frontend. Es el camino estándar y con menos
  mantenimiento para una PWA ya construida en Flask/Jinja.
- Estado actual de la PWA (verificado en este repo):
  - `app/routes/pwa.py` sirve `/manifest.json` (dinámico) y `/sw.js`.
  - Iconos ya existen: `app/static/icons/icon-192.png`, `icon-512.png`,
    `badge-72.png`. **Hay que verificar que 192/512 tienen "safe zone"
    maskable** (contenido dentro del 80% central) porque el manifest ya
    declara `"purpose": "any maskable"` para ambos — si el icono actual no
    respeta la zona segura, Android recortará mal el icono adaptativo.
  - `app/static/sw.js` solo precachea `/` — suficiente para instalabilidad,
    pero conviene un fallback offline mínimo antes de publicar (ver Fase 1).
  - Push notifications ya con VAPID (`app/push/sender.py`, `pywebpush`) —
    **no requieren cambios para la TWA**: Chrome en Android gestiona el push
    igual que en escritorio, no hace falta Firebase Cloud Messaging nativo.
  - Despliegue en Railway. Dominio actual de producción a confirmar (ver Fase
    2) — el `.env.example` referencia `https://tu-app.railway.app` como
    placeholder y `turnero.xyz` como dominio ya reservado para email
    (`RESEND_FROM_EMAIL=noreply@turnero.xyz`). La TWA necesita un dominio
    **estable** (el mismo para siempre, no un subdominio `*.up.railway.app`
    que pueda cambiar).
- **Bloqueo por cuenta con login:** la app requiere autenticación para casi
  todo. Google Play pide, para la revisión, credenciales de una cuenta de
  demo funcional — ya existe el patrón `DEMO_LOGIN_EMAIL`/`DEMO_LOGIN_PASSWORD`
  para staging (ver `config.py`); en producción hace falta una cuenta
  equivalente (real o de demo) que el equipo de revisión de Google pueda usar.
- **Requisito de Google Play desde nov. 2023 para cuentas nuevas:** antes de
  poder publicar en producción, toda app nueva debe pasar por una pista de
  pruebas cerrada (closed testing) con **al menos 12 testers activos durante
  14 días consecutivos**. Esto añade tiempo de calendario que no depende de
  escribir código — hay que arrancarlo cuanto antes (Fase 6).
- **La cuenta de desarrollador de Google Play (25 $ únicos) y el pago del
  dominio/certificados son acciones humanas con dinero real** — Claude Code no
  puede ejecutarlas; están marcadas como [ACCIÓN HUMANA] y solo se puede
  ayudar a preparar lo previo.
- Dado que la app maneja datos de personal sanitario (turnos, categoría
  profesional, posiblemente datos identificativos), la ficha de Play exige
  una **política de privacidad pública** y, si la app permite crear/darse de
  baja de una cuenta, una **URL de eliminación de cuenta** públicamente
  accesible (no solo dentro de la app). Ninguna de las dos existe hoy en el
  repo (no se encontró `privacy`/`terms`/`aviso-legal` en `app/templates` ni
  en la raíz).

---

## Fase 1 — Auditoría y refuerzo de la PWA existente

- [x] Ejecutar una auditoría Lighthouse (categoría PWA) contra staging o
  local y documentar el resultado (captura o resumen) en este archivo, sección
  "Notas de ejecución".
- [x] Verificar que `icon-192.png` e `icon-512.png` respetan la zona segura
  "maskable" (contenido dentro del 80% central, sin texto ni bordes pegados
  al borde). Si no la respetan, regenerar los iconos con margen y actualizar
  `app/static/icons/`.
- [x] Añadir una página/fallback offline mínima en `app/static/sw.js` (p. ej.
  servir una página "sin conexión" cacheada cuando falla el `fetch` de
  navegación), con su test si aplica.
- [x] Confirmar que `theme_color`/`background_color` del manifest
  (`app/routes/pwa.py`) coinciden con el diseño real de la app (actualmente
  `#2563eb` / `#ffffff`).
- [x] Confirmar que todas las páginas relevantes cargan por HTTPS sin
  contenido mixto (http://) — revisar `app/templates` en busca de `src="http://`
  o similar.

## Fase 2 — Dominio estable de producción

- [x] **[ACCIÓN HUMANA]** Decidir y confirmar el dominio definitivo de
  producción (candidato: `turnero.xyz` o un subdominio como `app.turnero.xyz`,
  ya reservado para email). Debe ser el mismo dominio para siempre: la TWA y
  el fichero `assetlinks.json` (Fase 4) quedan atados a él.
- [x] **[ACCIÓN HUMANA]** Configurar el dominio elegido en Railway (dominio
  personalizado + certificado TLS automático) y verificar que resuelve y
  sirve la app por HTTPS.
- [x] Actualizar `APP_BASE_URL` (ver `config.py`) y cualquier referencia a la
  URL de producción en el repo para usar el dominio definitivo.
- [x] Verificar que `/manifest.json` y `/sw.js` se sirven correctamente desde
  el dominio definitivo (no solo desde el subdominio de Railway).

## Fase 3 — Aspectos legales obligatorios

- [x] Escribir y publicar una página de **Política de Privacidad** (ruta
  pública, sin login, p. ej. `/privacidad`) que cubra: qué datos personales se
  recogen (nombre, email, categoría profesional, turnos, firma), con qué
  finalidad, cuánto tiempo se conservan, si se comparten con terceros
  (Resend para email, Railway para hosting), y los derechos RGPD del usuario
  (acceso, rectificación, supresión) dado el contexto español/UE.
- [x] Escribir y publicar unos **Términos de Uso** básicos (ruta pública, p.
  ej. `/terminos`).
- [x] Añadir una **página o mecanismo público de eliminación de cuenta**
  (accesible sin instalar la app, p. ej. `/eliminar-cuenta` con instrucciones
  o un formulario), tal y como exige la política de Google Play para apps con
  cuentas de usuario — puede ser tan simple como una dirección de contacto
  con un compromiso de plazo de borrado, pero tiene que ser una URL pública.
- [x] Enlazar estas páginas desde el pie de página de la app (`base.html`) y
  desde el formulario de registro si existe.
- [x] Marcar todos los textos nuevos con `_()`/`gettext` según la convención
  de i18n de `CLAUDE.md`.

## Fase 4 — Generar el paquete Android (TWA)

- [x] **[ACCIÓN HUMANA]** Decidir el nombre de paquete Android (formato
  reverse-domain, p. ej. `xyz.turnero.app`) — es definitivo, no se puede
  cambiar después de publicar.
- [x] Instalar y configurar [Bubblewrap CLI](https://github.com/GoogleChromeLabs/bubblewrap)
  (requiere Node.js + JDK) o usar [PWABuilder](https://www.pwabuilder.com/)
  como alternativa sin instalación local, apuntando al `manifest.json` del
  dominio definitivo de la Fase 2.
- [x] Generar el proyecto Android TWA (`bubblewrap init --manifest=<url>`),
  revisando: nombre de la app, colores, orientación, `display: standalone`.
- [x] **[ACCIÓN HUMANA]** Generar el *keystore* de firma (upload key) y
  **guardarlo con máxima seguridad y backup** (contraseña + fichero `.jks`) —
  perderlo impide publicar actualizaciones futuras de la app. No debe
  commitearse al repo.
- [x] Compilar el Android App Bundle (`.aab`) con `bubblewrap build`.
- [x] Publicar el fichero **Digital Asset Links** en
  `https://<dominio>/.well-known/assetlinks.json`, referenciando el nombre de
  paquete y la huella SHA-256 del certificado (primero la del upload key; más
  adelante, tras el primer envío a Play, añadir también la huella que genere
  **Play App Signing**, ver Fase 5). Añadir la ruta correspondiente en
  `app/routes/pwa.py` (o servir el fichero estático desde `app/static/.well-known/`).
- [ ] Verificar con la herramienta de Google
  (`https://developers.google.com/digital-asset-links/tools/generator`) que
  la asociación dominio↔app es válida antes de subir el `.aab`.

## Fase 5 — Google Play Console: cuenta y ficha de la app

- [ ] **[ACCIÓN HUMANA]** Crear/usar una cuenta de Google Play Console
  (individual o de organización) y pagar la cuota única de registro (25 $).
- [ ] **[ACCIÓN HUMANA]** Crear la app dentro de Play Console: nombre,
  idioma por defecto (español), tipo (app, gratuita).
- [x] Subir el `.aab` generado en la Fase 4 a una pista interna o cerrada
  inicial.
- [ ] **[ACCIÓN HUMANA]** Activar **Play App Signing** y, una vez Google
  genere su propia clave de firma, descargar la huella SHA-256 del
  certificado de Play desde *App integrity* y añadirla al
  `assetlinks.json` (Fase 4) junto a la del upload key.
- [x] Preparar los recursos gráficos de la ficha de Play: icono de alta
  resolución (512×512 PNG), gráfico de funciones/feature graphic (1024×500),
  al menos 2 capturas de pantalla de teléfono (se pueden generar con
  Playwright, ya usado en `e2e/`, contra staging). Ver
  `docs/store-assets/ficha_play_store.md`.
- [x] Redactar título, descripción corta (80 car.) y descripción completa de
  la ficha de la app, en español. Ver `docs/store-assets/ficha_play_store.md`.
- [ ] **[ACCIÓN HUMANA]** Rellenar el **cuestionario de clasificación de
  contenido** (IARC) en Play Console. Respuestas orientativas preparadas en
  `docs/store-assets/ficha_play_store.md`.
- [ ] **[ACCIÓN HUMANA]** Rellenar la sección **Data safety** (seguridad de
  los datos) en Play Console. Contenido ya redactado en
  `docs/store-assets/ficha_play_store.md`.
- [ ] **[ACCIÓN HUMANA]** Declarar **público objetivo y contenido para
  familias** en Play Console: marcar que la app no está dirigida a niños
  (uso profesional/sanitario). Texto orientativo en
  `docs/store-assets/ficha_play_store.md`.
- [ ] **[ACCIÓN HUMANA]** Enlazar la **Política de Privacidad** (Fase 3) en
  el campo correspondiente de Play Console:
  `https://app.turnero.xyz/privacidad`.
- [ ] **[ACCIÓN HUMANA]** Declarar en Play Console que la app **no
  contiene anuncios** (confirmado, no hay anuncios en la app).
- [ ] **[BLOQUEADO — pendiente decisión]** Añadir en el campo de notas para
  el revisor las **credenciales de la cuenta de demo** de producción para
  que el equipo de revisión de Google pueda acceder a las partes con login.
  `config.py` ya soporta `DEMO_LOGIN_EMAIL`/`DEMO_LOGIN_PASSWORD` vía
  variables de entorno, pero no están configuradas en Railway producción.
  Falta decidir con el usuario cómo crear esa cuenta antes de tocar datos
  de producción (ver nota en `docs/store-assets/ficha_play_store.md`).

## Fase 6 — Pruebas cerradas (closed testing)

- [ ] **[ACCIÓN HUMANA]** Crear una pista de pruebas cerrada en Play Console
  e invitar como mínimo a 12 testers (idealmente compañeros/as reales del
  hospital, con sus emails de Google) mediante el enlace de opt-in.
- [ ] Confirmar que al menos 12 testers instalan y abren la app.
- [ ] Mantener la pista activa **14 días consecutivos** sin interrupciones
  (requisito de Google para cuentas de desarrollador nuevas antes de poder
  promocionar a producción).
- [ ] Recoger feedback de los testers durante ese periodo y corregir bugs
  bloqueantes que aparezcan (issues normales de desarrollo, seguir el flujo
  TDD habitual de `CLAUDE.md`).

## Fase 7 — Publicación en producción y mantenimiento

- [ ] **[ACCIÓN HUMANA]** Una vez cumplidos los 14 días y sin incidencias
  graves, promocionar la build de la pista de pruebas a producción.
- [ ] Verificar tras la publicación que la ficha pública de Play Store
  muestra correctamente icono, capturas y descripción.
- [ ] Documentar en `PROGRESS.md`/`README` el flujo de actualización futuro:
  **las actualizaciones normales de la PWA (cambios de Flask/Jinja/CSS) no
  requieren volver a subir nada a Play** — se despliegan en Railway como
  siempre y la TWA las refleja al instante. Solo hace falta generar y subir
  un nuevo `.aab` si cambia el propio shell nativo (nombre de paquete,
  versión mínima de Android, configuración de Bubblewrap, etc.), algo poco
  frecuente.
- [ ] Añadir un recordatorio de mantenimiento: revisar periódicamente que el
  `targetSdkVersion` de la TWA cumple los requisitos vigentes de Google Play
  (Google exige subir el target SDK a la versión de Android más reciente
  aproximadamente una vez al año).

---

## Notas de ejecución

### Fase 1 — Auditoría Lighthouse PWA (2026-07-28)

- Ejecutada con `npx lighthouse@10` (la v13 instalada por defecto ya no
  incluye la categoría `pwa`, Google la eliminó del core de Lighthouse en
  versiones recientes — hay que fijar `lighthouse@10` o similar para repetir
  esta auditoría en el futuro) contra `https://staging.turnero.xyz/`.
- **Puntuación categoría PWA: 1.0 / 1.0 (100%)**. Todos los checks pasan:
  manifest + service worker cumplen los requisitos de instalabilidad, SW
  registrado y controla `start_url`, splash screen configurada, theme color
  del address bar definido, viewport correcto, e icono maskable presente.
  El resto de categorías (informativas, no puntúan la PWA): performance
  0.98, accessibility 0.95, best-practices 0.96, seo 0.91.
- Informe completo guardado en
  `docs/audits/lighthouse-pwa-staging-2026-07-28.html`.

### Fase 1 — Verificación de zona segura maskable (2026-07-28)

- Analizados `icon-192.png` e `icon-512.png` con un script Python/Pillow que
  compara el bounding box del contenido "importante" (la ilustración blanca:
  personas + tarjetas de turno) frente al margen del 10% que exige la zona
  segura maskable. La ilustración en sí **sí** respetaba ese margen (bbox
  dentro del rango 10%-90% del lienzo en ambos tamaños).
- Sin embargo, el fondo azul (el cuadrado redondeado que debe cubrir el
  icono de borde a borde en un icono maskable) **no llegaba hasta el borde**:
  tenía un halo/sombra blanco de ~2.5% de margen alrededor en los dos
  tamaños. Esto es un defecto real para maskable — cuando Android recorta el
  icono con una máscara (círculo, squircle, etc.) que sí toca los bordes del
  lienzo, ese halo blanco se ve en los puntos cardinales, dando un resultado
  inconsistente.
- Corregido regenerando ambos PNG: se rellenó el anillo exterior (margen de
  32 px en el de 512 y 12 px en el de 192, calibrado para quedar justo por
  fuera del redondeo de esquina original) con el mismo azul sólido del
  cuadrado, dejando intacta la ilustración interior píxel a píxel. Resultado:
  fondo azul de borde a borde sin transparencia ni halo, ilustración dentro
  del 80% central. Sin cambios en `badge-72.png` (no está declarado
  `maskable` en el manifest).

### Fase 1 — Página offline (2026-07-28)

- Añadida la ruta pública `/offline` (`app/routes/pwa.py`) con plantilla
  autocontenida `app/templates/main/offline.html` (estilos inline, sin
  depender de `main.css`) para que se muestre igual aunque la caché de
  estáticos no esté disponible.
- `app/static/sw.js` ahora precachea `/offline` junto a `/` y, en el
  `fetch` handler, si una petición de navegación (`event.request.mode ===
  'navigate'`) falla sin red y no hay una versión cacheada de esa URL
  concreta, sirve la página offline precacheada como fallback.
- Tests añadidos en `tests/test_pwa.py`: disponibilidad de `/offline` (200,
  `text/html`) y que `sw.js` referencia `/offline` para precache.

### Fase 1 — Colores del manifest y contenido mixto (2026-07-28)

- `theme_color` (`#2563eb`) coincide con el azul primario usado en toda la
  interfaz: `meta[name=theme-color]` en `base.html` y decenas de reglas en
  `app/static/css/main.css` (acentos, bordes, badges, focus) usan el mismo
  valor. `background_color` (`#ffffff`) es el fondo estándar de splash screen
  para TWAs; el `body` de la app usa `#f5f5f5` (gris muy claro) pero el
  contenido (tarjetas, cabecera) es blanco, así que no hay discrepancia
  perceptible en el arranque. No fue necesario ningún cambio.
- Revisado `app/templates` y `app/static` en busca de `src="http://`,
  `href="http://` o `url(http://` — sin resultados. Ninguna página carga
  contenido mixto; no fue necesario ningún cambio.

Con esto se completa la **Fase 1** del plan.

### Fase 2 — Dominio estable de producción (2026-07-28)

- Dominio definitivo: **`app.turnero.xyz`**. Configurado como custom domain en
  Railway con certificado TLS automático, en producción desde ~2026-07-14 sin
  incidencias.
- `/manifest.json` y `/sw.js` responden 200 con los content-types correctos
  desde `https://app.turnero.xyz`. `APP_BASE_URL` en Railway está seteado a
  `https://app.turnero.xyz`.
- Todas las referencias antiguas al placeholder `tu-app.railway.app` en el
  repo han sido actualizadas: `.env.example` (`APP_URL`) y
  `scripts/smoke_test.py` (docstrings) apuntan ahora al dominio definitivo.

Con esto se completa la **Fase 2** del plan.

### Fase 3 — Páginas legales (2026-07-28)

- Añadidas tres rutas públicas (sin login) en `app/routes/main.py`:
  `/privacidad`, `/terminos` y `/eliminar-cuenta`, con sus plantillas en
  `app/templates/main/` (`privacidad.html`, `terminos.html`,
  `eliminar_cuenta.html`). Todo el texto marcado con `_()`.
- Política de Privacidad: detalla los datos recogidos (nombre, email,
  categoría profesional, unidad/grupo, turnos, firma digital), la finalidad,
  el tiempo de conservación (anonimización inmediata al eliminar la cuenta,
  conservación mínima de intercambios ya confirmados) y los terceros
  implicados (Railway para hosting, Resend para email — sin cesión ni venta
  comercial de datos). Recoge los derechos RGPD (acceso, rectificación,
  supresión) enlazando al formulario de contacto (`feedback.nuevo`) y a la
  página de eliminación de cuenta.
- Términos de Uso: uso adecuado del servicio (identidad real, ofertas de
  turno reales, ningún cierre automático sin confirmación de todas las
  partes) y aviso de que la validez final de un cambio queda sujeta a las
  normas internas del centro/aprobación de la supervisora.
- Eliminación de cuenta: mecanismo dual — usuarias con acceso a su cuenta se
  autogestionan la baja desde el perfil (`auth.eliminar_cuenta_route`, ya
  existente); usuarias sin acceso usan el formulario público de contacto
  (`feedback.nuevo`), con compromiso de eliminación/anonimización en un
  plazo máximo de 30 días.
- Enlazadas las tres páginas desde el pie de página (`base.html`) y desde el
  formulario de registro (`auth/registro.html`, aviso legal antes del botón
  de enviar).
- Catálogo de traducción (`translations/es/LC_MESSAGES/messages.po`)
  regenerado con `pybabel extract`/`update`/`compile` para incluir las
  cadenas nuevas.
- Tests: `tests/test_paginas_legales.py` (3 tests, verifican 200 +
  `text/html` en las tres rutas nuevas).

Con esto se completa la **Fase 3** del plan.

### Fase 4 — Generacion del paquete Android TWA (2026-07-28)

- **Package name:** `xyz.turnero.app` (definitivo, reverse-domain de `turnero.xyz`).
- **Bubblewrap CLI:** instalado globalmente (`npm i -g @bubblewrap/cli`).
  Configuracion en `~/.bubblewrap/config.json` con JDK 17 en
  `/usr/lib/jvm/java-17-openjdk-amd64`. Android SDK disponible en
  `~/Android/Sdk` con build-tools 35.0.0 y platform android-35.
- **Proyecto TWA:** `android-twa/twa-manifest.json` creado con la configuracion
  completa: host `app.turnero.xyz`, colores `#2563eb`/`#ffffff`, display
  standalone, iconos desde el dominio de produccion.
- **Digital Asset Links:** ruta `/.well-known/assetlinks.json` servida desde
  `app/routes/pwa.py`, fichero estatico en
  `app/static/.well-known/assetlinks.json` con package name
  `xyz.turnero.app`. Las huellas SHA-256 son placeholders: hay que reemplazar
  con la huella del upload key (tras generarlo) y la de Play App Signing (tras
  el primer envio a Play Console, Fase 5).
- **Keystore:** generado en `~/upload-keystore.jks` con alias `turnero`.
  Copiado a `android-twa/android-keystore.jks` (no commiteado al repo).
- **App Bundle compilado:** `android-twa/app-release-bundle.aab` (2.1 MB).
  Generado con `bubblewrap build` usando las password envars
  `BUBBLEWRAP_KEYSTORE_PASSWORD` / `BUBBLEWRAP_KEY_PASSWORD`.
- **Huella SHA-256 del upload key:** `CA:CC:BE:4C:16:D5:A1:88:45:74:71:BC:04:5A:10:E2:7C:6C:AF:2F:A6:F8:4F:78:1B:58:47:E3:8B:3B:24:87`
  - Añadida a `app/static/.well-known/assetlinks.json`.
  - Falta añadir la huella de Play App Signing (tras primer subida a Play Console, Fase 5).
- **Nota:** fue necesario añadir `"enableNotifications": false` al
  `twa-manifest.json` para que el build no fallase por un valor vacio en el
  `build.gradle` generado.
- **Pendiente:**
  - Verificar assetlinks con la herramienta de Google antes de subir el `.aab`.

### Fase 5 — Ficha de Play Console (2026-07-29)

- **Subida a pista interna:** completada por el usuario (el `.aab` de la
  Fase 4 ya está en una pista interna en Play Console).
- **Capturas de pantalla:** generadas con Playwright contra un servidor local
  con datos sintéticos (no staging/producción), reutilizando el golden path
  de `e2e/test_sintetica_golden_path.py`. Script nuevo:
  `e2e/test_screenshots_play_store.py`. 7 capturas 1080×2160 (ratio 2:1,
  dentro de los límites de Google) en `docs/store-assets/screenshots/`.
- **Feature graphic:** generado con Pillow a partir de `store_icon.png` +
  color de marca, en `docs/store-assets/feature_graphic.png` (1024×500).
- **Copy de la ficha:** título, descripción corta y completa, borrador de
  respuestas para IARC, Data safety y target audience, todo en
  `docs/store-assets/ficha_play_store.md`. Estos campos son formularios web
  de Play Console — no automatizables desde aquí — así que el documento
  sirve para copiar/pegar.
- **Pendiente / bloqueado:** falta decidir cómo crear la cuenta de demo de
  producción para las notas del revisor (`DEMO_LOGIN_EMAIL`/
  `DEMO_LOGIN_PASSWORD` no configuradas en Railway producción). Es una
  acción sobre datos de producción, así que se deja pendiente de decisión
  del usuario en vez de crearla unilateralmente.
- **Aún requiere acción humana en Play Console:** activar Play App Signing
  (en curso por el usuario) y luego añadir su huella SHA-256 a
  `assetlinks.json`; rellenar los formularios de IARC, Data safety, target
  audience, enlace de privacidad y "sin anuncios" (contenido ya redactado,
  solo falta transcribirlo en la consola).
