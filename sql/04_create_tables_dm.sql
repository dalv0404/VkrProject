-- Витрины данных (Gold-слой)

CREATE TABLE IF NOT EXISTS dm.dm_order_kpi (
    date_value       DATE,
    order_code       VARCHAR(50),
    product_code     VARCHAR(50),
    planned_qty      NUMERIC,
    actual_qty       NUMERIC,
    on_time_rate     NUMERIC(5,2),
    delay_days       INT,
    PRIMARY KEY (date_value, order_code)
);

CREATE TABLE IF NOT EXISTS dm.targets (
    target_date     DATE PRIMARY KEY,
    planned_revenue NUMERIC,
    planned_cost    NUMERIC,
    planned_ros     NUMERIC(5,4)
);