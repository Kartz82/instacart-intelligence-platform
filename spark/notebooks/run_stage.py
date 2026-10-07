# Databricks notebook source
# MAGIC %md
# MAGIC # Instacart lakehouse — run one pipeline stage
# MAGIC
# MAGIC Every task in the `instacart_lakehouse` Job runs this notebook with a different `stage`.
# MAGIC All logic lives in `spark/instacart_spark/` so it is unit-tested outside Databricks;
# MAGIC this notebook only reads the widgets and calls `pipeline.run_stage`.
# MAGIC
# MAGIC | Widget | Meaning |
# MAGIC | --- | --- |
# MAGIC | `stage` | setup · bronze · silver · gold · quality · optimize |
# MAGIC | `mode` | `full` rebuilds from the CSVs; `incremental` MERGEs one wave |
# MAGIC | `wave` | wave number for incremental mode (0 = order numbers 1-10, 1 = 11-20, ...) |
# MAGIC | `catalog` | Unity Catalog catalog (Free Edition default: `workspace`) |
# MAGIC | `raw_path` | folder holding the Kaggle CSVs, normally the `raw` volume |
# MAGIC | `run_id` | groups the stages of one Job run in `instacart_ops.pipeline_runs` |

# COMMAND ----------

import os
import sys

# This notebook sits in <git folder>/spark/notebooks; the package is in <git folder>/spark.
sys.path.insert(0, os.path.abspath(".."))

# COMMAND ----------

dbutils.widgets.dropdown("stage", "setup", ["setup", "bronze", "silver", "gold", "quality", "optimize"])  # noqa: F821
dbutils.widgets.dropdown("mode", "full", ["full", "incremental"])  # noqa: F821
dbutils.widgets.text("wave", "")  # noqa: F821
dbutils.widgets.text("catalog", "workspace")  # noqa: F821
dbutils.widgets.text("raw_path", "/Volumes/workspace/instacart_bronze/raw")  # noqa: F821
dbutils.widgets.text("run_id", "")  # noqa: F821

w = {k: dbutils.widgets.get(k) for k in ["stage", "mode", "wave", "catalog", "raw_path", "run_id"]}  # noqa: F821
print(w)

# COMMAND ----------

from instacart_spark.config import Settings
from instacart_spark.pipeline import run_stage

settings = Settings().with_overrides(catalog=w["catalog"] or None, raw_path=w["raw_path"], storage_format="delta")
log = run_stage(
    spark,  # noqa: F821  (provided by Databricks)
    w["stage"],
    settings,
    mode=w["mode"],
    wave=int(w["wave"]) if w["wave"].strip() else None,
    run_id=w["run_id"] or None,
)

# COMMAND ----------

display(spark.table(settings.table("ops", "pipeline_runs")).where(f"run_id = '{log.run_id}'"))  # noqa: F821
