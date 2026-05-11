# samples/generate_data.py (оптимизированная версия)
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

rng = np.random.default_rng(42)

N_EQUIPMENT = 20
N_EMPLOYEES = 50
N_ORDERS = 200
N_MAINTENANCE = 100
START_DATE = np.datetime64('2025-01-01')

def generate_orders(n: int) -> pd.DataFrame:
    order_codes = [f"ORD-{i:06d}" for i in range(1, n+1)]
    product_codes = [f"PRD-{i:03d}" for i in range(1, 11)]
    statuses = ["Created", "Released", "InProgress", "Completed"]

    # Генерируем массивы смещений в днях
    start_deltas = rng.integers(0, 365, size=n).astype('timedelta64[D]')
    planned_start_dates = START_DATE + start_deltas
    # Конец = начало + случайное смещение от 1 до 30 дней
    end_deltas = rng.integers(1, 31, size=n).astype('timedelta64[D]')
    planned_end_dates = planned_start_dates + end_deltas

    df = pd.DataFrame({
        'order_code': order_codes,
        'product_code': rng.choice(product_codes, size=n),
        'planned_qty': rng.integers(10, 501, size=n),
        'planned_start': pd.to_datetime(planned_start_dates).strftime('%Y-%m-%d'),
        'planned_end': pd.to_datetime(planned_end_dates).strftime('%Y-%m-%d'),
        'status': rng.choice(statuses, size=n)
    })
    return df

def generate_production_events(orders_df: pd.DataFrame, ops_per_order: float = 3.0) -> pd.DataFrame:
    equipment_codes = np.array([f"EQ-{i:04d}" for i in range(1, N_EQUIPMENT + 1)])
    employee_codes = np.array([f"EMP-{i:04d}" for i in range(1, N_EMPLOYEES + 1)])

    n_orders = len(orders_df)
    ops_counts = rng.poisson(ops_per_order - 1, size=n_orders) + 1
    ops_counts = np.maximum(1, ops_counts)
    total_events = ops_counts.sum()

    order_indices = np.repeat(np.arange(n_orders), ops_counts)
    orders = orders_df.iloc[order_indices]

    planned_starts = pd.to_datetime(orders['planned_start'].values)
    shifts_hours = rng.integers(0, 24, size=total_events)
    start_times = planned_starts + pd.to_timedelta(shifts_hours, unit='h')

    durations = rng.uniform(0.5, 8.0, size=total_events)
    end_times = start_times + pd.to_timedelta(durations, unit='h')

    df = pd.DataFrame({
        'event_id': [f"EV-{i+1:08d}" for i in range(total_events)],
        'order_code': orders['order_code'].values,
        'equipment_code': rng.choice(equipment_codes, size=total_events),
        'employee_code': rng.choice(employee_codes, size=total_events),
        'start_time': start_times.strftime('%Y-%m-%d %H:%M:%S'),
        'end_time': end_times.strftime('%Y-%m-%d %H:%M:%S'),
        'planned_qty': rng.integers(10, 101, size=total_events),
        'actual_qty': rng.integers(8, 101, size=total_events)
    })
    return df

def generate_quality_checks(prod_df: pd.DataFrame, check_prob: float = 0.7) -> pd.DataFrame:
    mask = rng.random(len(prod_df)) < check_prob
    selected = prod_df[mask].copy()
    n = len(selected)
    if n == 0:
        return pd.DataFrame(columns=['check_id','order_code','equipment_code','check_time',
                                     'checked_qty','defect_qty','defect_code','defect_type'])

    defect_codes_arr = np.array(["DEF01", "DEF02", "DEF03", "DEF04", "DEF05", None])
    defect_types_arr = np.array(["Scratch", "Crack", "Dimension", "Material", "Other", None])

    checked_qty = selected['actual_qty'].astype(int).values
    defect_qty = np.minimum(np.random.poisson(2, size=n), checked_qty)
    # Для записей без дефектов: код = NONE
    has_defect = defect_qty > 0
    defect_code = np.where(has_defect, rng.choice(defect_codes_arr[:-1], size=n), "NONE")
    defect_type = np.where(has_defect, rng.choice(defect_types_arr[:-1], size=n), "None")

    df = pd.DataFrame({
        'check_id': [f"QC-{i+1:08d}" for i in range(n)],
        'order_code': selected['order_code'],
        'equipment_code': selected['equipment_code'],
        'check_time': selected['end_time'],
        'checked_qty': checked_qty,
        'defect_qty': defect_qty,
        'defect_code': defect_code,
        'defect_type': defect_type
    })
    return df

def generate_downtime_events(prod_df: pd.DataFrame, downtime_prob: float = 0.2) -> pd.DataFrame:
    reason_codes = ["PM", "BREAKDOWN", "SETUP", "MATERIAL", "OPERATOR", "OTHER"]
    events = []
    event_id = 0
    daily_downtime = {}          # ключ: (equipment_code, дата) -> сумма минут

    for _, ev in prod_df.iterrows():
        if rng.random() > downtime_prob:
            continue

        eq = ev["equipment_code"]
        ev_date = ev["start_time"][:10]   # YYYY-MM-DD
        key = (eq, ev_date)

        # Сколько минут уже занято простоями в этот день для этого оборудования
        current_total = daily_downtime.get(key, 0)
        if current_total >= 480:
            continue

        # Сколько ещё можно добавить, но не более 120 минут за один простой
        max_duration = min(120, 480 - current_total)
        if max_duration < 5:          # слишком мало места, пропускаем
            continue

        # Генерируем длительность от 5 до max_duration включительно
        duration = int(rng.integers(5, max_duration + 1))
        daily_downtime[key] = current_total + duration

        event_id += 1
        reason = rng.choice(reason_codes)
        start_time = pd.to_datetime(ev["start_time"]) + pd.Timedelta(minutes=int(rng.integers(1, 61)))
        events.append({
            "event_id": f"DT-{event_id:08d}",
            "equipment_code": eq,
            "reason_code": reason,
            "start_time": start_time.strftime('%Y-%m-%d %H:%M:%S'),
            "duration_min": duration,
            "description": f"{reason} downtime"
        })

    return pd.DataFrame(events)

def generate_maintenance(equipment_codes: list, n: int) -> pd.DataFrame:
    codes = np.array(equipment_codes)
    types_arr = np.array(["Routine", "Repair", "Inspection"])

    maint_deltas = rng.integers(0, 365, size=n).astype('timedelta64[D]')
    maint_dates = START_DATE + maint_deltas

    df = pd.DataFrame({
        'maintenance_id': [f"MT-{i+1:06d}" for i in range(n)],
        'equipment_code': rng.choice(codes, size=n),
        'maintenance_date': pd.to_datetime(maint_dates).strftime('%Y-%m-%d'),
        'type': rng.choice(types_arr, size=n),
        'description': 'Maintenance'
    })
    return df

def main():
    parser = argparse.ArgumentParser(description="Генератор синтетических производственных данных (быстрый)")
    parser.add_argument("-n", "--orders", type=int, default=N_ORDERS)
    parser.add_argument("--production-factor", type=float, default=3.0)
    parser.add_argument("--quality-prob", type=float, default=0.7)
    parser.add_argument("--downtime-prob", type=float, default=0.2)
    parser.add_argument("--maintenance-count", type=int, default=N_MAINTENANCE)
    parser.add_argument("-o", "--output", type=str, default="samples")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)

    print("Генерация заказов...")
    orders_df = generate_orders(args.orders)
    orders_df.to_csv(output_dir / "orders.csv", index=False)

    print("Генерация производственных событий...")
    prod_df = generate_production_events(orders_df, args.production_factor)
    prod_df.to_csv(output_dir / "production_events.csv", index=False)

    print("Генерация проверок качества...")
    quality_df = generate_quality_checks(prod_df, args.quality_prob)
    quality_df.to_csv(output_dir / "quality_checks.csv", index=False)

    print("Генерация простоев...")
    downtime_df = generate_downtime_events(prod_df, args.downtime_prob)
    downtime_df.to_csv(output_dir / "downtime_events.csv", index=False)

    equipment_codes = prod_df["equipment_code"].unique().tolist()
    print("Генерация обслуживания...")
    maintenance_df = generate_maintenance(equipment_codes, args.maintenance_count)
    maintenance_df.to_csv(output_dir / "maintenance.csv", index=False)

    print(f"Файлы: orders={orders_df.shape[0]}, production={prod_df.shape[0]}, quality={quality_df.shape[0]}, downtime={downtime_df.shape[0]}, maintenance={maintenance_df.shape[0]}")

if __name__ == "__main__":
    main()