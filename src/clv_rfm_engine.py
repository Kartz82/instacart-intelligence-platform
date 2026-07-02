from pathlib import Path

import pandas as pd
import psycopg2


ROOT = Path(__file__).resolve().parents[1]
RFM_SQL_PATH = ROOT / "sql" / "rfm_analysis.sql"


def get_connection():
    return psycopg2.connect(
        dbname="instacart_db",
        user="postgres",
        password="postgres",
        host="localhost",
        port="5434",
    )


def rebuild_customer_rfm_segments():
    """Create customer_rfm_segments from the warehouse using sql/rfm_analysis.sql."""
    sql = RFM_SQL_PATH.read_text()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)
        conn.commit()


def fetch_segment_summary():
    query = """
        SELECT
            customer_segment,
            COUNT(*) AS customer_count,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS customer_pct,
            ROUND(AVG(total_orders), 1) AS avg_orders,
            ROUND(AVG(total_items_purchased), 1) AS avg_items,
            ROUND(AVG(latest_reorder_gap_days)::NUMERIC, 1) AS avg_latest_reorder_gap_days
        FROM customer_rfm_segments
        GROUP BY customer_segment
        ORDER BY customer_count DESC;
    """
    with get_connection() as conn:
        return pd.read_sql(query, conn)


if __name__ == "__main__":
    rebuild_customer_rfm_segments()
    summary = fetch_segment_summary()
    print(summary.to_string(index=False))
