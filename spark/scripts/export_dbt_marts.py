"""Export the five dbt marts from the local PostgreSQL warehouse to Parquet, for the
Databricks reconciliation notebook.

    python spark/scripts/export_dbt_marts.py --out exports/dbt_marts

Reads connection settings from .env (same variables as src/database_loader.py).
Requires pandas, pyarrow, SQLAlchemy and psycopg2 (pip install pyarrow on top of
requirements.txt).
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

# dbt builds into <profile schema>_<custom schema>; the profile schema is `analytics`.
MARTS = {
    "mart_executive_kpis": "analytics_kpis",
    "mart_customer_segments": "analytics_kpis",
    "mart_cohort_retention": "analytics_analysis",
    "mart_time_patterns": "analytics_analysis",
    "mart_basket_affinity": "analytics_analysis",
}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=ROOT / "exports" / "dbt_marts")
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    url = "postgresql+psycopg2://{u}:{pw}@{h}:{port}/{db}".format(
        u=os.getenv("POSTGRES_USER", "postgres"),
        pw=os.getenv("POSTGRES_PASSWORD", "postgres"),
        h=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5434"),
        db=os.getenv("POSTGRES_DB", "instacart_db"),
    )
    engine = create_engine(url)
    for mart, schema in MARTS.items():
        df = pd.read_sql_table(mart, engine, schema=schema)
        target = a.out / f"{mart}.parquet"
        df.to_parquet(target, index=False)
        print(f"{schema}.{mart}: {len(df):,} rows -> {target}")


if __name__ == "__main__":
    main()
