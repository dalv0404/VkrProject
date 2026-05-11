-- Staging-таблицы (Bronze-слой): точные копии CSV-файлов плюс служебные поля

CREATE TABLE IF NOT EXISTS stg.orders (
    order_code    TEXT,
    product_code  TEXT,
    planned_qty   TEXT,
    planned_start TEXT,
    planned_end   TEXT,
    status        TEXT,
    _load_id      TEXT NOT NULL,
    _loaded_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stg.production_events (
    event_id       TEXT,
    order_code     TEXT,
    equipment_code TEXT,
    employee_code  TEXT,
    start_time     TEXT,
    end_time       TEXT,
    planned_qty    TEXT,
    actual_qty     TEXT,
    _load_id       TEXT NOT NULL,
    _loaded_at     TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stg.quality_checks (
    check_id       TEXT,
    order_code     TEXT,
    equipment_code TEXT,
    check_time     TEXT,
    checked_qty    TEXT,
    defect_qty     TEXT,
    defect_code    TEXT,
    defect_type    TEXT,
    _load_id       TEXT NOT NULL,
    _loaded_at     TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stg.downtime_events (
    event_id       TEXT,
    equipment_code TEXT,
    reason_code    TEXT,
    start_time     TEXT,
    duration_min   TEXT,
    description    TEXT,
    _load_id       TEXT NOT NULL,
    _loaded_at     TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS stg.maintenance (
    maintenance_id   TEXT,
    equipment_code   TEXT,
    maintenance_date TEXT,
    type             TEXT,
    description      TEXT,
    _load_id         TEXT NOT NULL,
    _loaded_at       TIMESTAMP DEFAULT NOW()
);