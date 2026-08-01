# Ficha de Play Store — Turnero

Contenido de referencia para rellenar Play Console (Fase 5 de
`docs/PLAN_PLAY_STORE.md`). Los campos de formulario en Play Console son
manuales (solo accesibles desde la consola web), así que este documento
recoge el texto ya redactado para copiar/pegar.

## Recursos gráficos

- **Icono 512×512**: `android-twa/store_icon.png` (ya cumple el requisito,
  confirmado 512×512 PNG).
- **Feature graphic 1024×500**: `docs/store-assets/feature_graphic.png`
  (generado a partir del icono + color de marca `#2563eb`).
- **Capturas de pantalla de teléfono** (7, 1080×2160, ratio 2:1):
  `docs/store-assets/screenshots/01_dashboard.png` … `07_dashboard_match_3_bandas.png`.
  Generadas con Playwright reutilizando el golden path de
  `e2e/test_sintetica_golden_path.py` (script:
  `e2e/test_screenshots_play_store.py`, contra un servidor local con datos
  sintéticos — no toca staging ni producción). Google exige un mínimo de 2;
  se recomienda subir al menos 4-5 para mostrar el flujo completo (calendario,
  aviso de oportunidad, búsqueda de cambios, match a 3 bandas).

## Título (máx. 30 caracteres)

```
Turnero: cambio de turnos
```

## Descripción corta (máx. 80 caracteres)

```
Intercambia turnos con tus compañeros de forma fácil y segura
```

## Descripción completa

```
Turnero es la app para que el personal sanitario intercambie turnos con sus
compañeros de la misma categoría profesional y unidad, de forma rápida,
ordenada y sin tener que depender de grupos de WhatsApp o notas en papel.

Cómo funciona:
• Publica los turnos que quieres ceder y los que te vendrían bien a cambio.
• La app busca automáticamente coincidencias con las publicaciones de tus
  compañeros de la misma unidad y categoría.
• Recibe avisos cuando aparece un cambio que te interesa, incluidas
  oportunidades de cambios encadenados entre varias personas.
• Confirma el cambio con un solo toque: ningún cambio se cierra sin que
  todas las partes lo confirmen.
• Consulta tu calendario de turnos y el estado de tus cambios en cualquier
  momento, desde el móvil.

Turnero no sustituye la validez interna de los cambios de turno: la
aprobación final sigue las normas de tu hospital y de tu supervisor/a
habituales. La app solo facilita ponerse de acuerdo entre compañeros.

Pensada para instalarse como una app más en tu móvil, funciona directamente
desde el navegador sin ocupar apenas espacio.
```

## Cuestionario de clasificación de contenido (IARC) — respuestas orientativas

App de gestión/productividad para uso profesional (personal sanitario).
No contiene: violencia, contenido sexual, lenguaje soez, sustancias
controladas, apuestas, contenido generado por usuarios de tipo público
(las publicaciones de turnos solo son visibles dentro de la misma unidad/
categoría, no son un foro abierto), ni interacción social no moderada con
desconocidos. Resultado esperado: clasificación PEGI 3 / "Para todos los
públicos".

## Data safety (seguridad de los datos)

- **Datos que se recogen**: nombre, email, categoría profesional, hospital/
  unidad, turnos de trabajo (fechas y franjas), firma digital de
  confirmación de cambios.
- **Finalidad**: exclusivamente para el funcionamiento del servicio
  (identificación, emparejamiento de cambios de turno, notificaciones).
- **Cifrado en tránsito**: sí, toda la comunicación es HTTPS.
- **Eliminación de datos**: el usuario puede eliminar su cuenta y sus datos
  en cualquier momento desde `/perfil/cuenta` (autoservicio) o solicitándolo
  mediante el formulario de contacto público, ver
  `https://app.turnero.xyz/eliminar-cuenta`. Compromiso de eliminación o
  anonimización en un máximo de 30 días.
- **Comparte datos con terceros**: no, no se venden ni se comparten datos
  con terceros con fines publicitarios o comerciales. Se usan proveedores
  de infraestructura (hosting en Railway, envío de emails transaccionales
  vía Resend) exclusivamente como encargados del tratamiento.
- **Política de privacidad**: `https://app.turnero.xyz/privacidad`.

## Público objetivo y contenido para familias

- La app **no está dirigida a niños** ni a audiencias familiares: es una
  herramienta de uso profesional para personal sanitario adulto.
- Target audience: mayores de edad (18+), uso profesional.
- No hay contenido inapropiado para ningún grupo de edad; simplemente no es
  relevante ni accesible sin pertenecer a una organización sanitaria.

## Anuncios

La app **no contiene anuncios**.

## Enlaces

- Política de privacidad: `https://app.turnero.xyz/privacidad`
- Términos de uso: `https://app.turnero.xyz/terminos`
- Eliminación de cuenta: `https://app.turnero.xyz/eliminar-cuenta`

## Notas para el equipo de revisión (pendiente)

Falta decidir y crear una **cuenta de demo en producción** para que el
equipo de revisión de Google pueda acceder a las pantallas que requieren
login. `config.py` ya soporta `DEMO_LOGIN_EMAIL`/`DEMO_LOGIN_PASSWORD` (y
las variantes `DEMO_SUPERVISORA_*`) vía variables de entorno, pero
**no están configuradas en el entorno de producción de Railway todavía**.
Antes de crear una cuenta real en la base de datos de producción, confirmar
con el usuario del proyecto cómo prefiere proceder (cuenta dedicada de solo
lectura, hospital/unidad ficticios, etc.), ya que es una acción sobre datos
de producción.
