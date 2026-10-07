"""Run the real dbt project on DuckDB over a CSV folder, to get reference marts.

This is the "answer key" for the PySpark ports: the same dbt SQL that builds the
Postgres warehouse is compiled for DuckDB, run over the synthetic sample, and its marts
are exported to Parquet for comparison.

Requires: dbt-duckdb, and dbt_utils installed in <project>/dbt_packages (run `dbt deps`).

    python spark/tests/dbt_oracle.py --csv-dir /tmp/sample --out-dir /tmp/oracle \
        --project-dir dbt --vars '{"min_product_orders": 20, "min_pair_orders": 5}'
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import duckdb

RAW_TABLES = ["departments", "aisles", "products", "orders", "order_products"]
MARTS = {
    "mart_executive_kpis": "kpis",
    "mart_customer_segments": "kpis",
    "mart_cohort_retention": "analysis",
    "mart_time_patterns": "analysis",
    "mart_basket_affinity": "analysis",
    "dim_orders": "core",
    "dim_customers": "core",
    "fact_order_items": "core",
}

PROFILE = """instacart_analytics:
  target: duckdb
  outputs:
    duckdb:
      type: duckdb
      path: "{db}"
      schema: main
      threads: 2
"""


def load_raw(db_path: Path, csv_dir: Path) -> None:
    con = duckdb.connect(str(db_path))
    con.execute("create schema if not exists raw")
    for name in RAW_TABLES:
        con.execute(
            f"create or replace table raw.{name} as "
            f"select * from read_csv_auto(?, header=true, nullstr='')",
            [str(csv_dir / f"{name}.csv")],
        )
    con.close()


def run_dbt(project_dir: Path, db_path: Path, vars_json: str, dbt_bin: str, select: str) -> None:
    with tempfile.TemporaryDirectory() as profiles_dir:
        Path(profiles_dir, "profiles.yml").write_text(PROFILE.format(db=db_path))
        env = {**os.environ, "DBT_RAW_SCHEMA": "raw"}
        cmd = [
            dbt_bin, "build",
            "--project-dir", str(project_dir),
            "--profiles-dir", profiles_dir,
            "--target-path", str(db_path.parent / "dbt_target"),
            "--log-path", str(db_path.parent / "dbt_logs"),
            "--vars", vars_json,
            "--select", select,
            "--indirect-selection", "cautious",
            # Tests that assert properties of the REAL extract (e.g. every segment
            # non-empty) are not expected to hold on a 300-user synthetic sample.
            "--exclude", "assert_customer_segments_cover_all_customers",
        ]
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        print(result.stdout[-4000:])
        if result.returncode != 0:
            print(result.stderr[-4000:], file=sys.stderr)
            raise SystemExit(f"dbt build failed with exit code {result.returncode}")


def export_marts(db_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path), read_only=True)
    for name, schema in MARTS.items():
        # dbt-duckdb names custom schemas <target schema>_<custom schema>
        con.execute(f"copy main_{schema}.{name} to ? (format parquet)", [str(out_dir / f"{name}.parquet")])
    con.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--project-dir", type=Path, default=Path("dbt"))
    parser.add_argument("--vars", default="{}")
    parser.add_argument("--dbt-bin", default=shutil.which("dbt") or "dbt")
    parser.add_argument("--select", default="+mart_executive_kpis +mart_customer_segments "
                        "+mart_cohort_retention +mart_time_patterns +mart_basket_affinity")
    args = parser.parse_args()
    json.loads(args.vars)  # fail fast on malformed JSON

    args.out_dir.mkdir(parents=True, exist_ok=True)
    db_path = (args.out_dir / "oracle.duckdb").resolve()
    db_path.unlink(missing_ok=True)
    load_raw(db_path, args.csv_dir)
    run_dbt(args.project_dir.resolve(), db_path, args.vars, args.dbt_bin, args.select)
    export_marts(db_path, args.out_dir)
    print(f"exported {len(MARTS)} tables to {args.out_dir}")


if __name__ == "__main__":
    main()
