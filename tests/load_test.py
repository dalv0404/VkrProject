import time
import subprocess
import sys
from sqlalchemy import create_engine, text
import pandas as pd

DB_USER = "postgres"
DB_PASS = "postgres"
DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "dwh_db"

engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

def ensure_hub_date():
    """Добавляем в hub_date все уникальные даты из staging-таблиц, которых ещё нет."""
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO dwh.hub_date (date_hash_key, date_value, load_date)
            SELECT MD5(to_char(d, 'YYYYMMDD'))::CHAR(32), d, NOW()
            FROM (
                SELECT DISTINCT CAST(start_time AS DATE) AS d
                FROM stg.src_production_events
                UNION
                SELECT DISTINCT CAST(check_time AS DATE)
                FROM stg.src_quality_checks
                UNION
                SELECT DISTINCT CAST(start_time AS DATE)
                FROM stg.src_downtime_events
            ) t
            WHERE NOT EXISTS (
                SELECT 1 FROM dwh.hub_date
                WHERE date_hash_key = MD5(to_char(t.d, 'YYYYMMDD'))::CHAR(32)
            )
        """))

volumes = [500_000, 1_000_000]
results = []

for vol in volumes:
    print(f"\n--- Объём: {vol:,} строк ---")
    # Генерация данных
    subprocess.run([sys.executable, "samples/generate_data.py", "-n", str(vol), "-o", "samples"], check=True)
    # Дозаполнение отсутствующих дат
    print("Добавление отсутствующих дат в hub_date...")
    ensure_hub_date()
    # ETL
    subprocess.run([sys.executable, "etl/run_etl.py"], check=True)
    # Обновление витрин
    with engine.begin() as conn:
        conn.execute(text("REFRESH MATERIALIZED VIEW dm.dm_order_kpi;"))
        conn.execute(text("REFRESH MATERIALIZED VIEW dm.dm_downtime;"))
        conn.execute(text("REFRESH MATERIALIZED VIEW dm.dm_quality;"))
        conn.execute(text("REFRESH MATERIALIZED VIEW dm.dm_oee;"))

    # Тестовые запросы
    queries = {
        "Сводка по заказам за месяц": """
            SELECT product_code, SUM(total_planned_qty), SUM(total_actual_qty)
            FROM dm.dm_order_kpi
            WHERE order_date BETWEEN '2025-01-01' AND '2025-01-31'
            GROUP BY product_code
        """,
        "Топ-5 простоев": """
            SELECT equipment_code, total_downtime_min
            FROM dm.dm_downtime
            ORDER BY total_downtime_min DESC
            LIMIT 5
        """,
        "Качество по участкам": """
            SELECT workshop_code, defect_rate_pct
            FROM dm.dm_quality
            ORDER BY defect_rate_pct DESC
        """
    }

    for name, sql in queries.items():
        with engine.connect() as conn:
            start = time.perf_counter()
            conn.execute(text(sql))
            elapsed = time.perf_counter() - start
            results.append((vol, name, round(elapsed * 1000, 2)))
            print(f"  {name}: {elapsed*1000:.2f} мс")

# Сохраняем результаты
df = pd.DataFrame(results, columns=["Объём", "Запрос", "Время, мс"])
df.to_csv("tests/load_test_results.csv", index=False)
print("\nРезультаты сохранены в tests/load_test_results.csv")