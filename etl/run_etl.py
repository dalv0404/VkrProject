# etl/run_etl.py
import subprocess
import sys
from datetime import datetime
from sqlalchemy import create_engine, text
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

def main():
    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    # Регистрируем начало
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO audit.etl_run_log (run_id, status) VALUES (:rid, 'running')"), {"rid": run_id})

    try:
        # Используем sys.executable вместо просто 'python'
        subprocess.run([sys.executable, "etl/load_staging.py", run_id], check=True)
        # валидация
        valid = subprocess.run([sys.executable, "etl/validate_data.py", run_id], check=False)
        if valid.returncode != 0:
            raise Exception("Валидация не пройдена (критические ошибки)")

        subprocess.run([sys.executable, "etl/build_core.py", run_id], check=True)
        subprocess.run([sys.executable, "etl/refresh_marts.py"], check=True)

        # Обновим статус
        with engine.begin() as conn:
            conn.execute(text("UPDATE audit.etl_run_log SET status='success', finished_at=NOW() WHERE run_id=:rid"), {"rid": run_id})
        print("ETL успешно завершён")
    except Exception as e:
        with engine.begin() as conn:
            conn.execute(text("UPDATE audit.etl_run_log SET status='failed', finished_at=NOW(), error_text=:err WHERE run_id=:rid"),
                         {"rid": run_id, "err": str(e)})
        print(f"Ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()