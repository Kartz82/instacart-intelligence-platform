"""Real Delta MERGE / OPTIMIZE / time travel, through the actual pipeline stages.

Needs the Delta jars, so it only runs when TEST_WITH_DELTA=1 (as in CI, where Maven is
reachable). It loads three waves incrementally into one set of schemas and a full load
into another, then requires the gold marts to be identical.
"""

from __future__ import annotations

import pytest
from conftest import SAMPLE_VARS
from instacart_spark import delta_ops
from instacart_spark.config import Settings
from instacart_spark.gold import GOLD_KEYS
from instacart_spark.pipeline import run_stage
from instacart_spark.reconcile import compare_frames


def _settings(prefix, sample_dir):
    return Settings(
        catalog=None,
        bronze_schema=f"{prefix}_bronze",
        silver_schema=f"{prefix}_silver",
        gold_schema=f"{prefix}_gold",
        ops_schema=f"{prefix}_ops",
        storage_format="delta",
        raw_path=str(sample_dir),
        min_product_orders=SAMPLE_VARS["min_product_orders"],
        min_pair_orders=SAMPLE_VARS["min_pair_orders"],
    )


def test_incremental_merge_matches_full_load(spark, sample_dir):
    if "Delta" not in spark.conf.get("spark.sql.extensions", ""):
        pytest.skip("Delta not enabled (set TEST_WITH_DELTA=1)")

    full = _settings("dfull", sample_dir)
    for stage in ("setup", "bronze", "silver", "gold", "quality"):
        run_stage(spark, stage, full, mode="full", run_id="full")

    inc = _settings("dinc", sample_dir)
    run_stage(spark, "setup", inc, run_id="inc")
    for wave in range(3):
        run_stage(spark, "bronze", inc, mode="incremental", wave=wave, run_id="inc")
        run_stage(spark, "silver", inc, mode="incremental", wave=wave, run_id="inc")
    # re-running a wave must be a no-op (MERGE on natural keys)
    run_stage(spark, "bronze", inc, mode="incremental", wave=1, run_id="inc")
    run_stage(spark, "silver", inc, mode="incremental", wave=1, run_id="inc")
    for stage in ("gold", "quality", "optimize"):
        run_stage(spark, stage, inc, mode="full", run_id="inc")

    for name, keys in GOLD_KEYS.items():
        r = compare_frames(
            name,
            spark.table(inc.table("gold", name)).toPandas(),
            spark.table(full.table("gold", name)).toPandas(),
            keys,
        )
        assert r.ok, r

    fact = inc.table("silver", "fact_order_items")
    # one create + MERGE per later wave + the re-run + OPTIMIZE -> version history exists
    assert delta_ops.current_version(spark, fact) >= 3
    v0 = delta_ops.read_version(spark, fact, 0).count()
    assert 0 < v0 < spark.table(fact).count()
