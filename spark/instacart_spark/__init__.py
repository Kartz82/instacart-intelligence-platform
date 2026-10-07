"""PySpark / Delta Lake implementation of the Instacart platform's medallion layers.

The dbt project under ``dbt/`` stays the reference implementation. Every transformation
in this package is a port of a dbt model and is reconciled against the dbt output
(see ``reconcile.py`` and ``tests/``).

Layering:
    config / session   settings and Spark session construction
    bronze             raw CSV -> typed, lineage-stamped bronze tables
    silver             dbt staging + intermediate + core models, as pure DataFrame functions
    gold               dbt marts, as pure DataFrame functions
    incremental        Delta MERGE upserts
    delta_ops          OPTIMIZE / history / time travel / restore helpers
    quality            data-quality gates that fail the job (the dbt test equivalents)
    runlog             stage timing written to a Delta table
    reconcile          compare Spark marts against dbt-built marts
    pipeline           the stage orchestration the Databricks Job calls
"""

__version__ = "0.1.0"
