# etl/build_core.py
"""
Загрузка данных из staging-слоя в ядро Data Vault (Silver-слой).
Все имена полей соответствуют реальным колонкам staging-таблиц.
"""
from sqlalchemy import create_engine, text
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

def load_hubs(conn, run_id):
    # Оборудование
    conn.execute(text("""
        INSERT INTO dwh.hub_equipment (equipment_hash_key, equipment_code, source_system)
        SELECT DISTINCT ON (equipment_code)
            MD5(equipment_code)::CHAR(32), equipment_code, 'stg'
        FROM stg.production_events
        WHERE _load_id = :rid AND equipment_code IS NOT NULL
        ON CONFLICT (equipment_code) DO NOTHING
    """), {"rid": run_id})

    # Заказы
    conn.execute(text("""
        INSERT INTO dwh.hub_order (order_hash_key, order_code, source_system)
        SELECT DISTINCT ON (order_code)
            MD5(order_code)::CHAR(32), order_code, 'stg'
        FROM stg.orders
        WHERE _load_id = :rid
        ON CONFLICT (order_code) DO NOTHING
    """), {"rid": run_id})

    # Сотрудники
    conn.execute(text("""
        INSERT INTO dwh.hub_employee (employee_hash_key, employee_code, source_system)
        SELECT DISTINCT ON (employee_code)
            MD5(employee_code)::CHAR(32), employee_code, 'stg'
        FROM stg.production_events
        WHERE _load_id = :rid AND employee_code IS NOT NULL
        ON CONFLICT (employee_code) DO NOTHING
    """), {"rid": run_id})

    # Типы дефектов
    conn.execute(text("""
        INSERT INTO dwh.hub_defect_type (defect_type_hash_key, defect_code, source_system)
        SELECT DISTINCT ON (defect_code)
            MD5(defect_code)::CHAR(32), defect_code, 'stg'
        FROM stg.quality_checks
        WHERE _load_id = :rid AND defect_code IS NOT NULL
        ON CONFLICT (defect_code) DO NOTHING
    """), {"rid": run_id})

def load_links(conn, run_id):
    # Производственные операции
    conn.execute(text("""
        INSERT INTO dwh.lnk_production_operation (link_hash_key, order_hash_key, equipment_hash_key, employee_hash_key, date_hash_key)
        SELECT
            MD5(pe.event_id || pe.start_time)::CHAR(32),
            MD5(pe.order_code)::CHAR(32),
            MD5(pe.equipment_code)::CHAR(32),
            MD5(pe.employee_code)::CHAR(32),
            MD5(TO_CHAR(CAST(pe.start_time AS DATE), 'YYYY-MM-DD'))::CHAR(32)
        FROM stg.production_events pe
        WHERE pe._load_id = :rid
        ON CONFLICT (link_hash_key) DO NOTHING
    """), {"rid": run_id})

    # События качества (все проверки, включая бездефектные)
    conn.execute(text("""
        INSERT INTO dwh.lnk_quality_event (link_hash_key, order_hash_key, equipment_hash_key, defect_type_hash_key, date_hash_key)
        SELECT
            MD5(qc.check_id || qc.check_time)::CHAR(32),
            MD5(qc.order_code)::CHAR(32),
            MD5(qc.equipment_code)::CHAR(32),
            MD5(qc.defect_code)::CHAR(32),
            MD5(TO_CHAR(CAST(qc.check_time AS DATE), 'YYYY-MM-DD'))::CHAR(32)
        FROM stg.quality_checks qc
        WHERE qc._load_id = :rid
        ON CONFLICT (link_hash_key) DO NOTHING
    """), {"rid": run_id})

    # Простои
    conn.execute(text("""
        INSERT INTO dwh.lnk_downtime (link_hash_key, equipment_hash_key, date_hash_key)
        SELECT
            MD5(de.event_id || de.start_time)::CHAR(32),
            MD5(de.equipment_code)::CHAR(32),
            MD5(TO_CHAR(CAST(de.start_time AS DATE), 'YYYY-MM-DD'))::CHAR(32)
        FROM stg.downtime_events de
        WHERE de._load_id = :rid
        ON CONFLICT (link_hash_key) DO NOTHING
    """), {"rid": run_id})

    # Техобслуживание
    conn.execute(text("""
        INSERT INTO dwh.lnk_maintenance (link_hash_key, equipment_hash_key, date_hash_key)
        SELECT
            MD5(m.maintenance_id || m.maintenance_date)::CHAR(32),
            MD5(m.equipment_code)::CHAR(32),
            MD5(TO_CHAR(CAST(m.maintenance_date AS DATE), 'YYYY-MM-DD'))::CHAR(32)
        FROM stg.maintenance m
        WHERE m._load_id = :rid
        ON CONFLICT (link_hash_key) DO NOTHING
    """), {"rid": run_id})

def load_satellites(conn, run_id):
    # Описательные атрибуты оборудования
    conn.execute(text("""
        INSERT INTO dwh.sat_equipment_details (equipment_hash_key, valid_from, equipment_name, equipment_group, workshop_code, ideal_cycle_sec)
        SELECT
            MD5(pe.equipment_code)::CHAR(32),
            CURRENT_DATE,
            pe.equipment_code,
            'Group01',
            'Workshop01',
            60
        FROM stg.production_events pe
        WHERE pe._load_id = :rid
        ON CONFLICT (equipment_hash_key, load_date) DO NOTHING
    """), {"rid": run_id})

    # Атрибуты заказов
    conn.execute(text("""
        INSERT INTO dwh.sat_order_details (order_hash_key, planned_qty, product_code, planned_start, planned_end, status)
        SELECT
            MD5(o.order_code)::CHAR(32),
            CAST(o.planned_qty AS NUMERIC),
            o.product_code,
            CAST(o.planned_start AS DATE),
            CAST(o.planned_end AS DATE),
            o.status
        FROM stg.orders o
        WHERE o._load_id = :rid
        ON CONFLICT (order_hash_key, load_date) DO NOTHING
    """), {"rid": run_id})

    # Метрики производства
    conn.execute(text("""
        INSERT INTO dwh.sat_production_metric (link_hash_key, planned_qty, actual_qty, cycle_time_sec)
        SELECT
            MD5(pe.event_id || pe.start_time)::CHAR(32),
            CAST(pe.planned_qty AS NUMERIC),
            CAST(pe.actual_qty AS NUMERIC),
            EXTRACT(EPOCH FROM (CAST(pe.end_time AS TIMESTAMP) - CAST(pe.start_time AS TIMESTAMP)))::INT
        FROM stg.production_events pe
        WHERE pe._load_id = :rid
        ON CONFLICT (link_hash_key, load_date) DO NOTHING
    """), {"rid": run_id})

    # Метрики простоев
    conn.execute(text("""
        INSERT INTO dwh.sat_downtime_metric (link_hash_key, reason_code, duration_min, is_planned, description)
        SELECT
            MD5(de.event_id || de.start_time)::CHAR(32),
            de.reason_code,
            CAST(de.duration_min AS INT),
            CASE WHEN de.reason_code IN ('PM','SCHEDULED_MAINT') THEN TRUE ELSE FALSE END,
            de.description
        FROM stg.downtime_events de
        WHERE de._load_id = :rid
        ON CONFLICT (link_hash_key, load_date) DO NOTHING
    """), {"rid": run_id})

    # Метрики качества – для всех проверок (и с дефектами, и без)
    conn.execute(text("""
        INSERT INTO dwh.sat_quality_metric (link_hash_key, checked_qty, defect_qty, defect_type)
        SELECT
            MD5(qc.check_id || qc.check_time)::CHAR(32),
            CAST(qc.checked_qty AS INT),
            CAST(qc.defect_qty AS INT),
            qc.defect_type
        FROM stg.quality_checks qc
        WHERE qc._load_id = :rid
        ON CONFLICT (link_hash_key, load_date) DO NOTHING
    """), {"rid": run_id})
    
    
def load_all(run_id: str):
    with engine.begin() as conn:
        print("Загрузка хабов...")
        load_hubs(conn, run_id)
        print("Загрузка связей...")
        load_links(conn, run_id)
        print("Загрузка сателлитов...")
        load_satellites(conn, run_id)
    print("Ядро обновлено.")

if __name__ == "__main__":
    import sys
    run_id = sys.argv[1] if len(sys.argv) > 1 else f"run_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')}"
    load_all(run_id)