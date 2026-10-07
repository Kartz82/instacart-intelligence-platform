"""Incremental loads with Delta MERGE.

The Kaggle extract is static, so arrivals are simulated as "waves" (see
``bronze.select_wave``): each wave is the next window of every customer's order sequence.
A wave flows through the layers like this:

    bronze.orders / bronze.order_products   MERGE on the natural key (idempotent re-runs)
    silver.dim_orders                        MERGE the wave's orders on order_id
    silver.fact_order_items                  MERGE the wave's lines on (order_id, product_id)
    silver.dim_customers                     recompute ONLY the customers in the wave,
                                             from their full order history, MERGE on user_id
    gold.*                                   full rebuild from silver

Why gold is rebuilt rather than merged: the gold marts are small (the largest is
mart_customer_segments, one row per customer) and several are global by definition. A
new order can move every customer's ntile() score in mart_customer_segments, and it
changes every pair's support denominator in mart_basket_affinity. An incremental
gold layer would be more code to be wrong, for little saving.

The merge rule lives in two forms that must agree:
    ``upsert_frame``   pure DataFrame version, used by the local tests
    ``delta_merge``    Delta Lake MERGE INTO, used on Databricks
"""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from . import silver

KEYS: dict[str, list[str]] = {
    "orders": ["order_id"],
    "order_products": ["order_id", "product_id"],
    "dim_orders": ["order_id"],
    "fact_order_items": ["order_id", "product_id"],
    "dim_customers": ["user_id"],
}


def upsert_frame(existing: DataFrame, updates: DataFrame, keys: list[str]) -> DataFrame:
    """MERGE semantics without Delta: matched rows are replaced, new rows inserted."""
    updates = updates.select(*existing.columns)
    return existing.join(updates.select(*keys), on=keys, how="left_anti").unionByName(updates)


def delta_merge(spark: SparkSession, table: str, updates: DataFrame, keys: list[str]) -> dict:
    """MERGE INTO a Delta table on ``keys``. Returns Delta's operation metrics for the
    merge (rows inserted / updated), which the run log records."""
    from delta.tables import DeltaTable

    target = DeltaTable.forName(spark, table)
    condition = " AND ".join(f"t.{k} = s.{k}" for k in keys)
    (
        target.alias("t")
        .merge(updates.alias("s"), condition)
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute()
    )
    last = target.history(1).select("operation", "operationMetrics").first()
    metrics = dict(last["operationMetrics"] or {}) if last and last["operation"] == "MERGE" else {}
    return {
        k: int(metrics[k])
        for k in ("numTargetRowsInserted", "numTargetRowsUpdated", "numSourceRows")
        if k in metrics
    }


def wave_silver_updates(
    wave_orders: DataFrame,
    wave_items: DataFrame,
    stg_products: DataFrame,
    stg_aisles: DataFrame,
    stg_departments: DataFrame,
) -> dict[str, DataFrame]:
    """Silver rows produced by one wave, before customers are recomputed.

    Correct because a wave carries an order together with all of its line items, so an
    order's basket_size is final the first time it is merged."""
    s_orders = silver.stg_orders(wave_orders)
    s_items = silver.stg_order_products(wave_items)
    return {
        "dim_orders": silver.dim_orders(s_orders, s_items),
        "fact_order_items": silver.fact_order_items(
            s_orders, s_items, stg_products, stg_aisles, stg_departments
        ),
    }


def customer_updates(dim_orders_after_merge: DataFrame, wave_orders: DataFrame) -> DataFrame:
    """dim_customers rows for the customers the wave touched, recomputed from their whole
    history (which is why this runs after dim_orders has been merged)."""
    affected = wave_orders.select("user_id").distinct()
    history = dim_orders_after_merge.join(F.broadcast(affected), on="user_id", how="left_semi")
    return silver.dim_customers(silver.customer_history_from_orders(history))
