-- ================================================================
-- Аналитические витрины (материализованные представления)
-- ================================================================
-- 1. Общая эффективность оборудования (OEE) с защитой от чрезмерных простоев
DROP MATERIALIZED VIEW IF EXISTS dm.dm_oee CASCADE;

CREATE MATERIALIZED VIEW dm.dm_oee AS
WITH availability AS (
    SELECT
        e.equipment_code,
        d.date_value,
        -- Ограничиваем суммарный простой 480 минутами, чтобы доступность не уходила в минус
        GREATEST(0, (480.0 - LEAST(COALESCE(SUM(s.duration_min), 0), 480.0))) / 480.0 * 100 AS availability_pct
    FROM dwh.hub_equipment e
    CROSS JOIN dwh.hub_date d
    LEFT JOIN dwh.lnk_downtime lnk
        ON lnk.equipment_hash_key = e.equipment_hash_key
        AND lnk.date_hash_key = d.date_hash_key
    LEFT JOIN dwh.sat_downtime_metric s ON lnk.link_hash_key = s.link_hash_key
    WHERE d.date_value BETWEEN '2024-01-01' AND CURRENT_DATE
    GROUP BY e.equipment_code, d.date_value
),
performance AS (
    SELECT
        e.equipment_code,
        d.date_value,
        CASE
            WHEN SUM(s.cycle_time_sec) > 0 THEN
                (SUM(s.actual_qty) * 1.0 / NULLIF(SUM(s.cycle_time_sec), 0)) * 100
            ELSE 0
        END AS performance_pct
    FROM dwh.hub_equipment e
    JOIN dwh.lnk_production_operation lnk ON lnk.equipment_hash_key = e.equipment_hash_key
    JOIN dwh.hub_date d ON lnk.date_hash_key = d.date_hash_key
    JOIN dwh.sat_production_metric s ON lnk.link_hash_key = s.link_hash_key
    WHERE d.date_value BETWEEN '2024-01-01' AND CURRENT_DATE
    GROUP BY e.equipment_code, d.date_value
),
quality AS (
    SELECT
        e.equipment_code,
        d.date_value,
        CASE
            WHEN SUM(s.checked_qty) > 0 THEN
                (1.0 - SUM(s.defect_qty)::NUMERIC / NULLIF(SUM(s.checked_qty), 0)) * 100
            ELSE 100
        END AS quality_pct
    FROM dwh.hub_equipment e
    JOIN dwh.lnk_quality_event lnk ON lnk.equipment_hash_key = e.equipment_hash_key
    JOIN dwh.hub_date d ON lnk.date_hash_key = d.date_hash_key
    JOIN dwh.sat_quality_metric s ON lnk.link_hash_key = s.link_hash_key
    WHERE d.date_value BETWEEN '2024-01-01' AND CURRENT_DATE
    GROUP BY e.equipment_code, d.date_value
)
SELECT
    a.date_value,
    a.equipment_code,
    ROUND(a.availability_pct, 2) AS availability_pct,
    ROUND(p.performance_pct, 2) AS performance_pct,
    ROUND(q.quality_pct, 2) AS quality_pct,
    ROUND((a.availability_pct * p.performance_pct * q.quality_pct) / 10000.0, 2) AS oee_pct
FROM availability a
JOIN performance p ON a.equipment_code = p.equipment_code AND a.date_value = p.date_value
JOIN quality q ON a.equipment_code = q.equipment_code AND a.date_value = q.date_value;

-- 2. Надёжность оборудования (MTBF / MTTR)
DROP MATERIALIZED VIEW IF EXISTS dm.dm_mtbf_mttr CASCADE;

CREATE MATERIALIZED VIEW dm.dm_mtbf_mttr AS
WITH failure_events AS (
    SELECT
        e.equipment_code,
        d.date_value,
        SUM(s.duration_min) AS total_downtime_min,
        COUNT(*) AS failure_count
    FROM dwh.hub_equipment e
    JOIN dwh.lnk_downtime lnk ON lnk.equipment_hash_key = e.equipment_hash_key
    JOIN dwh.hub_date d ON lnk.date_hash_key = d.date_hash_key
    JOIN dwh.sat_downtime_metric s ON lnk.link_hash_key = s.link_hash_key
    WHERE NOT s.is_planned
    GROUP BY e.equipment_code, d.date_value
)
SELECT
    equipment_code,
    date_value,
    CASE WHEN failure_count > 0 THEN (480.0 - total_downtime_min) / failure_count ELSE NULL END AS mtbf_min,
    CASE WHEN failure_count > 0 THEN total_downtime_min::NUMERIC / failure_count ELSE NULL END AS mttr_min
FROM failure_events;

-- 3. Витрина качества (FPY и анализ дефектов)
DROP MATERIALIZED VIEW IF EXISTS dm.dm_quality CASCADE;

CREATE MATERIALIZED VIEW dm.dm_quality AS
SELECT
    d.date_value,
    e.equipment_code,
    sat.defect_type,
    SUM(sat.checked_qty) AS checked_qty,
    SUM(sat.defect_qty) AS defect_qty,
    CASE WHEN SUM(sat.checked_qty) > 0 THEN
        (1.0 - SUM(sat.defect_qty)::NUMERIC / SUM(sat.checked_qty)) * 100
    ELSE 100 END AS fpy_pct
FROM dwh.sat_quality_metric sat
JOIN dwh.lnk_quality_event lnk ON sat.link_hash_key = lnk.link_hash_key
JOIN dwh.hub_equipment e ON lnk.equipment_hash_key = e.equipment_hash_key
JOIN dwh.hub_date d ON lnk.date_hash_key = d.date_hash_key
GROUP BY d.date_value, e.equipment_code, sat.defect_type;

-- 4. Витрина простоев (материализованное представление)
DROP MATERIALIZED VIEW IF EXISTS dm.dm_downtime CASCADE;

CREATE MATERIALIZED VIEW dm.dm_downtime AS
SELECT
    d.date_value,
    e.equipment_code,
    sat_e.equipment_name,
    sat_e.workshop_code,
    s.reason_code,
    SUM(s.duration_min)::int AS total_downtime_min,
    bool_or(s.is_planned) AS is_planned,
    COUNT(*)::int AS event_count
FROM dwh.lnk_downtime lnk
JOIN dwh.hub_equipment e ON lnk.equipment_hash_key = e.equipment_hash_key
JOIN dwh.hub_date d ON lnk.date_hash_key = d.date_hash_key
JOIN dwh.sat_downtime_metric s ON lnk.link_hash_key = s.link_hash_key
LEFT JOIN dwh.sat_equipment_details sat_e
    ON e.equipment_hash_key = sat_e.equipment_hash_key
    AND sat_e.is_current = TRUE
GROUP BY d.date_value, e.equipment_code, sat_e.equipment_name, sat_e.workshop_code, s.reason_code;