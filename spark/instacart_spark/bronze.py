"""Bronze layer: raw Kaggle CSVs -> typed DataFrames stamped with lineage columns.

Bronze keeps the source shape. The only additions are lineage columns:
    _batch_id      which load produced the row (0 for a full load)
    _ingested_at   load timestamp
    _source_file   the file the row came from

Schemas are explicit and the read is FAILFAST: a malformed row stops the load instead of
silently becoming a null, which is the Spark equivalent of the dbt source tests.
"""

from __future__ import annotations

import os

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, IntegerType, StringType, StructField, StructType

RAW_SCHEMAS: dict[str, StructType] = {
    "departments": StructType(
        [
            StructField("department_id", IntegerType(), False),
            StructField("department", StringType(), False),
        ]
    ),
    "aisles": StructType(
        [
            StructField("aisle_id", IntegerType(), False),
            StructField("aisle", StringType(), False),
        ]
    ),
    "products": StructType(
        [
            StructField("product_id", IntegerType(), False),
            StructField("product_name", StringType(), False),
            StructField("aisle_id", IntegerType(), False),
            StructField("department_id", IntegerType(), False),
        ]
    ),
    # days_since_prior_order is empty on a customer's first order, hence nullable.
    "orders": StructType(
        [
            StructField("order_id", IntegerType(), False),
            StructField("user_id", IntegerType(), False),
            StructField("eval_set", StringType(), False),
            StructField("order_number", IntegerType(), False),
            StructField("order_dow", IntegerType(), False),
            StructField("order_hour_of_day", IntegerType(), False),
            StructField("days_since_prior_order", DoubleType(), True),
        ]
    ),
    "order_products": StructType(
        [
            StructField("order_id", IntegerType(), False),
            StructField("product_id", IntegerType(), False),
            StructField("add_to_cart_order", IntegerType(), False),
            StructField("reordered", IntegerType(), False),
        ]
    ),
}

REFERENCE_TABLES = ("departments", "aisles", "products")
LINEAGE_COLUMNS = ("_batch_id", "_ingested_at", "_source_file")


def _read_csv(spark: SparkSession, path: str, schema: StructType) -> DataFrame:
    return (
        spark.read.option("header", True)
        .option("mode", "FAILFAST")
        .option("escape", '"')  # Kaggle quotes fields and doubles embedded quotes
        .schema(schema)
        .csv(path)
        .select("*", F.col("_metadata.file_path").alias("_source_file"))
    )


def read_raw_csvs(spark: SparkSession, raw_path: str) -> dict[str, DataFrame]:
    """Read every raw table. ``order_products`` comes from the pre-unioned
    ``order_products.csv`` if present, otherwise from prior + train unioned here."""
    tables: dict[str, DataFrame] = {}
    for name in ("departments", "aisles", "products", "orders"):
        tables[name] = _read_csv(spark, os.path.join(raw_path, f"{name}.csv"), RAW_SCHEMAS[name])

    combined = os.path.join(raw_path, "order_products.csv")
    if os.path.exists(combined):
        tables["order_products"] = _read_csv(spark, combined, RAW_SCHEMAS["order_products"])
    else:
        prior = _read_csv(
            spark, os.path.join(raw_path, "order_products__prior.csv"), RAW_SCHEMAS["order_products"]
        )
        train = _read_csv(
            spark, os.path.join(raw_path, "order_products__train.csv"), RAW_SCHEMAS["order_products"]
        )
        tables["order_products"] = prior.unionByName(train)
    return tables


def select_wave(
    orders: DataFrame, order_products: DataFrame, wave: int, wave_size: int
) -> tuple[DataFrame, DataFrame]:
    """Simulate one incremental arrival: the orders whose ``order_number`` falls in the
    wave's window (wave 0 = order numbers 1..wave_size, wave 1 = the next window, ...),
    plus their line items. In effect, the next stretch of every customer's history lands.

    The Kaggle extract is static, so this is how a "daily batch" is modelled."""
    low = wave * wave_size + 1
    high = (wave + 1) * wave_size
    wave_orders = orders.where(F.col("order_number").between(low, high))
    wave_items = order_products.join(
        wave_orders.select("order_id"), on="order_id", how="left_semi"
    )
    return wave_orders, wave_items


def stamp_lineage(df: DataFrame, batch_id: int) -> DataFrame:
    return df.withColumn("_batch_id", F.lit(batch_id).cast("int")).withColumn(
        "_ingested_at", F.current_timestamp()
    )
