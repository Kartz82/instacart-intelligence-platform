"""Stage timing, written to a Delta table so runtimes are measured, queryable evidence.

Every pipeline stage runs inside ``RunLog.stage(...)``. One row per stage execution:

    run_id, stage, mode, wave, status, started_at, finished_at, seconds, details (JSON)

``details`` holds row counts, MERGE metrics and OPTIMIZE before/after file counts. The
README and resume bullets may only quote runtimes that appear in this table.
"""

from __future__ import annotations

import json
import time
import traceback
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

RUNLOG_SCHEMA = StructType(
    [
        StructField("run_id", StringType(), False),
        StructField("stage", StringType(), False),
        StructField("mode", StringType(), True),
        StructField("wave", IntegerType(), True),
        StructField("status", StringType(), False),
        StructField("started_at", TimestampType(), False),
        StructField("finished_at", TimestampType(), False),
        StructField("seconds", DoubleType(), False),
        StructField("details", StringType(), True),
    ]
)


class RunLog:
    def __init__(
        self,
        spark: SparkSession,
        table: str | None,
        run_id: str | None = None,
        storage_format: str = "delta",
    ):
        self.spark = spark
        self.table = table
        self.storage_format = storage_format
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self.rows: list[tuple] = []

    @contextmanager
    def stage(self, name: str, mode: str | None = None, wave: int | None = None):
        details: dict = {}
        started = datetime.now(timezone.utc)
        t0 = time.perf_counter()
        status = "SUCCESS"
        try:
            yield details
        except Exception as exc:
            status = "FAILED"
            details["error"] = f"{type(exc).__name__}: {exc}"[:2000]
            details["traceback"] = traceback.format_exc()[-2000:]
            raise
        finally:
            seconds = round(time.perf_counter() - t0, 3)
            row = (
                self.run_id,
                name,
                mode,
                wave,
                status,
                started.replace(tzinfo=None),
                datetime.now(timezone.utc).replace(tzinfo=None),
                seconds,
                json.dumps(details, default=str),
            )
            self.rows.append(row)
            print(f"[runlog] {self.run_id} {name} {status} {seconds:.1f}s {json.dumps(details, default=str)[:500]}")
            self._flush(row)

    def _flush(self, row: tuple) -> None:
        if not self.table:
            return
        try:
            self.spark.createDataFrame([row], RUNLOG_SCHEMA).write.format(self.storage_format).mode("append").saveAsTable(
                self.table
            )
        except Exception as exc:  # the log must never mask the stage's own result
            print(f"[runlog] could not write to {self.table}: {exc}")
