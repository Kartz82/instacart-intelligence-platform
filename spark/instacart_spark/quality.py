"""Data-quality gates for the Spark pipeline: the dbt tests that matter most, re-stated
as checks that fail the Databricks Job instead of letting a bad gold table publish.

Each check returns the count of offending rows; zero passes. ``run_all`` collects every
failure before raising so one run reports everything that is wrong, not just the first.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


class DataQualityError(RuntimeError):
    pass


@dataclass
class QualityReport:
    checks: dict[str, int] = field(default_factory=dict)

    @property
    def failures(self) -> list[str]:
        return [f"{name}: {n} offending rows" for name, n in self.checks.items() if n]

    @property
    def ok(self) -> bool:
        return not self.failures

    def raise_if_failed(self) -> None:
        if not self.ok:
            raise DataQualityError("; ".join(self.failures))


def nulls(df: DataFrame, col: str) -> int:
    return df.where(F.col(col).isNull()).count()


def duplicates(df: DataFrame, keys: list[str]) -> int:
    return df.groupBy(*keys).count().where(F.col("count") > 1).count()


def orphans(child: DataFrame, parent: DataFrame, key: str) -> int:
    return child.select(key).join(parent.select(key), on=key, how="left_anti").count()


def out_of_set(df: DataFrame, col: str, allowed: list) -> int:
    return df.where(~F.col(col).isin(allowed) | F.col(col).isNull()).count()


def out_of_range(df: DataFrame, col: str, low: float, high: float) -> int:
    return df.where(F.col(col).isNotNull() & ~F.col(col).between(low, high)).count()


def run_all(
    bronze: dict[str, DataFrame], silver: dict[str, DataFrame], gold: dict[str, DataFrame]
) -> QualityReport:
    r = QualityReport()
    b = bronze
    # source integrity (dbt sources.yml)
    r.checks["orders.order_id unique"] = duplicates(b["orders"], ["order_id"])
    r.checks["products.product_id unique"] = duplicates(b["products"], ["product_id"])
    r.checks["order_products.order_id -> orders"] = orphans(b["order_products"], b["orders"], "order_id")
    r.checks["order_products.product_id -> products"] = orphans(
        b["order_products"], b["products"], "product_id"
    )
    r.checks["orders.eval_set accepted values"] = out_of_set(b["orders"], "eval_set", ["prior", "train", "test"])
    r.checks["order_products.reordered in (0,1)"] = out_of_set(b["order_products"], "reordered", [0, 1])

    # grain (dbt singular tests)
    r.checks["fact_order_items grain unique"] = duplicates(silver["fact_order_items"], ["order_id", "product_id"])
    r.checks["dim_customers.user_id unique"] = duplicates(silver["dim_customers"], ["user_id"])
    r.checks["dim_time is 168 rows"] = abs(silver["dim_time"].count() - 168)

    # marts
    tp = gold["mart_time_patterns"]
    mart_orders = tp.agg(F.coalesce(F.sum("total_orders"), F.lit(0))).first()[0]
    r.checks["mart_time_patterns reconciles to dim_orders"] = abs(mart_orders - silver["dim_orders"].count())
    r.checks["mart_customer_segments.user_id unique"] = duplicates(gold["mart_customer_segments"], ["user_id"])
    r.checks["mart_customer_segments segment not null"] = nulls(gold["mart_customer_segments"], "behavioral_segment")
    r.checks["mart_basket_affinity pair unique"] = duplicates(
        gold["mart_basket_affinity"], ["product_a_id", "product_b_id"]
    )
    for col in ("support", "confidence_a_to_b"):
        r.checks[f"mart_basket_affinity.{col} in [0,1]"] = out_of_range(gold["mart_basket_affinity"], col, 0, 1)
    r.checks["mart_cohort_retention.retention_rate in [0,1]"] = out_of_range(
        gold["mart_cohort_retention"], "retention_rate", 0, 1
    )
    return r
