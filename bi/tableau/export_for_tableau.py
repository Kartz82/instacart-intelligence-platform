"""Export the dbt marts from the local PostgreSQL warehouse to CSV for Tableau Public.

Tableau Public (free) cannot connect to a database; it reads files. This writes one CSV
per mart into bi/tableau/data/, plus a manifest with row counts so the workbook can be
checked against the warehouse.

    docker compose up -d                      # the warehouse must be running
    python bi/tableau/export_for_tableau.py   # writes bi/tableau/data/*.csv

Reads connection settings from .env, same variables as src/database_loader.py.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

# mart -> schema. dbt builds into <profile schema>_<custom schema>; the profile schema is `analytics`.
MARTS = {
    "mart_executive_kpis": "analytics_kpis",
    "mart_customer_segments": "analytics_kpis",
    "mart_product_performance": "analytics_kpis",
    "mart_reorder_behavior": "analytics_kpis",
    "mart_cohort_retention": "analytics_analysis",
    "mart_time_patterns": "analytics_analysis",
    "mart_basket_affinity": "analytics_analysis",
}


def engine_from_env():
    url = "postgresql+psycopg2://{u}:{pw}@{h}:{port}/{db}".format(
        u=os.getenv("POSTGRES_USER", "postgres"),
        pw=os.getenv("POSTGRES_PASSWORD", "postgres"),
        h=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5434"),
        db=os.getenv("POSTGRES_DB", "instacart_db"),
    )
    return create_engine(url)


def export(engine, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "tables": {}}
    for mart, schema in MARTS.items():
        df = pd.read_sql_table(mart, engine, schema=schema)
        path = out_dir / f"{mart}.csv"
        df.to_csv(path, index=False)
        manifest["tables"][mart] = {"rows": len(df), "columns": list(df.columns), "file": path.name}
        print(f"{schema}.{mart}: {len(df):,} rows -> {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, default=ROOT / "bi" / "tableau" / "data")
    a = p.parse_args()
    export(engine_from_env(), a.out)


if __name__ == "__main__":
    main()
