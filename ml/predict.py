# ml/predict.py
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'etl'))

import pandas as pd
import numpy as np
import joblib
from sqlalchemy import create_engine, text, types
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

def add_features(df, engine):
    downtime = pd.read_sql("""
        SELECT equipment_code, date_value, total_downtime_min
        FROM dm.dm_downtime
        ORDER BY equipment_code, date_value
    """, engine)
    if not downtime.empty:
        downtime['rolling_downtime'] = downtime.groupby('equipment_code')['total_downtime_min'].transform(
            lambda x: x.shift(1).rolling(7, min_periods=1).mean()
        ).fillna(0)
        df = df.merge(downtime[['equipment_code', 'date_value', 'rolling_downtime']],
                      on=['equipment_code', 'date_value'], how='left')
        df['rolling_downtime'] = df['rolling_downtime'].fillna(0)
    else:
        df['rolling_downtime'] = 0
    df['days_since_last_maint'] = np.random.randint(0, 30, len(df))  # заглушка
    return df

def predict():
    model_data = joblib.load('ml/model_rf.pkl')
    model = model_data['model']
    scaler = model_data['scaler']

    # Агрегированный запрос: одна строка на дату и оборудование
    query = """
    SELECT
        d.date_value,
        d.day_of_week,
        d.week_of_year,
        e.equipment_code,
        SUM(dm.checked_qty) AS checked_qty,
        SUM(dm.defect_qty) AS defect_qty,
        CASE WHEN SUM(dm.checked_qty) > 0 THEN SUM(dm.defect_qty)::float / SUM(dm.checked_qty) ELSE 0 END AS defect_rate
    FROM dm.dm_quality dm
    JOIN dwh.hub_date d ON dm.date_value = d.date_value
    JOIN dwh.hub_equipment e ON dm.equipment_code = e.equipment_code
    GROUP BY d.date_value, d.day_of_week, d.week_of_year, e.equipment_code
    """
    df = pd.read_sql(query, engine)
    if df.empty:
        print("Нет данных для прогнозирования.")
        return

    # Лаговый признак
    df = df.sort_values(['equipment_code', 'date_value'])
    df['rolling_avg_defect'] = df.groupby('equipment_code')['defect_rate'].transform(
        lambda x: x.shift(1).rolling(7, min_periods=1).mean()
    ).fillna(0)

    df = add_features(df, engine)

    features = ['day_of_week', 'week_of_year', 'checked_qty', 'rolling_avg_defect',
                'rolling_downtime', 'days_since_last_maint']
    X = df[features].fillna(0)

    X_scaled = scaler.transform(X)
    probs = model.predict_proba(X_scaled)[:, 1]
    preds = model.predict(X_scaled)

    result = pd.DataFrame({
        'date_value': df['date_value'],
        'equipment_code': df['equipment_code'],
        'predicted_class': preds.astype(int),
        'probability': np.round(probs, 4)
    })

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM dm.predictions"))
        result.to_sql('predictions', conn, schema='dm', if_exists='append', index=False,
                      dtype={'predicted_class': types.Integer()})
    print(f"Сохранено {len(result)} прогнозов в dm.predictions")

if __name__ == "__main__":
    predict()