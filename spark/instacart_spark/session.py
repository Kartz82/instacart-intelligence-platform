"""Spark session construction.

On Databricks a session already exists and its configuration is managed for you (and on
serverless compute most Spark configs cannot be set), so this module only calls
``getOrCreate()`` there. Locally it builds a small session, with Delta Lake enabled when
the Delta jars can be resolved.
"""

from __future__ import annotations

import os

from pyspark.sql import SparkSession


def on_databricks() -> bool:
    return "DATABRICKS_RUNTIME_VERSION" in os.environ or "DATABRICKS_HOST" in os.environ


def get_spark(app_name: str = "instacart-lakehouse", *, delta: bool = True, cores: int = 2) -> SparkSession:
    if on_databricks():
        return SparkSession.builder.getOrCreate()

    builder = (
        SparkSession.builder.master(f"local[{cores}]")
        .appName(app_name)
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.warehouse.dir", os.getenv("SPARK_WAREHOUSE_DIR", "spark-warehouse"))
    )
    if delta:
        from delta import configure_spark_with_delta_pip

        builder = (
            builder.config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
            .config(
                "spark.sql.catalog.spark_catalog",
                "org.apache.spark.sql.delta.catalog.DeltaCatalog",
            )
        )
        return configure_spark_with_delta_pip(builder).getOrCreate()
    return builder.getOrCreate()
