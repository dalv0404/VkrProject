-- ================================================================
-- Контур аудита и контроля качества
-- ================================================================

CREATE TABLE audit.etl_run_log (
    run_id      TEXT PRIMARY KEY,
    started_at  TIMESTAMP DEFAULT NOW(),
    finished_at TIMESTAMP,
    status      VARCHAR(20) CHECK (status IN ('running','success','failed')),
    rows_loaded_total INT DEFAULT 0,
    rows_rejected_total INT DEFAULT 0,
    error_text  TEXT
);

CREATE TABLE audit.data_quality_checks (
    check_id    SERIAL PRIMARY KEY,
    run_id      TEXT REFERENCES audit.etl_run_log(run_id),
    table_name  VARCHAR(100),
    rule_name   VARCHAR(100),
    severity    VARCHAR(10) CHECK (severity IN ('critical','warning')),
    failed_rows INT,
    checked_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE audit.etl_batch_log (
    batch_id      SERIAL PRIMARY KEY,
    run_id        TEXT NOT NULL,
    file_name     VARCHAR(100) NOT NULL,
    rows_read     INT,
    rows_loaded   INT,
    rows_rejected INT DEFAULT 0,
    started_at    TIMESTAMP DEFAULT NOW(),
    finished_at   TIMESTAMP
);