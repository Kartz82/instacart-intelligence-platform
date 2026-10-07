# Databricks notebook source
# MAGIC %md
# MAGIC # Reconcile the Spark gold marts against the dbt marts
# MAGIC
# MAGIC The dbt project on PostgreSQL is the reference build. This notebook compares the
# MAGIC Databricks gold tables against the dbt marts row for row.
# MAGIC
# MAGIC **Before running:** export the dbt marts from Postgres on your machine with
# MAGIC `python spark/scripts/export_dbt_marts.py` and upload the five `.parquet` files to
# MAGIC `/Volumes/<catalog>/instacart_bronze/raw/dbt_marts/`.
# MAGIC
# MAGIC The Markdown table this prints is the evidence for any "reconciled to dbt" claim.

# COMMAND ----------

import os
import sys

sys.path.insert(0, os.path.abspath(".."))

from instacart_spark.config import Settings
from instacart_spark.gold import GOLD_KEYS
from instacart_spark.reconcile import reconcile_all, to_markdown

dbutils.widgets.text("catalog", "workspace")  # noqa: F821
dbutils.widgets.text("dbt_marts_path", "/Volumes/workspace/instacart_bronze/raw/dbt_marts")  # noqa: F821
s = Settings().with_overrides(catalog=dbutils.widgets.get("catalog") or None)  # noqa: F821
path = dbutils.widgets.get("dbt_marts_path")  # noqa: F821

# COMMAND ----------

# The marts are small (largest: one row per customer), so comparing in pandas is fine.
spark_marts = {m: spark.table(s.table("gold", m)).toPandas() for m in GOLD_KEYS}  # noqa: F821
dbt_marts = {m: spark.read.parquet(f"{path}/{m}.parquet").toPandas() for m in GOLD_KEYS}  # noqa: F821

results = reconcile_all(spark_marts, dbt_marts)
report = to_markdown(results, "Spark (Databricks) vs dbt (PostgreSQL)")
print(report)

# COMMAND ----------

displayHTML("<pre>" + report + "</pre>")  # noqa: F821
assert all(r.ok for r in results), "one or more marts do not reconcile; see the table above"
