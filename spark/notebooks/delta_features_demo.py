# Databricks notebook source
# MAGIC %md
# MAGIC # Delta Lake features on the Instacart silver layer
# MAGIC
# MAGIC Run this **after** the Job has loaded the data in `incremental` mode for a few waves,
# MAGIC so `silver.fact_order_items` has a version history to travel through.
# MAGIC
# MAGIC 1. Version history of the fact table (one MERGE per wave)
# MAGIC 2. Time travel: row counts at every version
# MAGIC 3. A deliberate bad write, detected, then undone with `RESTORE`
# MAGIC 4. `OPTIMIZE ... ZORDER BY` with files before/after, measured by `DESCRIBE DETAIL`
# MAGIC 5. Run timings recorded in `instacart_ops.pipeline_runs`
# MAGIC
# MAGIC Every number this notebook prints is read from the tables. Copy figures into the
# MAGIC README only from this output.

# COMMAND ----------

import os
import sys

sys.path.insert(0, os.path.abspath(".."))

from instacart_spark import delta_ops
from instacart_spark.config import Settings

dbutils.widgets.text("catalog", "workspace")  # noqa: F821
s = Settings().with_overrides(catalog=dbutils.widgets.get("catalog") or None)  # noqa: F821
FACT = s.table("silver", "fact_order_items")

# COMMAND ----------

# MAGIC %md ## 1. Version history

# COMMAND ----------

display(delta_ops.history(spark, FACT))  # noqa: F821

# COMMAND ----------

# MAGIC %md ## 2. Time travel — the fact table as of each version

# COMMAND ----------

hist = delta_ops.history(spark, FACT, limit=100).select("version", "operation").orderBy("version").collect()
rows = [(h["version"], h["operation"], delta_ops.read_version(spark, FACT, h["version"]).count()) for h in hist]
display(spark.createDataFrame(rows, "version long, operation string, row_count long"))  # noqa: F821

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Recover from a bad write with RESTORE
# MAGIC
# MAGIC Simulates a faulty job that deletes every reordered line. The quality gate would
# MAGIC catch the drift; here the table is rolled back to the version before the bad write.

# COMMAND ----------

good_version = delta_ops.current_version(spark, FACT)
good_count = spark.table(FACT).count()

spark.sql(f"DELETE FROM {FACT} WHERE reordered = 1")
bad_count = spark.table(FACT).count()

delta_ops.restore(spark, FACT, good_version)
restored_count = spark.table(FACT).count()

print(f"version {good_version}: {good_count:,} rows -> bad write: {bad_count:,} -> restored: {restored_count:,}")
assert restored_count == good_count

# COMMAND ----------

# MAGIC %md ## 4. OPTIMIZE + Z-ORDER

# COMMAND ----------

result = delta_ops.optimize(spark, FACT, ["product_id", "order_id"])
print(result)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Measured stage runtimes
# MAGIC
# MAGIC These are the numbers to quote. Each Job run is one `run_id`.

# COMMAND ----------

display(  # noqa: F821
    spark.sql(f"""
        select run_id, stage, mode, wave, status, seconds, started_at
        from {s.table('ops', 'pipeline_runs')}
        order by started_at desc
    """)
)
