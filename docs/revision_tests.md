# Plan de revisión de la suite de tests

## Objetivo
La suite tiene 131 archivos de test (~1600+ casos, contando parametrizaciones). Muchos de estos
tests se escribieron como parte del ciclo TDD (rojo-verde-refactor) que exige `CLAUDE.md`, lo que
produce cobertura fina de variantes intermedias que fueron útiles para *diseñar* el comportamiento
pero que no aportan valor como **suite de regresión** una vez el comportamiento está consolidado.

El objetivo de este plan es revisar cada archivo y **reducir su número de tests** dejando solo los
que sirven como regresión, comprobando en cada uno:
- Que el test sigue siendo necesario (no cubre código muerto ni comportamiento obsoleto).
- Que no hay duplicación evidente entre archivos (mismo escenario cubierto dos veces).
- Que el test aporta valor real: prueba comportamiento, no implementación de detalle.
- Que, si varios tests cubren variantes finas del mismo flujo (p. ej. combinaciones de flags,
  errores de validación equivalentes), pueden consolidarse en menos tests sin perder cobertura del
  camino feliz y de los bordes que realmente importan.
- Que los tests que sobreviven son legibles y su nombre describe honestamente qué comportamiento
  verifican.

Para lógica de negocio crítica (motor de matching, reglas de confirmación, resolución parcial,
visibilidad por categoría/grupo) prioriza mantener la granularidad: ahí el coste de un bug no
detectado es alto y la exhaustividad sigue aportando valor.

## Cómo trabajar este plan
- Cada fila de las tablas de abajo es **un paso independiente**: revisar y reducir un solo archivo
  de test.
- El paso sigue el ciclo TDD/commit atómico habitual (`CLAUDE.md`): con todos los tests en verde,
  elimina o fusiona los tests redundantes, comprueba que la suite del archivo sigue pasando y que
  la cobertura del comportamiento relevante se mantiene, y deja constancia del resultado.
- Al terminar un archivo, marca su casilla `[x]` y rellena la columna "Notas" con el veredicto y el
  recuento antes/después (ej. "18→11 tests: fusionadas 4 variantes de validación de email",
  "OK, sin cambios: cada test cubre un escenario distinto sin solape").
- Haz commit del código de test modificado junto con este archivo actualizado, tras cada archivo
  revisado (o cada pocos, si son triviales), para no perder progreso entre sesiones. Mensaje
  sugerido: `test: reduce tests/test_x.py a los necesarios para regresión (plan revisión tests)`.
- Si una reducción es dudosa (no está claro si un escenario sigue aportando valor), anótalo en
  "Notas" en vez de borrar, y decide con el usuario si se aborda ahora o se deja para después.
- El recuento de "Nº tests" es el número de funciones `def test_*` en el archivo (incluye tests
  parametrizados como una sola función) **antes** de empezar este plan. Sirve solo de referencia
  para priorizar/estimar tiempo.
- Progreso total: cuenta las casillas marcadas frente al total (131 archivos).

---

## 1. Autenticación, cuentas y usuarios
- [x] tests/test_auth_routes.py (86→81 tests) — Notas: fusionadas las variantes de botón de
  login demo repetidas en `/auth/login` y `/` (antes 5 tests separados por ruta, ahora 3 que
  iteran ambas rutas), eliminados 2 tests de elección trabajador/supervisora redundantes con
  los anteriores, y fusionados `test_registro_con_flag_inactivo_ignora_segunda_unidad` +
  `test_registro_con_flag_inactivo_no_crea_unidad_extra_ni_error` en un solo test. Suite
  verificada en verde (81 passed).
- [x] tests/test_recuperar_contrasena.py (13→8 tests) — Notas: fusionados los 3 tests que
  comprobaban distintos aspectos de la misma petición POST con email existente (envío de email,
  enlace con token, redirección al login) en un único test con varios asserts; fusionadas las 2
  variantes de contraseña inválida al restablecer (distintas / demasiado corta) en un test
  parametrizado; fusionado el GET del formulario con token válido dentro del test que hace el
  POST y cambia la contraseña (mismo flujo, un solo `_usuario()`+token); eliminado
  `test_login_enlaza_a_recuperar_contrasena_de_auth` por probar un detalle de plantilla (href en
  `/auth/login`) ajeno al comportamiento del propio flujo de recuperación. Suite verificada en
  verde (9 passed).
- [x] tests/test_password_reset_service.py (8→7 tests) — Notas: casi todos los tests cubren un
  escenario distinto de seguridad del token (expirado, usado, inexistente, invalidación de tokens
  previos) y se mantienen separados por criticidad. Solo se fusionaron
  `test_generar_token_reset_crea_fila_en_bd` y `test_generar_token_reset_no_guarda_el_token_en_claro`
  (mismo `generar_token_reset()`, dos asserts sobre la misma fila) en un único test. Suite
  verificada en verde (7 passed).
- [x] tests/test_invitacion.py (8→5 tests) — Notas: fusionados los 3 tests que comprobaban
  distintos aspectos del mismo enlace de invitación en `/auth/perfil/cuenta` (wa.me, URL de
  registro, IDs de hospital/unidad/categoría) en uno solo; fusionados los 2 tests que comprobaban
  `data-selected-hospital` y `data-selected-unidad` en la misma petición GET a `/registro` en uno
  solo. Los casos de país preseleccionado, sin invitación y con `inv_hospital` inexistente se
  mantienen separados por cubrir escenarios distintos. Suite verificada en verde (5 passed).
- [x] tests/test_eliminar_cuenta.py (13→9 tests) — Notas: fusionados
  `test_eliminar_cuenta_anonimiza_nombre_y_email` + `test_eliminar_cuenta_bloquea_login` en un
  solo test (misma llamada a `eliminar_cuenta()`, varios asserts); convertidos los 3 tests de
  estado de match (`rechaza_matches_propuestos`, `rechaza_matches_confirmados_parcialmente`,
  `no_toca_matches_ya_cerrados`) en un único test parametrizado con los 3 pares
  estado-inicial/estado-esperado (se mantiene la granularidad de casos, solo se concentra la
  función); fusionados `borra_suscripciones_como_suscriptor` + `borra_suscripciones_como_publicador`
  en un test que crea ambas suscripciones y comprueba las dos. Los tests de la ruta HTTP
  (autenticación requerida, password incorrecta, éxito, login bloqueado tras eliminar) cubren
  comportamientos distintos y se mantienen separados. Suite verificada en verde (11 tests, 13
  casos con la parametrización).
- [x] tests/test_unidad_usuario.py (7 tests) — Notas: OK, sin cambios. Cada test cubre una
  combinación distinta de flag/contexto (flag activo/inactivo, `unidad_id` explícito vs sesión vs
  ninguno, regresión de `pertenece_a`) sin solape.
- [x] tests/test_servicio_unidad_usuario.py (17→14 tests) — Notas: fusionados
  `pertenece_a_true_para_la_principal_y_las_membresias` + `pertenece_a_false_para_unidad_ajena` en
  un test; fusionados los 2 tests de `categoria_en_unidad` (principal/extra) en uno; fusionados
  `con_unidad_ajena_aborta` + `con_unidad_inexistente_aborta` de `unidad_activa_o_403` en un solo
  test (mismo `pytest.raises(Forbidden)`, dos disparadores). El resto de casos de
  `unidad_activa_o_403` y los 4 de `sincronizar_unidades` cubren comportamiento crítico distinto
  (prioridad query/sesión, invariantes de membresía) y se mantienen separados. Suite verificada en
  verde.
- [x] tests/test_servicio_registro.py (16→15 tests) — Notas: fusionados
  `test_reutiliza_hospital_existente` + `test_hospital_coincide_ignorando_mayusculas` en un test
  parametrizado (misma reutilización, dos variantes de casing). El resto de tests cubre casos
  distintos de find-or-create (unidad, categoría, registro completo, multi-unidad) sin solape.
  Suite verificada en verde.
- [x] tests/test_unidad_activa_rutas.py (16→10 tests) — Notas: el patrón "sin unidad_id usa la
  principal" / "con unidad_id válido cambia contexto" / "con unidad_id ajena → 403" estaba
  duplicado literalmente 3 veces (una por cada ruta: calendario, cambios, planilla). Convertidos
  en 3 tests parametrizados por endpoint (`RUTAS_CON_SELECTOR_DE_UNIDAD`), manteniendo la cobertura
  de las 3 rutas pero sin repetir el cuerpo del test. Los tests específicos de cada ruta (filtrado
  por categoría, franjas activas, sesión) se mantienen intactos. Suite verificada en verde.
- [x] tests/test_models_usuario.py (7 tests) — Notas: OK, sin cambios. Cada test cubre un
  comportamiento de modelo distinto (password hasheado, unicidad de email, flask-login,
  eliminación, firma) sin solape.
- [x] tests/test_models_usuario_unidad.py (4 tests) — Notas: OK, sin cambios. Cada test cubre un
  aspecto distinto de la relación usuario-unidad-categoría (ambas direcciones, categoría por
  membresía, constraint de duplicado).

## 2. Administración
- [ ] tests/test_admin.py (45 tests) — Notas:
- [ ] tests/test_admin_analytics.py (25 tests) — Notas:
- [ ] tests/test_admin_feature_flags.py (6 tests) — Notas:

## 3. Planillas / hojas de turno
- [ ] tests/test_compatibilidad_planilla.py (22 tests) — Notas:
- [ ] tests/test_servicio_planilla.py (27 tests) — Notas:
- [ ] tests/test_servicio_planilla_supervision.py (31 tests) — Notas:
- [ ] tests/test_servicio_planilla_matching.py (20 tests) — Notas:
- [ ] tests/test_rutas_planilla_supervision.py (40 tests) — Notas:
- [ ] tests/test_planilla_relleno.py (19 tests) — Notas:
- [ ] tests/test_planilla_multi_unidad.py (15 tests) — Notas:
- [ ] tests/test_planilla_rutas.py (11 tests) — Notas:
- [ ] tests/test_planilla_import.py (6 tests) — Notas:
- [ ] tests/test_planilla_modelo.py (6 tests) — Notas:
- [ ] tests/test_compat_planilla_persistente.py (9 tests) — Notas:
- [ ] tests/test_importar_planilla.py (4 tests) — Notas:
- [ ] tests/test_rutas_importar_planilla.py (20 tests) — Notas:
- [ ] tests/test_feature_flag_importacion_planilla.py (4 tests) — Notas:
- [ ] tests/test_feature_flag_planilla_supervision.py (4 tests) — Notas:
- [ ] tests/test_models_planilla_import.py (7 tests) — Notas:
- [ ] tests/test_compatibilidad_al_publicar.py (4 tests) — Notas:

## 4. Motor de matching
- [ ] tests/test_motor_matching.py (23 tests) — Notas:
- [ ] tests/test_servicio_matching.py (11 tests) — Notas:
- [ ] tests/test_combinaciones_match.py (10 tests) — Notas:
- [ ] tests/test_integracion_matching.py (5 tests) — Notas:
- [ ] tests/test_cadena_3.py (20 tests) — Notas:
- [ ] tests/test_cadena_4.py (20 tests) — Notas:
- [ ] tests/test_commits_matching.py (4 tests) — Notas:
- [ ] tests/test_rematch.py (3 tests) — Notas:
- [ ] tests/test_match_parcial.py (7 tests) — Notas:
- [ ] tests/test_match_labels.py (5 tests) — Notas:
- [ ] tests/test_matching_cambio_dia.py (5 tests) — Notas:

## 5. Documento de cambio
- [ ] tests/test_servicio_documento_cambio.py (51 tests) — Notas:
- [ ] tests/test_documento_cambio_creacion.py (22 tests) — Notas:
- [ ] tests/test_documento_cambio_supervision.py (20 tests) — Notas:
- [ ] tests/test_documento_cambio_firma.py (19 tests) — Notas:
- [ ] tests/test_documento_cambio_desde_match.py (11 tests) — Notas:
- [ ] tests/test_documento_cambio_bloque.py (9 tests) — Notas:
- [ ] tests/test_documento_cambio_registro_papel.py (8 tests) — Notas:
- [ ] tests/test_documento_cambio_multi_unidad.py (8 tests) — Notas:
- [ ] tests/test_documento_cambio_anular.py (7 tests) — Notas:
- [ ] tests/test_documento_cambio_lista.py (6 tests) — Notas:
- [ ] tests/test_documento_cambio_encadenadas.py (4 tests) — Notas:
- [ ] tests/test_documento_cambio_cambio_dia.py (2 tests) — Notas:
- [ ] tests/test_models_documento_cambio.py (15 tests) — Notas:
- [ ] tests/test_confirmar_con_documento.py (14 tests) — Notas:
- [ ] tests/test_anular_documento.py (11 tests) — Notas:

## 6. Cambio de turno en el día
- [ ] tests/test_cambio_dia_validacion.py (6 tests) — Notas:
- [ ] tests/test_publicar_cambio_dia.py (8 tests) — Notas:
- [ ] tests/test_factibilidad_cambio_dia.py (3 tests) — Notas:
- [ ] tests/test_servicio_factibilidad_documento_cambio.py (21 tests) — Notas:
- [ ] tests/test_supervision_cambio_dia.py (4 tests) — Notas:
- [ ] tests/test_volcado_cambio_dia.py (4 tests) — Notas:
- [ ] tests/test_volcar_cambios.py (15 tests) — Notas:

## 7. Publicaciones, turnos y calendario
- [ ] tests/test_publicar.py (18 tests) — Notas:
- [ ] tests/test_publicar_junte.py (8 tests) — Notas:
- [ ] tests/test_editar_eliminar_publicacion.py (21 tests) — Notas:
- [ ] tests/test_turnos_unidad.py (20 tests) — Notas:
- [ ] tests/test_cambios.py (26 tests) — Notas:
- [ ] tests/test_contraoferta.py (11 tests) — Notas:
- [ ] tests/test_aviso_interes.py (9 tests) — Notas:
- [ ] tests/test_me_interesa.py (19 tests) — Notas:
- [ ] tests/test_cancelar.py (6 tests) — Notas:
- [ ] tests/test_nota_dia.py (10 tests) — Notas:
- [ ] tests/test_junte_semanal.py (13 tests) — Notas:
- [ ] tests/test_calendario_mercado.py (32 tests) — Notas:
- [ ] tests/test_calendario_ruta.py (17 tests) — Notas:
- [ ] tests/test_calendario_semanas_juntes.py (8 tests) — Notas:
- [ ] tests/test_models_publicacion.py (5 tests) — Notas:
- [ ] tests/test_pub_sintetica.py (17 tests) — Notas:
- [ ] tests/test_sintetica_4.py (24 tests) — Notas:

## 8. Confirmación, notificaciones y caducidad
- [ ] tests/test_confirmacion.py (27 tests) — Notas:
- [ ] tests/test_notificaciones.py (27 tests) — Notas:
- [ ] tests/test_notificacion_unidad.py (8 tests) — Notas:
- [ ] tests/test_push.py (18 tests) — Notas:
- [ ] tests/test_push_count.py (6 tests) — Notas:
- [ ] tests/test_push_concurrencia.py (1 test) — Notas:
- [ ] tests/test_push_integracion.py (4 tests) — Notas:
- [ ] tests/test_email.py (6 tests) — Notas:
- [ ] tests/test_feedback.py (29 tests) — Notas:
- [ ] tests/test_eventos.py (7 tests) — Notas:
- [ ] tests/test_limpieza_matches.py (8 tests) — Notas:
- [ ] tests/test_caducidad.py (10 tests) — Notas:
- [ ] tests/test_caducidad_dashboard.py (1 test) — Notas:

## 9. Asistente (parser de WhatsApp)
- [ ] tests/test_asistente_cliente.py (13 tests) — Notas:
- [ ] tests/test_asistente_resolver.py (18 tests) — Notas:
- [ ] tests/test_asistente_route.py (13 tests) — Notas:
- [ ] tests/test_asistente_schema.py (6 tests) — Notas:
- [ ] tests/test_eval_parser.py (20 tests) — Notas:
- [ ] tests/test_anadir_fecha_mensaje.py (3 tests) — Notas:
- [ ] tests/test_anonimizar_corpus.py (7 tests) — Notas:
- [ ] tests/test_generar_plantilla_corpus.py (6 tests) — Notas:

## 10. Feature flags
- [ ] tests/test_servicio_feature_flags.py (7 tests) — Notas:
- [ ] tests/test_feature_flag_hoja_cambio_digital.py (4 tests) — Notas:
- [ ] tests/test_integracion_feature_flags.py (5 tests) — Notas:
- [ ] tests/test_models_feature_flag.py (3 tests) — Notas:
- [ ] tests/test_models_feature_flag_unidad.py (3 tests) — Notas:

## 11. Modelos de dominio (sin categoría propia)
- [ ] tests/test_models_categoria_franja.py (7 tests) — Notas:
- [ ] tests/test_models_hospital_unidad.py (8 tests) — Notas:
- [ ] tests/test_models_match.py (4 tests) — Notas:
- [ ] tests/test_models_unidad_supervisada.py (3 tests) — Notas:

## 12. Supervisión
- [ ] tests/test_servicio_supervision.py (13 tests) — Notas:

## 13. Dashboards y UI / PWA
- [ ] tests/test_dashboard.py (37 tests) — Notas:
- [ ] tests/test_busquedas_guardadas.py (36 tests) — Notas:
- [ ] tests/test_landing.py (7 tests) — Notas:
- [ ] tests/test_nav_base.py (2 tests) — Notas:
- [ ] tests/test_onboarding.py (8 tests) — Notas:
- [ ] tests/test_pwa.py (11 tests) — Notas:
- [ ] tests/test_pwa_frontend.py (4 tests) — Notas:
- [ ] tests/test_paginas_legales.py (3 tests) — Notas:
- [ ] tests/test_latencia_editar.py (4 tests) — Notas:
- [ ] tests/test_pdf_junte_frames.py (3 tests) — Notas:

## 14. Sembrado de datos (seed)
- [ ] tests/test_seed_staging_rota.py (6 tests) — Notas:
- [ ] tests/test_seed_staging_uco.py (13 tests) — Notas:

## 15. Infraestructura, i18n y misceláneos
- [ ] tests/test_db_timing.py (7 tests) — Notas:
- [ ] tests/test_i18n.py (3 tests) — Notas:
- [ ] tests/test_smoke.py (17 tests) — Notas:
- [ ] tests/test_demo.py (23 tests) — Notas:
- [ ] tests/test_main.py (1 test) — Notas:
- [ ] tests/test_flujos_criticos.py (5 tests) — Notas:
- [ ] tests/test_reglas_comprobacion.py (8 tests) — Notas:

---

## Notas / decisiones pendientes
- Plan generado el 2026-08-28 a partir de un recuento estático (`grep -c "^def test_"`), sin ejecutar
  la suite. El número de "Nº tests" no cuenta variantes de `@pytest.mark.parametrize` como tests
  separados — la cifra real de casos ejecutados (~1600) es mayor que la suma de estas cifras.
  Si conviene refinar la estimación, usar `pytest --collect-only -q | tail -1`.
- Este documento es de solo seguimiento de revisión. Las acciones concretas que surjan de una
  revisión (borrar test, fusionar archivos, etc.) se implementan como pasos de trabajo aparte,
  siguiendo el ciclo TDD/commits atómicos habitual del proyecto (ver `CLAUDE.md`), no dentro de
  este plan.
