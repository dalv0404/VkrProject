# ml/train_forecast.py
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'etl'))

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report
from sklearn.preprocessing import StandardScaler
from imblearn.over_sampling import SMOTE
import joblib
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

def add_features(df, engine):
    # 1. Скользящее среднее простоев за 7 дней по оборудованию
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

    # 2. Дней с последнего обслуживания (пока заглушка)
    df['days_since_last_maint'] = np.random.randint(0, 30, len(df))
    return df

def train():
    query = """
    SELECT
        d.date_value,
        d.day_of_week,
        d.week_of_year,
        e.equipment_code,
        dm.defect_type,
        dm.checked_qty,
        dm.defect_qty,
        CASE WHEN dm.checked_qty > 0 THEN dm.defect_qty::float / dm.checked_qty ELSE 0 END AS defect_rate
    FROM dm.dm_quality dm
    JOIN dwh.hub_date d ON dm.date_value = d.date_value
    JOIN dwh.hub_equipment e ON dm.equipment_code = e.equipment_code
    """
    df = pd.read_sql(query, engine)

    # Целевая переменная: 1, если хотя бы один дефект в проверке
    df['high_defect'] = (df['defect_qty'] > 0).astype(int)

    # Лаговый признак: скользящее среднее defect_rate за 7 дней
    df = df.sort_values(['equipment_code', 'date_value'])
    df['rolling_avg_defect'] = df.groupby('equipment_code')['defect_rate'].transform(
        lambda x: x.shift(1).rolling(7, min_periods=1).mean()
    ).fillna(0)

    df = add_features(df, engine)

    features = ['day_of_week', 'week_of_year', 'checked_qty', 'rolling_avg_defect',
                'rolling_downtime', 'days_since_last_maint']
    X = df[features]
    y = df['high_defect']

    print(f"Распределение классов: 0={sum(y==0)}, 1={sum(y==1)}")
    if len(np.unique(y)) < 2:
        print("Только один класс в выборке. Модель не может быть обучена.")
        return

    smote = SMOTE(random_state=42)
    X_resampled, y_resampled = smote.fit_resample(X, y)
    print(f"После SMOTE: 0={sum(y_resampled==0)}, 1={sum(y_resampled==1)}")

    X_train, X_test, y_train, y_test = train_test_split(X_resampled, y_resampled,
                                                        test_size=0.2, random_state=42)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    param_grid = {'n_estimators': [100, 150], 'max_depth': [10, 15, None]}
    grid = GridSearchCV(RandomForestClassifier(random_state=42, class_weight='balanced'),
                        param_grid, cv=3, scoring='recall')
    grid.fit(X_train_scaled, y_train)

    model = grid.best_estimator_
    y_pred = model.predict(X_test_scaled)
    print("Лучшие параметры:", grid.best_params_)
    print("Accuracy:", accuracy_score(y_test, y_pred))
    print("Precision:", precision_score(y_test, y_pred))
    print("Recall:", recall_score(y_test, y_pred))
    print("F1-score:", f1_score(y_test, y_pred))
    print(classification_report(y_test, y_pred))

    joblib.dump({'model': model, 'scaler': scaler}, 'ml/model_rf.pkl')
    print("Модель и скейлер сохранены в ml/model_rf.pkl")

if __name__ == "__main__":
    train()