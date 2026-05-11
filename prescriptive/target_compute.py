# prescriptive/target_compute.py
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'etl'))

from sqlalchemy import create_engine, text
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

def compute_targets(target_ros=0.20):
    with engine.begin() as conn:
        res = conn.execute(text("""
            SELECT AVG(planned_qty) as avg_planned_qty
            FROM dwh.sat_order_details
            WHERE planned_qty IS NOT NULL
        """)).fetchone()
        avg_planned_qty = float(res[0]) if res[0] else 100.0

        revenue = float(avg_planned_qty * 1000.0)
        cost = float(avg_planned_qty * 820.0)

        alpha = 0.3
        beta = 0.7
        target_ros = float(target_ros)

        k0 = (target_ros * revenue - revenue + cost) / (alpha + beta - target_ros * alpha)
        planned_revenue = revenue + alpha * k0
        planned_cost = cost - beta * k0
        planned_ros = (planned_revenue - planned_cost) / planned_revenue

        conn.execute(text("""
            INSERT INTO dm.targets (target_date, planned_revenue, planned_cost, planned_ros)
            VALUES (CURRENT_DATE, :rev, :cost, :ros)
            ON CONFLICT (target_date) DO UPDATE SET
                planned_revenue = EXCLUDED.planned_revenue,
                planned_cost = EXCLUDED.planned_cost,
                planned_ros = EXCLUDED.planned_ros
        """), {"rev": planned_revenue, "cost": planned_cost, "ros": planned_ros})

        print(f"Целевые показатели рассчитаны: revenue={planned_revenue:.2f}, cost={planned_cost:.2f}, ROS={planned_ros:.2%}")

if __name__ == "__main__":
    compute_targets()