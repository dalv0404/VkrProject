# etl/validate_data.py
"""
Проводит проверки качества данных в staging-слое.
Все имена полей соответствуют структуре CSV и staging-таблиц.
"""
from sqlalchemy import create_engine, text
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

# Список проверок скорректирован под реальные названия колонок в stg.*
CHECKS = [
    # orders
    {"table": "stg.orders", "field": "order_code", "rule": "not_null", "severity": "critical"},
    {"table": "stg.orders", "field": "order_code", "rule": "unique", "severity": "critical"},
    # production_events
    {"table": "stg.production_events", "field": "event_id", "rule": "not_null", "severity": "critical"},
    {"table": "stg.production_events", "field": "order_code", "rule": "not_null", "severity": "critical"},
    {"table": "stg.production_events", "field": "event_id", "rule": "unique", "severity": "critical"},
    # quality_checks
    {"table": "stg.quality_checks", "field": "check_id", "rule": "not_null", "severity": "critical"},
    {"table": "stg.quality_checks", "field": "order_code", "rule": "not_null", "severity": "critical"},
    {"table": "stg.quality_checks", "field": "check_id", "rule": "unique", "severity": "critical"},
    # downtime_events
    {"table": "stg.downtime_events", "field": "event_id", "rule": "not_null", "severity": "critical"},
    {"table": "stg.downtime_events", "field": "event_id", "rule": "unique", "severity": "critical"},
    {"table": "stg.downtime_events", "field": "duration_min", "rule": "positive", "severity": "warning"},
    # maintenance
    {"table": "stg.maintenance", "field": "maintenance_id", "rule": "not_null", "severity": "critical"},
    {"table": "stg.maintenance", "field": "maintenance_id", "rule": "unique", "severity": "critical"},
]

def run_validation(run_id: str) -> bool:
    critical_fails = 0
    with engine.begin() as conn:
        for check in CHECKS:
            table = check["table"]
            field = check["field"]
            rule = check["rule"]
            severity = check["severity"]
            sql = ""
            if rule == "not_null":
                sql = f"SELECT COUNT(*) FROM {table} WHERE {field} IS NULL AND _load_id = '{run_id}'"
            elif rule == "unique":
                sql = f"SELECT COUNT(*) FROM (SELECT {field} FROM {table} WHERE _load_id = '{run_id}' GROUP BY {field} HAVING COUNT(*) > 1) sub"
            elif rule == "positive":
                sql = f"SELECT COUNT(*) FROM {table} WHERE CAST({field} AS INT) <= 0 AND _load_id = '{run_id}'"
            else:
                continue

            res = conn.execute(text(sql)).scalar()
            # Запись результата в журнал качества
            conn.execute(text("""
                INSERT INTO audit.data_quality_checks (run_id, table_name, rule_name, severity, failed_rows)
                VALUES (:rid, :table, :rule, :sev, :cnt)
            """), {"rid": run_id, "table": table, "rule": rule, "sev": severity, "cnt": res})

            if severity == "critical" and res > 0:
                critical_fails += 1
                print(f"Критическая ошибка в {table}.{field} ({rule}), записей: {res}")

    if critical_fails > 0:
        print(f"Валидация НЕ пройдена: критических ошибок {critical_fails}")
        return False
    print("Валидация пройдена успешно")
    return True

if __name__ == "__main__":
    import sys
    run_id = sys.argv[1] if len(sys.argv) > 1 else input("Введите run_id: ")
    run_validation(run_id)