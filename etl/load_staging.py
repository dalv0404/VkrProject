import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime
import os
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DATA_DIR

CSV_TABLES = {
    "orders.csv": "stg.orders",
    "production_events.csv": "stg.production_events",
    "quality_checks.csv": "stg.quality_checks",
    "downtime_events.csv": "stg.downtime_events",
    "maintenance.csv": "stg.maintenance"
}

engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

def load_to_staging(file_path: str, table_name: str, run_id: str) -> int:
    df = pd.read_csv(file_path, dtype=str)
    rows_read = len(df)
    df["_load_id"] = run_id
    df["_loaded_at"] = datetime.now()

    with engine.begin() as conn:
        # удаляем предыдущую загрузку с таким же run_id
        conn.execute(text(f"DELETE FROM {table_name} WHERE _load_id = :rid"), {"rid": run_id})
        df.to_sql(table_name.split(".")[1], conn, schema=table_name.split(".")[0],
                  if_exists="append", index=False)
    return rows_read

def main(run_id: str):
    for csv_file, table in CSV_TABLES.items():
        path = os.path.join(DATA_DIR, csv_file)
        if not os.path.exists(path):
            print(f"Файл {path} не найден, пропускаем.")
            continue
        rows = load_to_staging(path, table, run_id)
        print(f"{csv_file}: загружено {rows} строк в {table}")

if __name__ == "__main__":
    import sys
    run_id = sys.argv[1] if len(sys.argv) > 1 else f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    main(run_id)