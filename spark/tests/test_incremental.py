"""Loading the data wave by wave must end in exactly the state a full load produces.

This exercises the incremental logic with ``upsert_frame``, the pure-DataFrame form of
the MERGE rule. The Delta ``MERGE INTO`` that runs on Databricks applies the same rule;
it is not executed here because the Delta jars cannot be downloaded in this environment.
"""

from __future__ import annotations

from conftest import SAMPLE_VARS
from instacart_spark import bronze, gold, incremental, silver
from instacart_spark.gold import GOLD_KEYS
from instacart_spark.reconcile import compare_frames


def test_waves_converge_to_full_load(spark, sample_dir):
    raw = bronze.read_raw_csvs(spark, str(sample_dir))
    full = silver.build_silver(spark, raw)
    full_gold = gold.build_gold(full, **SAMPLE_VARS)

    s_p = silver.stg_products(raw["products"])
    s_a = silver.stg_aisles(raw["aisles"])
    s_d = silver.stg_departments(raw["departments"])

    state = None
    for wave in range(3):  # synthetic users have <= 30 orders; wave_size 10
        w_orders, w_items = bronze.select_wave(raw["orders"], raw["order_products"], wave, 10)
        updates = incremental.wave_silver_updates(w_orders, w_items, s_p, s_a, s_d)
        if state is None:
            state = {k: v for k, v in updates.items()}
        else:
            for name, df in updates.items():
                state[name] = incremental.upsert_frame(state[name], df, incremental.KEYS[name])
        state = {k: v.localCheckpoint() for k, v in state.items()}

        cust = incremental.customer_updates(state["dim_orders"], w_orders)
        if "dim_customers" in state:
            state["dim_customers"] = incremental.upsert_frame(state["dim_customers"], cust, ["user_id"])
        else:
            state["dim_customers"] = cust
        state["dim_customers"] = state["dim_customers"].localCheckpoint()

        # Re-running the same wave must change nothing (idempotency).
        if wave == 1:
            before = state["dim_orders"].count()
            rerun = incremental.upsert_frame(state["dim_orders"], updates["dim_orders"], ["order_id"])
            assert rerun.count() == before

    for name, keys in [
        ("dim_orders", ["order_id"]),
        ("fact_order_items", ["order_id", "product_id"]),
        ("dim_customers", ["user_id"]),
    ]:
        r = compare_frames(name, state[name].toPandas(), full[name].toPandas(), keys)
        assert r.ok, r

    inc_silver = {**full, **state}
    inc_gold = gold.build_gold(inc_silver, **SAMPLE_VARS)
    for name, keys in GOLD_KEYS.items():
        r = compare_frames(name, inc_gold[name].toPandas(), full_gold[name].toPandas(), keys)
        assert r.ok, r
