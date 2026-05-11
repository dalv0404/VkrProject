# etl/refresh_marts.py
from sqlalchemy import create_engine, text
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

def refresh_all():
    with engine.begin() as conn:
        conn.execute(text("REFRESH MATERIALIZED VIEW dm.dm_oee"))
        conn.execute(text("REFRESH MATERIALIZED VIEW dm.dm_mtbf_mttr"))
        conn.execute(text("REFRESH MATERIALIZED VIEW dm.dm_quality"))
        conn.execute(text("REFRESH MATERIALIZED VIEW dm.dm_downtime"))  
    print("Витрины обновлены.")

if __name__ == "__main__":
    refresh_all()