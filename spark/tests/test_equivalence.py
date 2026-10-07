"""The PySpark ports must produce the same marts as the dbt models, row for row."""

from __future__ import annotations

import pytest
from conftest import SAMPLE_VARS
from instacart_spark import bronze, gold, silver
from instacart_spark.reconcile import compare_frames, reconcile_all, to_markdown


@pytest.fixture(scope="module")
def spark_layers(spark, sample_dir):
    raw = bronze.read_raw_csvs(spark, str(sample_dir))
    s = silver.build_silver(spark, raw)
    g = gold.build_gold(s, **SAMPLE_VARS)
    return s, g


def test_gold_marts_match_dbt(spark_layers, dbt_marts):
    _, g = spark_layers
    spark_pd = {name: df.toPandas() for name, df in g.items()}
    results = reconcile_all(spark_pd, dbt_marts)
    print(to_markdown(results, "Spark vs dbt (synthetic sample)"))
    assert len(results) == 5
    assert all(r.ok for r in results), to_markdown(results, "mismatch")


def test_affinity_sample_is_not_trivially_empty(spark_layers):
    # A reconciliation of two empty tables proves nothing.
    _, g = spark_layers
    assert g["mart_basket_affinity"].count() > 0


@pytest.mark.parametrize(
    "table,keys",
    [
        ("dim_orders", ["order_id"]),
        ("dim_customers", ["user_id"]),
        ("fact_order_items", ["order_id", "product_id"]),
    ],
)
def test_silver_matches_dbt(spark_layers, dbt_marts, table, keys):
    s, _ = spark_layers
    result = compare_frames(table, s[table].toPandas(), dbt_marts[table], keys)
    assert result.ok, result
