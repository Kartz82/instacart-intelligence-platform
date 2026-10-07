"""Properties the Spark pipeline must hold regardless of dbt. These mirror the dbt
singular tests and run without dbt installed."""

from __future__ import annotations

from conftest import SAMPLE_VARS
from instacart_spark import bronze, gold, quality, silver
from pyspark.sql import functions as F


def _layers(spark, sample_dir):
    raw = bronze.read_raw_csvs(spark, str(sample_dir))
    s = silver.build_silver(spark, raw)
    return raw, s, gold.build_gold(s, **SAMPLE_VARS)


def test_dim_time_is_complete_grid(spark):
    t = silver.dim_time(spark)
    assert t.count() == 168
    assert t.select("time_key").distinct().count() == 168


def test_time_patterns_reconcile_to_orders(spark, sample_dir):
    _, s, g = _layers(spark, sample_dir)
    mart_total = g["mart_time_patterns"].agg(F.sum("total_orders")).first()[0]
    assert mart_total == s["dim_orders"].count()
    assert g["mart_time_patterns"].count() == 168


def test_fact_grain_is_unique(spark, sample_dir):
    _, s, _ = _layers(spark, sample_dir)
    fact = s["fact_order_items"]
    assert fact.count() == fact.select("order_id", "product_id").distinct().count()


def test_quality_gates_pass_on_clean_data(spark, sample_dir):
    raw, s, g = _layers(spark, sample_dir)
    report = quality.run_all(raw, s, g)
    assert report.ok, report.failures


def test_quality_gate_catches_orphan_line(spark, sample_dir):
    raw, s, g = _layers(spark, sample_dir)
    orphan = spark.createDataFrame(
        [(999999999, 1, 1, 0)], raw["order_products"].drop("_source_file").schema
    )
    raw_bad = dict(raw)
    raw_bad["order_products"] = raw["order_products"].drop("_source_file").unionByName(orphan)
    report = quality.run_all(raw_bad, s, g)
    assert not report.ok
    assert any("order_products.order_id" in f for f in report.failures)


def test_wave_split_partitions_every_order(spark, sample_dir):
    raw = bronze.read_raw_csvs(spark, str(sample_dir))
    orders, items = raw["orders"], raw["order_products"]
    total_orders, total_items = 0, 0
    for wave in range(3):  # synthetic users have at most 30 orders -> 3 waves of 10
        o, i = bronze.select_wave(orders, items, wave, 10)
        total_orders += o.count()
        total_items += i.count()
    assert total_orders == orders.count()
    assert total_items == items.count()
