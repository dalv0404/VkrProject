-- Таблица фактов производства (ссылается на линк)
CREATE TABLE dwh.fact_production (
    fact_id BIGSERIAL PRIMARY KEY,
    link_hash_key CHAR(32) NOT NULL REFERENCES dwh.lnk_production(link_hash_key),
    planned_qty NUMERIC(10,2) CHECK (planned_qty >= 0),
    actual_qty NUMERIC(10,2) CHECK (actual_qty >= 0),
    cycle_time_sec INT,
    load_date TIMESTAMP DEFAULT NOW()
);

-- Таблица фактов простоев
CREATE TABLE dwh.dim_downtime (
    downtime_id BIGSERIAL PRIMARY KEY,
    link_hash_key CHAR(32) NOT NULL REFERENCES dwh.lnk_downtime(link_hash_key),
    reason_code VARCHAR(20),
    duration_min INT,
    is_planned CHAR(1),
    load_date TIMESTAMP DEFAULT NOW()
);

-- Таблица фактов качества
CREATE TABLE dwh.fact_quality (
    quality_id BIGSERIAL PRIMARY KEY,
    link_hash_key CHAR(32) NOT NULL REFERENCES dwh.lnk_quality(link_hash_key),
    defect_type VARCHAR(20),
    checked_qty INT,
    defect_qty INT,
    load_date TIMESTAMP DEFAULT NOW()
);