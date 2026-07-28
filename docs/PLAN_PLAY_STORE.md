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
- [ ] Añadir una página/fallback offline mínima en `app/static/sw.js` (p. ej.
  servir una página "sin conexión" cacheada cuando falla el `fetch` de
  navegación), con su test si aplica.
- [ ] Confirmar que `theme_color`/`background_color` del manifest
  (`app/routes/pwa.py`) coinciden con el diseño real de la app (actualmente
  `#2563eb` / `#ffffff`).
- [ ] Confirmar que todas las páginas relevantes cargan por HTTPS sin
  contenido mixto (http://) — revisar `app/templates` en busca de `src="http://`
  o similar.

## Fase 2 — Dominio estable de producción

- [ ] **[ACCIÓN HUMANA]** Decidir y confirmar el dominio definitivo de
  producción (candidato: `turnero.xyz` o un subdominio como `app.turnero.xyz`,
  ya reservado para email). Debe ser el mismo dominio para siempre: la TWA y
  el fichero `assetlinks.json` (Fase 4) quedan atados a él.
- [ ] **[ACCIÓN HUMANA]** Configurar el dominio elegido en Railway (dominio
  personalizado + certificado TLS automático) y verificar que resuelve y
  sirve la app por HTTPS.
- [ ] Actualizar `APP_BASE_URL` (ver `config.py`) y cualquier referencia a la
  URL de producción en el repo para usar el dominio definitivo.
- [ ] Verificar que `/manifest.json` y `/sw.js` se sirven correctamente desde
  el dominio definitivo (no solo desde el subdominio de Railway).

## Fase 3 — Aspectos legales obligatorios

- [ ] Escribir y publicar una página de **Política de Privacidad** (ruta
  pública, sin login, p. ej. `/privacidad`) que cubra: qué datos personales se
  recogen (nombre, email, categoría profesional, turnos, firma), con qué
  finalidad, cuánto tiempo se conservan, si se comparten con terceros
  (Resend para email, Railway para hosting), y los derechos RGPD del usuario
  (acceso, rectificación, supresión) dado el contexto español/UE.
- [ ] Escribir y publicar unos **Términos de Uso** básicos (ruta pública, p.
  ej. `/terminos`).
- [ ] Añadir una **página o mecanismo público de eliminación de cuenta**
  (accesible sin instalar la app, p. ej. `/eliminar-cuenta` con instrucciones
  o un formulario), tal y como exige la política de Google Play para apps con
  cuentas de usuario — puede ser tan simple como una dirección de contacto
  con un compromiso de plazo de borrado, pero tiene que ser una URL pública.
- [ ] Enlazar estas páginas desde el pie de página de la app (`base.html`) y
  desde el formulario de registro si existe.
- [ ] Marcar todos los textos nuevos con `_()`/`gettext` según la convención
  de i18n de `CLAUDE.md`.

## Fase 4 — Generar el paquete Android (TWA)

- [ ] **[ACCIÓN HUMANA]** Decidir el nombre de paquete Android (formato
  reverse-domain, p. ej. `xyz.turnero.app`) — es definitivo, no se puede
  cambiar después de publicar.
- [ ] Instalar y configurar [Bubblewrap CLI](https://github.com/GoogleChromeLabs/bubblewrap)
  (requiere Node.js + JDK) o usar [PWABuilder](https://www.pwabuilder.com/)
  como alternativa sin instalación local, apuntando al `manifest.json` del
  dominio definitivo de la Fase 2.
- [ ] Generar el proyecto Android TWA (`bubblewrap init --manifest=<url>`),
  revisando: nombre de la app, colores, orientación, `display: standalone`.
- [ ] **[ACCIÓN HUMANA]** Generar el *keystore* de firma (upload key) y
  **guardarlo con máxima seguridad y backup** (contraseña + fichero `.jks`) —
  perderlo impide publicar actualizaciones futuras de la app. No debe
  commitearse al repo.
- [ ] Compilar el Android App Bundle (`.aab`) con `bubblewrap build`.
- [ ] Publicar el fichero **Digital Asset Links** en
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
- [ ] Subir el `.aab` generado en la Fase 4 a una pista interna o cerrada
  inicial.
- [ ] **[ACCIÓN HUMANA]** Activar **Play App Signing** y, una vez Google
  genere su propia clave de firma, descargar la huella SHA-256 del
  certificado de Play desde *App integrity* y añadirla al
  `assetlinks.json` (Fase 4) junto a la del upload key.
- [ ] Preparar los recursos gráficos de la ficha de Play: icono de alta
  resolución (512×512 PNG), gráfico de funciones/feature graphic (1024×500),
  al menos 2 capturas de pantalla de teléfono (se pueden generar con
  Playwright, ya usado en `e2e/`, contra staging).
- [ ] Redactar título, descripción corta (80 car.) y descripción completa de
  la ficha de la app, en español.
- [ ] Rellenar el **cuestionario de clasificación de contenido** (IARC).
- [ ] Rellenar la sección **Data safety** (seguridad de los datos):
  declarar qué datos se recogen (identificación, datos laborales/turnos),
  si se cifran en tránsito (sí, HTTPS), si se pueden eliminar (enlazar la
  página de la Fase 3), y que no se comparten con terceros con fines
  publicitarios.
- [ ] Declarar **público objetivo y contenido para familias**: marcar que la
  app no está dirigida a niños (uso profesional/sanitario) y ajustar el
  target audience en consecuencia.
- [ ] Enlazar la **Política de Privacidad** (Fase 3) en el campo
  correspondiente de Play Console.
- [ ] Declarar que la app **no contiene anuncios** (si es el caso).
- [ ] Añadir en el campo de notas para el revisor las **credenciales de la
  cuenta de demo** de producción (Fase, ver Contexto técnico) para que el
  equipo de revisión de Google pueda acceder a las partes con login.

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

(Rellenar aquí, a medida que se ejecuten las fases: nombre de paquete
elegido, dominio definitivo, huellas SHA-256, URLs de listing, fecha de
inicio/fin de la pista de pruebas cerrada, etc.)

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
