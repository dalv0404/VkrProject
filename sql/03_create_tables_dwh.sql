-- ================================================================
-- Ядро хранилища (Silver-слой) – Data Vault 2.0
-- ================================================================

-- 1. Хабы (Hubs)
CREATE TABLE dwh.hub_date (
    date_hash_key CHAR(32) PRIMARY KEY,
    date_value    DATE NOT NULL UNIQUE,
    day_of_week   SMALLINT,
    week_of_year  SMALLINT,
    month         SMALLINT,
    quarter       SMALLINT,
    year          SMALLINT,
    is_holiday    BOOLEAN DEFAULT FALSE
);

CREATE TABLE dwh.hub_equipment (
    equipment_hash_key CHAR(32) PRIMARY KEY,
    equipment_code     TEXT NOT NULL UNIQUE,
    load_date          TIMESTAMP NOT NULL DEFAULT NOW(),
    source_system      TEXT NOT NULL
);

CREATE TABLE dwh.hub_order (
    order_hash_key CHAR(32) PRIMARY KEY,
    order_code     TEXT NOT NULL UNIQUE,
    load_date      TIMESTAMP NOT NULL DEFAULT NOW(),
    source_system  TEXT NOT NULL
);

CREATE TABLE dwh.hub_employee (
    employee_hash_key CHAR(32) PRIMARY KEY,
    employee_code     TEXT NOT NULL UNIQUE,
    load_date         TIMESTAMP NOT NULL DEFAULT NOW(),
    source_system     TEXT NOT NULL
);

CREATE TABLE dwh.hub_defect_type (
    defect_type_hash_key CHAR(32) PRIMARY KEY,
    defect_code          TEXT NOT NULL UNIQUE,
    load_date            TIMESTAMP NOT NULL DEFAULT NOW(),
    source_system        TEXT NOT NULL
);

CREATE TABLE dwh.hub_material (
    material_hash_key CHAR(32) PRIMARY KEY,
    material_code     TEXT NOT NULL UNIQUE,
    load_date         TIMESTAMP NOT NULL DEFAULT NOW(),
    source_system     TEXT NOT NULL
);

-- 2. Связи (Links)
CREATE TABLE dwh.lnk_production_operation (
    link_hash_key      CHAR(32) PRIMARY KEY,
    order_hash_key     CHAR(32) NOT NULL REFERENCES dwh.hub_order(order_hash_key),
    equipment_hash_key CHAR(32) NOT NULL REFERENCES dwh.hub_equipment(equipment_hash_key),
    employee_hash_key  CHAR(32) NOT NULL REFERENCES dwh.hub_employee(employee_hash_key),
    date_hash_key      CHAR(32) NOT NULL REFERENCES dwh.hub_date(date_hash_key),
    load_date          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE dwh.lnk_quality_event (
    link_hash_key       CHAR(32) PRIMARY KEY,
    order_hash_key      CHAR(32) NOT NULL REFERENCES dwh.hub_order(order_hash_key),
    equipment_hash_key  CHAR(32) NOT NULL REFERENCES dwh.hub_equipment(equipment_hash_key),
    defect_type_hash_key CHAR(32) NOT NULL REFERENCES dwh.hub_defect_type(defect_type_hash_key),
    date_hash_key       CHAR(32) NOT NULL REFERENCES dwh.hub_date(date_hash_key),
    load_date           TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE dwh.lnk_downtime (
    link_hash_key      CHAR(32) PRIMARY KEY,
    equipment_hash_key CHAR(32) NOT NULL REFERENCES dwh.hub_equipment(equipment_hash_key),
    date_hash_key      CHAR(32) NOT NULL REFERENCES dwh.hub_date(date_hash_key),
    load_date          TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE dwh.lnk_maintenance (
    link_hash_key      CHAR(32) PRIMARY KEY,
    equipment_hash_key CHAR(32) NOT NULL REFERENCES dwh.hub_equipment(equipment_hash_key),
    date_hash_key      CHAR(32) NOT NULL REFERENCES dwh.hub_date(date_hash_key),
    load_date          TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 3. Сателлиты (Satellites)
-- Описательные атрибуты оборудования
CREATE TABLE dwh.sat_equipment_details (
    equipment_hash_key CHAR(32) NOT NULL REFERENCES dwh.hub_equipment(equipment_hash_key),
    load_date          TIMESTAMP NOT NULL DEFAULT NOW(),
    valid_from         DATE NOT NULL,
    is_current         BOOLEAN NOT NULL DEFAULT TRUE,
    equipment_name     TEXT,
    equipment_group    TEXT,
    workshop_code      TEXT,
    ideal_cycle_sec    NUMERIC,   -- для расчёта Performance
    PRIMARY KEY (equipment_hash_key, load_date)
);

-- Атрибуты заказа
CREATE TABLE dwh.sat_order_details (
    order_hash_key CHAR(32) NOT NULL REFERENCES dwh.hub_order(order_hash_key),
    load_date      TIMESTAMP NOT NULL DEFAULT NOW(),
    planned_qty    NUMERIC,
    product_code   TEXT,
    planned_start  DATE,
    planned_end    DATE,
    status         TEXT,
    PRIMARY KEY (order_hash_key, load_date)
);

-- Метрики производственных операций
CREATE TABLE dwh.sat_production_metric (
    link_hash_key  CHAR(32) NOT NULL REFERENCES dwh.lnk_production_operation(link_hash_key),
    load_date      TIMESTAMP NOT NULL DEFAULT NOW(),
    planned_qty    NUMERIC,
    actual_qty     NUMERIC,
    cycle_time_sec NUMERIC,
    PRIMARY KEY (link_hash_key, load_date)
);

-- Метрики простоев
CREATE TABLE dwh.sat_downtime_metric (
    link_hash_key CHAR(32) NOT NULL REFERENCES dwh.lnk_downtime(link_hash_key),
    load_date     TIMESTAMP NOT NULL DEFAULT NOW(),
    reason_code   VARCHAR(20) NOT NULL,
    duration_min  INT NOT NULL CHECK (duration_min > 0),
    is_planned    BOOLEAN NOT NULL DEFAULT FALSE,
    description   TEXT,
    PRIMARY KEY (link_hash_key, load_date)
);

-- Метрики контроля качества
CREATE TABLE dwh.sat_quality_metric (
    link_hash_key CHAR(32) NOT NULL REFERENCES dwh.lnk_quality_event(link_hash_key),
    load_date     TIMESTAMP NOT NULL DEFAULT NOW(),
    checked_qty   INT NOT NULL,
    defect_qty    INT NOT NULL DEFAULT 0,
    defect_type   VARCHAR(20),
    PRIMARY KEY (link_hash_key, load_date)
);

-- Заполнение календаря (2024-2027)
INSERT INTO dwh.hub_date (date_hash_key, date_value, day_of_week, week_of_year, month, quarter, year)
SELECT
    MD5(TO_CHAR(gen_date, 'YYYY-MM-DD'))::CHAR(32),
    gen_date,
    EXTRACT(DOW FROM gen_date),
    EXTRACT(WEEK FROM gen_date),
    EXTRACT(MONTH FROM gen_date),
    EXTRACT(QUARTER FROM gen_date),
    EXTRACT(YEAR FROM gen_date)
FROM generate_series('2024-01-01'::date, '2027-12-31'::date, '1 day'::interval) AS gen_date;