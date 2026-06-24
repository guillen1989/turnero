-- Queries de funnel — tabla event
-- Ejecutar desde Railway: Data → Query


-- 1. Visión general del funnel
SELECT
  COUNT(*) FILTER (WHERE event_type = 'publication_created')  AS creadas,
  COUNT(*) FILTER (WHERE event_type = 'publication_cancelled') AS canceladas,
  COUNT(*) FILTER (WHERE event_type = 'match_found')           AS con_match,
  COUNT(*) FILTER (WHERE event_type = 'match_cancelled')       AS match_cancelado,
  COUNT(*) FILTER (WHERE event_type = 'match_confirmed')       AS confirmadas
FROM event;


-- 2. Tasa de conversión en cada paso
WITH counts AS (
  SELECT
    COUNT(*) FILTER (WHERE event_type = 'publication_created')  AS creadas,
    COUNT(*) FILTER (WHERE event_type = 'match_found')           AS con_match,
    COUNT(*) FILTER (WHERE event_type = 'match_cancelled')       AS match_cancelado,
    COUNT(*) FILTER (WHERE event_type = 'match_confirmed')       AS confirmadas
  FROM event
)
SELECT
  creadas,
  con_match,
  match_cancelado,
  confirmadas,
  ROUND(100.0 * con_match      / NULLIF(creadas,        0), 1) AS pct_match,
  ROUND(100.0 * match_cancelado / NULLIF(con_match,     0), 1) AS pct_rechazo,
  ROUND(100.0 * confirmadas    / NULLIF(con_match,      0), 1) AS pct_confirmacion
FROM counts;


-- 3. Tiempo medio desde publicación hasta match (en horas)
SELECT
  ROUND(AVG(EXTRACT(EPOCH FROM (m.created_at - p.created_at)) / 3600), 1) AS horas_hasta_match
FROM event p
JOIN event m ON m.entity_id = p.entity_id
           AND m.event_type = 'match_found'
           AND p.event_type = 'publication_created';


-- 4. Tasa de abandono: publicaciones canceladas sin haber tenido match
SELECT
  COUNT(*) FILTER (WHERE event_type = 'publication_cancelled')
    AS total_canceladas,
  COUNT(*) FILTER (WHERE event_type = 'publication_cancelled'
                     AND entity_id NOT IN (
                       SELECT entity_id FROM event WHERE event_type = 'match_found'
                     ))
    AS canceladas_sin_match,
  ROUND(100.0 *
    COUNT(*) FILTER (WHERE event_type = 'publication_cancelled'
                       AND entity_id NOT IN (
                         SELECT entity_id FROM event WHERE event_type = 'match_found'
                       ))
    / NULLIF(COUNT(*) FILTER (WHERE event_type = 'publication_cancelled'), 0), 1)
    AS pct_abandono
FROM event;


-- 5. Actividad semanal
SELECT
  DATE_TRUNC('week', created_at)                               AS semana,
  COUNT(*) FILTER (WHERE event_type = 'publication_created')   AS publicaciones,
  COUNT(*) FILTER (WHERE event_type = 'match_found')           AS matches,
  COUNT(*) FILTER (WHERE event_type = 'match_cancelled')       AS rechazos,
  COUNT(*) FILTER (WHERE event_type = 'match_confirmed')       AS turnos_cambiados
FROM event
GROUP BY 1
ORDER BY 1 DESC;
