#!/bin/bash
# manage.sh — интерактивное управление проектом DWH iBPMS
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# --- Определение Python (приоритет: активное виртуальное окружение) ---
if [ -n "${VIRTUAL_ENV:-}" ]; then
    PYTHON_CMD="${VIRTUAL_ENV}/Scripts/python.exe"
else
    PYTHON_CMD="python"
fi

# --- Автоопределение PostgreSQL (Windows) ---
find_psql_dir() {
    local versions="18 17 16 15 14 13 12"
    for ver in $versions; do
        local path="/c/Program Files/PostgreSQL/$ver/bin"
        if [ -f "$path/psql.exe" ]; then
            echo "$path"
            return
        fi
        path="/c/Program Files (x86)/PostgreSQL/$ver/bin"
        if [ -f "$path/psql.exe" ]; then
            echo "$path"
            return
        fi
    done
    echo ""
}

PSQL_DIR=$(find_psql_dir)
if [ -n "$PSQL_DIR" ]; then
    export PATH="$PSQL_DIR:$PATH"
fi

# --- Переменные окружения БД ---
export PGHOST="${PGHOST:-localhost}"
export PGPORT="${PGPORT:-5432}"
export PGDATABASE="${PGDATABASE:-dwh_db}"
export PGUSER="${PGUSER:-postgres}"
export PGPASSWORD="${PGPASSWORD:-postgres}"

info()  { echo -e "\e[32m[INFO]\e[0m  $*"; }
warn()  { echo -e "\e[33m[WARN]\e[0m  $*"; }
error() { echo -e "\e[31m[ERROR]\e[0m $*"; exit 1; }

create_db_if_not_exists() {
    if psql -U "$PGUSER" -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw "$PGDATABASE"; then
        info "База данных '$PGDATABASE' уже существует."
    else
        warn "Создание базы данных '$PGDATABASE'..."
        createdb -U "$PGUSER" "$PGDATABASE"
        info "База данных создана."
    fi
}

clean_all() {
    info "Очистка всех схем..."
    psql -v ON_ERROR_STOP=1 <<EOF
DROP SCHEMA IF EXISTS stg CASCADE;
DROP SCHEMA IF EXISTS dwh CASCADE;
DROP SCHEMA IF EXISTS dm CASCADE;
DROP SCHEMA IF EXISTS audit CASCADE;
EOF
    info "Схемы удалены."
}

run_sql_scripts() {
    info "Применение SQL-скриптов..."
    for script in 01_create_schemas.sql 02_create_tables_stg.sql 03_create_tables_dwh.sql 04_create_tables_dm.sql 05_create_audit.sql 06_create_marts.sql; do
        local file="$SCRIPT_DIR/sql/$script"
        if [ -f "$file" ]; then
            info "Выполнение $script..."
            psql -v ON_ERROR_STOP=1 -f "$file"
        else
            warn "Файл $file не найден."
        fi
    done
    info "Структура БД готова."
}

generate_data() {
    local orders="${1:-200}"
    local prod_factor="${2:-3.0}"
    local qual_prob="${3:-0.7}"
    local down_prob="${4:-0.2}"
    local maint_count="${5:-100}"

    info "Генерация синтетических данных..."
    $PYTHON_CMD "$SCRIPT_DIR/samples/generate_data.py" \
        -n "$orders" \
        --production-factor "$prod_factor" \
        --quality-prob "$qual_prob" \
        --downtime-prob "$down_prob" \
        --maintenance-count "$maint_count" \
        -o "$SCRIPT_DIR/samples"
    info "Данные сгенерированы."
}

run_etl() {
    info "Запуск ETL..."
    $PYTHON_CMD "$SCRIPT_DIR/etl/run_etl.py"
    info "ETL завершён."
}

train_model() {
    info "Обучение модели..."
    $PYTHON_CMD "$SCRIPT_DIR/ml/train_forecast.py"
    info "Модель обучена."
}

run_prescriptive() {
    info "Расчёт прескриптивных показателей..."
    $PYTHON_CMD "$SCRIPT_DIR/prescriptive/target_compute.py"
    info "Целевые показатели рассчитаны."
}

run_predict() {
    info "Прогнозирование риска брака..."
    $PYTHON_CMD "$SCRIPT_DIR/ml/predict.py"
    info "Прогнозы обновлены."
}

status() {
    info "Состояние базы данных:"
    psql -c "
SELECT 'staging' as layer, count(*)::text FROM pg_tables WHERE schemaname='stg'
UNION ALL SELECT 'dwh', count(*)::text FROM pg_tables WHERE schemaname='dwh'
UNION ALL SELECT 'dm', count(*)::text FROM pg_tables WHERE schemaname='dm'
UNION ALL SELECT 'audit', count(*)::text FROM pg_tables WHERE schemaname='audit';
    "
    info "Количество записей в основных таблицах:"
    psql -c "
SELECT 'hub_equipment' as tbl, count(*) FROM dwh.hub_equipment
UNION ALL SELECT 'hub_order', count(*) FROM dwh.hub_order
UNION ALL SELECT 'hub_employee', count(*) FROM dwh.hub_employee
UNION ALL SELECT 'lnk_production', count(*) FROM dwh.lnk_production_operation
UNION ALL SELECT 'dm_oee (rows)', count(*) FROM dm.dm_oee;
    "
}

# --- Интерактивное меню ---
interactive_menu() {
    while true; do
        echo ""
        echo "======================================"
        echo "  Управление проектом DWH iBPMS"
        echo "======================================"
        echo "1. Генерация синтетических данных"
        echo "2. Запустить ETL + Модель + Прескриптив + Прогноз"
        echo "3. Выборочный запуск этапов"
        echo "0. Выход"
        echo "======================================"
        read -p "Ваш выбор: " main_choice

        case "$main_choice" in
            1) 
                read -p "Количество заказов (по умолчанию 200): " orders_input
                orders_input="${orders_input:-200}"
                orders_input="${orders_input//[^0-9]/}"
                [ -z "$orders_input" ] && orders_input=200
                read -p "Среднее число операций на заказ (по умолчанию 3.0): " prod_factor
                prod_factor="${prod_factor:-3.0}"
                read -p "Вероятность проверки качества (0..1, по умолчанию 0.7): " qual_prob
                qual_prob="${qual_prob:-0.7}"
                read -p "Вероятность простоя (0..1, по умолчанию 0.2): " down_prob
                down_prob="${down_prob:-0.2}"
                read -p "Количество записей обслуживания (по умолчанию 100): " maint_count
                maint_count="${maint_count:-100}"
                maint_count="${maint_count//[^0-9]/}"
                [ -z "$maint_count" ] && maint_count=100
                generate_data "$orders_input" "$prod_factor" "$qual_prob" "$down_prob" "$maint_count"
                ;;
            2)
                echo "Запуск ETL (полный) + обучение модели + прескриптивные расчёты + прогноз..."
                $PYTHON_CMD "$SCRIPT_DIR/etl/run_etl.py"
                $PYTHON_CMD "$SCRIPT_DIR/ml/train_forecast.py"
                $PYTHON_CMD "$SCRIPT_DIR/prescriptive/target_compute.py"
                $PYTHON_CMD "$SCRIPT_DIR/ml/predict.py"
                info "Цикл ETL+аналитика завершён."
                ;;
            3)
                submenu_etap
                ;;
            0) exit 0 ;;
            *) warn "Неверный ввод." ;;
        esac
    done
}

submenu_etap() {
    while true; do
        echo ""
        echo "--- Выборочный запуск этапов ---"
        echo "1. Загрузка данных в Staging (load_staging.py)"
        echo "2. Валидация данных (validate_data.py)"
        echo "3. Загрузка в ядро Data Vault (build_core.py)"
        echo "4. Обновление витрин (refresh_marts.py)"
        echo "5. Обучение модели (train_forecast.py)"
        echo "6. Прескриптивные расчёты (target_compute.py)"
        echo "7. Прогнозирование брака (predict.py)"
        echo "8. Все этапы ETL (load -> validate -> core -> marts)"
        echo "0. Назад"
        read -p "Ваш выбор: " sub_choice

        case "$sub_choice" in
            1) run_staging ;;
            2) run_validation ;;
            3) run_build_core ;;
            4) $PYTHON_CMD "$SCRIPT_DIR/etl/refresh_marts.py" ;;
            5) $PYTHON_CMD "$SCRIPT_DIR/ml/train_forecast.py" ;;
            6) $PYTHON_CMD "$SCRIPT_DIR/prescriptive/target_compute.py" ;;
            7) $PYTHON_CMD "$SCRIPT_DIR/ml/predict.py" ;;
            8) 
                run_id=$(date +"manual_%Y%m%d_%H%M%S")
                info "Запуск полного ETL с run_id=$run_id"
                $PYTHON_CMD "$SCRIPT_DIR/etl/load_staging.py" "$run_id"
                ensure_run_log "$run_id"
                $PYTHON_CMD "$SCRIPT_DIR/etl/validate_data.py" "$run_id"
                $PYTHON_CMD "$SCRIPT_DIR/etl/build_core.py" "$run_id"
                $PYTHON_CMD "$SCRIPT_DIR/etl/refresh_marts.py"
                info "Все этапы ETL выполнены."
                ;;
            0) break ;;
            *) warn "Неверный ввод." ;;
        esac
    done
}

ensure_run_log() {
    local rid="$1"
    psql -c "INSERT INTO audit.etl_run_log (run_id, status) VALUES ('$rid', 'running') ON CONFLICT (run_id) DO NOTHING;" >/dev/null
}

run_staging() {
    read -p "Введите run_id (Enter для автоматической генерации): " rid
    rid="${rid:-$(date +"manual_%Y%m%d_%H%M%S")}"
    $PYTHON_CMD "$SCRIPT_DIR/etl/load_staging.py" "$rid"
    echo "Staging загружен (run_id=$rid)."
}

run_validation() {
    read -p "Введите run_id: " rid
    if [ -z "$rid" ]; then
        echo "run_id обязателен."
        return
    fi
    ensure_run_log "$rid"
    $PYTHON_CMD "$SCRIPT_DIR/etl/validate_data.py" "$rid"
}

run_build_core() {
    read -p "Введите run_id: " rid
    if [ -z "$rid" ]; then
        echo "run_id обязателен."
        return
    fi
    $PYTHON_CMD "$SCRIPT_DIR/etl/build_core.py" "$rid"
}

# --- Автоматический режим (совместимость) ---
auto_mode() {
    case "${1:-help}" in
        all)
            create_db_if_not_exists
            generate_data
            run_etl
            train_model
            run_prescriptive
            run_predict
            ;;
        reset)
            create_db_if_not_exists
            clean_all
            run_sql_scripts
            generate_data 200 3.0 0.7 0.2 100
            run_etl
            train_model
            run_prescriptive
            run_predict
            ;;
        generate)
            create_db_if_not_exists
            generate_data
            ;;
        etl)
            create_db_if_not_exists
            run_etl
            ;;
        model)
            create_db_if_not_exists
            train_model
            ;;
        prescriptive)
            create_db_if_not_exists
            run_prescriptive
            ;;
        predict)
            create_db_if_not_exists
            run_predict
            ;;
        status)
            status
            ;;
        clean)
            clean_all
            ;;
        help|--help|-h)
            echo "Команды: all, reset, generate, etl, model, prescriptive, predict, status, clean, help"
            echo "Без аргументов запускает интерактивное меню."
            ;;
        *) error "Неизвестная команда: $1. Используйте help." ;;
    esac
}

# --- Главная логика ---
if [ $# -gt 0 ]; then
    auto_mode "$@"
else
    interactive_menu
fi