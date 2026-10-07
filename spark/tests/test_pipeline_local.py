"""End-to-end run of the full-mode pipeline stages on the local machine, using Parquet
tables in a temporary warehouse. This proves the stage wiring (table names, reads,
writes, quality gate, run log) without Databricks. MERGE and OPTIMIZE need Delta and
are not exercised here."""

from __future__ import annotations

import json

from conftest import SAMPLE_VARS
from instacart_spark.config import Settings
from instacart_spark.pipeline import run_stage


def test_full_pipeline_stages(spark, sample_dir):
    fmt = "delta" if "Delta" in spark.conf.get("spark.sql.extensions", "") else "parquet"
    s = Settings(
        catalog=None,
        bronze_schema="t_bronze",
        silver_schema="t_silver",
        gold_schema="t_gold",
        ops_schema="t_ops",
        storage_format=fmt,
        raw_path=str(sample_dir),
        min_product_orders=SAMPLE_VARS["min_product_orders"],
        min_pair_orders=SAMPLE_VARS["min_pair_orders"],
    )
    run_id = "pytest"
    for stage in ("setup", "bronze", "silver", "gold", "quality", "optimize"):
        run_stage(spark, stage, s, mode="full", run_id=run_id)

    log = spark.table("t_ops.pipeline_runs").where("run_id = 'pytest'").collect()
    assert [r["stage"] for r in sorted(log, key=lambda r: r["started_at"])] == [
        "setup", "bronze", "silver", "gold", "quality", "optimize"
    ]
    assert all(r["status"] == "SUCCESS" for r in log)

    gold_rows = json.loads(next(r for r in log if r["stage"] == "gold")["details"])["rows"]
    assert gold_rows["mart_time_patterns"] == 168
    assert gold_rows["mart_basket_affinity"] > 0
