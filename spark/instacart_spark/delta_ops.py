"""Delta Lake table maintenance and time travel.

Everything here is a thin, logged wrapper over Delta SQL so the commands a reviewer
reads in the notebooks are the commands that ran. Numbers reported by these helpers
(file counts, sizes, versions) come from DESCRIBE DETAIL / DESCRIBE HISTORY, not from
estimates.
"""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession


def detail(spark: SparkSession, table: str) -> dict:
    """numFiles and sizeInBytes from DESCRIBE DETAIL."""
    row = spark.sql(f"DESCRIBE DETAIL {table}").select("numFiles", "sizeInBytes").first()
    return {"num_files": int(row["numFiles"]), "size_bytes": int(row["sizeInBytes"])}


def history(spark: SparkSession, table: str, limit: int = 20) -> DataFrame:
    return spark.sql(f"DESCRIBE HISTORY {table} LIMIT {int(limit)}").select(
        "version", "timestamp", "operation", "operationParameters", "operationMetrics"
    )


def current_version(spark: SparkSession, table: str) -> int:
    return int(spark.sql(f"DESCRIBE HISTORY {table} LIMIT 1").first()["version"])


def read_version(spark: SparkSession, table: str, version: int) -> DataFrame:
    """Time travel: the table as it was at ``version``."""
    return spark.sql(f"SELECT * FROM {table} VERSION AS OF {int(version)}")


def optimize(spark: SparkSession, table: str, zorder_by: list[str] | None = None) -> dict:
    """OPTIMIZE (file compaction), optionally with Z-ORDER clustering.

    Returns DESCRIBE DETAIL before and after, plus the OPTIMIZE metrics row, so the run
    log carries the measured effect rather than a claim about it."""
    before = detail(spark, table)
    clause = f" ZORDER BY ({', '.join(zorder_by)})" if zorder_by else ""
    result = spark.sql(f"OPTIMIZE {table}{clause}").first()
    after = detail(spark, table)
    row = result.asDict(recursive=True) if result is not None else {}
    metrics = row.get("metrics") or {}
    return {
        "table": table,
        "zorder_by": zorder_by or [],
        "files_before": before["num_files"],
        "files_after": after["num_files"],
        "bytes_before": before["size_bytes"],
        "bytes_after": after["size_bytes"],
        "files_added": metrics.get("numFilesAdded"),
        "files_removed": metrics.get("numFilesRemoved"),
    }


def restore(spark: SparkSession, table: str, version: int) -> None:
    spark.sql(f"RESTORE TABLE {table} TO VERSION AS OF {int(version)}")
