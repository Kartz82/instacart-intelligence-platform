"""Pipeline stages. The Databricks Job runs one task per stage, all calling ``run_stage``.

    setup     create the four schemas (and the raw-data volume when a catalog is set)
    bronze    full: overwrite bronze from the CSVs
              incremental: MERGE one wave of orders + line items into bronze
    silver    full: rebuild silver from bronze
              incremental: MERGE the wave into dim_orders / fact, recompute touched customers
    gold      rebuild the five marts from silver
    quality   run the data-quality gates; raises (fails the task) on any violation
    optimize  OPTIMIZE + Z-ORDER the large silver tables, record files before/after

Every stage is timed into ``<ops schema>.pipeline_runs``.
"""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession

from . import bronze, delta_ops, gold, incremental, quality, silver
from .config import Settings
from .runlog import RunLog

STAGES = ("setup", "bronze", "silver", "gold", "quality", "optimize")
MODES = ("full", "incremental")

BRONZE_TABLES = ("departments", "aisles", "products", "orders", "order_products")
LOOKUPS = ("stg_products", "stg_aisles", "stg_departments")
SILVER_TABLES = ("dim_orders", "dim_customers", "dim_products", "dim_time", "fact_order_items") + LOOKUPS

# Columns to cluster on during OPTIMIZE: the keys the gold marts group or join by.
ZORDER = {
    "fact_order_items": ["product_id", "order_id"],
    "dim_orders": ["user_id"],
}


# --------------------------------------------------------------------------- helpers


def _exists(spark: SparkSession, table: str) -> bool:
    return spark.catalog.tableExists(table)


def _overwrite(df: DataFrame, table: str, fmt: str) -> None:
    (
        df.write.format(fmt)
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(table)
    )


def _read_layer(spark: SparkSession, s: Settings, layer: str, names) -> dict[str, DataFrame]:
    return {n: spark.table(s.table(layer, n)) for n in names}


def _upsert(spark: SparkSession, s: Settings, table: str, df: DataFrame, keys: list[str]) -> dict:
    """Create on first run, MERGE afterwards."""
    if not _exists(spark, table):
        _overwrite(df, table, s.storage_format)
        return {"created": True}
    if s.storage_format != "delta":
        raise RuntimeError("incremental mode needs Delta tables (LAKEHOUSE_FORMAT=delta)")
    return incremental.delta_merge(spark, table, df, keys)


# ---------------------------------------------------------------------------- stages


def stage_setup(spark: SparkSession, s: Settings, d: dict) -> None:
    for schema in s.schema_names():
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    if s.catalog:
        volume = f"{s.catalog}.{s.bronze_schema}.raw"
        spark.sql(f"CREATE VOLUME IF NOT EXISTS {volume}")
        d["volume"] = f"/Volumes/{s.catalog}/{s.bronze_schema}/raw"
    d["schemas"] = s.schema_names()


def stage_bronze(spark: SparkSession, s: Settings, mode: str, wave: int | None, d: dict) -> None:
    raw = bronze.read_raw_csvs(spark, s.raw_path)
    for name in bronze.REFERENCE_TABLES:  # tiny lookups: always a full refresh
        _overwrite(bronze.stamp_lineage(raw[name], 0), s.table("bronze", name), s.storage_format)

    if mode == "full":
        for name in ("orders", "order_products"):
            _overwrite(bronze.stamp_lineage(raw[name], 0), s.table("bronze", name), s.storage_format)
    else:
        w_orders, w_items = bronze.select_wave(raw["orders"], raw["order_products"], wave, s.wave_size)
        batch = wave + 1
        d["merge"] = {
            "orders": _upsert(spark, s, s.table("bronze", "orders"),
                              bronze.stamp_lineage(w_orders, batch), incremental.KEYS["orders"]),
            "order_products": _upsert(spark, s, s.table("bronze", "order_products"),
                                      bronze.stamp_lineage(w_items, batch), incremental.KEYS["order_products"]),
        }
    d["rows"] = {n: spark.table(s.table("bronze", n)).count() for n in BRONZE_TABLES}


def stage_silver(spark: SparkSession, s: Settings, mode: str, wave: int | None, d: dict) -> None:
    b = _read_layer(spark, s, "bronze", BRONZE_TABLES)
    s_products = silver.stg_products(b["products"])
    s_aisles = silver.stg_aisles(b["aisles"])
    s_depts = silver.stg_departments(b["departments"])

    # Lookups and conformed dimensions that do not depend on orders: full refresh.
    _overwrite(s_products, s.table("silver", "stg_products"), s.storage_format)
    _overwrite(s_aisles, s.table("silver", "stg_aisles"), s.storage_format)
    _overwrite(s_depts, s.table("silver", "stg_departments"), s.storage_format)
    _overwrite(silver.dim_products(s_products, s_aisles, s_depts), s.table("silver", "dim_products"), s.storage_format)
    _overwrite(silver.dim_time(spark), s.table("silver", "dim_time"), s.storage_format)

    if mode == "full":
        built = silver.build_silver(spark, b)
        for name in ("dim_orders", "fact_order_items", "dim_customers"):
            _overwrite(built[name], s.table("silver", name), s.storage_format)
    else:
        w_orders, w_items = bronze.select_wave(b["orders"], b["order_products"], wave, s.wave_size)
        updates = incremental.wave_silver_updates(w_orders, w_items, s_products, s_aisles, s_depts)
        d["merge"] = {}
        for name in ("dim_orders", "fact_order_items"):
            d["merge"][name] = _upsert(spark, s, s.table("silver", name), updates[name], incremental.KEYS[name])
        customers = incremental.customer_updates(spark.table(s.table("silver", "dim_orders")), w_orders)
        d["merge"]["dim_customers"] = _upsert(
            spark, s, s.table("silver", "dim_customers"), customers, incremental.KEYS["dim_customers"]
        )
    d["rows"] = {n: spark.table(s.table("silver", n)).count() for n in SILVER_TABLES}


def stage_gold(spark: SparkSession, s: Settings, d: dict) -> None:
    sv = _read_layer(spark, s, "silver", SILVER_TABLES)
    marts = gold.build_gold(sv, min_product_orders=s.min_product_orders, min_pair_orders=s.min_pair_orders)
    for name, df in marts.items():
        _overwrite(df, s.table("gold", name), s.storage_format)
    d["rows"] = {n: spark.table(s.table("gold", n)).count() for n in marts}


def stage_quality(spark: SparkSession, s: Settings, d: dict) -> None:
    report = quality.run_all(
        _read_layer(spark, s, "bronze", BRONZE_TABLES),
        _read_layer(spark, s, "silver", SILVER_TABLES),
        _read_layer(spark, s, "gold", gold.GOLD_KEYS),
    )
    d["checks"] = report.checks
    report.raise_if_failed()


def stage_optimize(spark: SparkSession, s: Settings, d: dict) -> None:
    if s.storage_format != "delta":
        d["skipped"] = "OPTIMIZE needs Delta tables"
        return
    d["optimize"] = [delta_ops.optimize(spark, s.table("silver", t), cols) for t, cols in ZORDER.items()]


# --------------------------------------------------------------------------- entry


def run_stage(
    spark: SparkSession,
    stage: str,
    settings: Settings,
    *,
    mode: str = "full",
    wave: int | None = None,
    run_id: str | None = None,
) -> RunLog:
    if stage not in STAGES:
        raise ValueError(f"stage must be one of {STAGES}, got {stage!r}")
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    if mode == "incremental" and stage in ("bronze", "silver") and wave is None:
        raise ValueError("incremental bronze/silver needs a wave number")

    # The run-log row is written when the stage finishes, so for `setup` the ops schema
    # it lands in already exists by then.
    log = RunLog(spark, settings.table("ops", "pipeline_runs"), run_id, settings.storage_format)
    with log.stage(stage, mode, wave) as d:
        if stage == "setup":
            stage_setup(spark, settings, d)
        elif stage == "bronze":
            stage_bronze(spark, settings, mode, wave, d)
        elif stage == "silver":
            stage_silver(spark, settings, mode, wave, d)
        elif stage == "gold":
            stage_gold(spark, settings, d)
        elif stage == "quality":
            stage_quality(spark, settings, d)
        elif stage == "optimize":
            stage_optimize(spark, settings, d)
    return log
