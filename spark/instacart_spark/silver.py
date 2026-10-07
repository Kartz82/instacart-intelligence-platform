"""Silver layer: the dbt staging, intermediate and core models as pure DataFrame functions.

Each function names the dbt model it ports. They take and return DataFrames and touch no
storage, so the same code runs against a laptop sample, a Delta table, or a test fixture.

Numeric convention: dbt's ``{{ dbt.type_numeric() }}`` is ``numeric(28,6)``; the same
type is used here (``NUMERIC``) so rounding happens at the same point as in the SQL.
"""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession, Window
from pyspark.sql import functions as F

NUMERIC = "decimal(28,6)"

# dbt_utils.generate_surrogate_key uses this literal for nulls.
_SURROGATE_NULL = "_dbt_utils_surrogate_key_null_"

DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def _day_name(col: str = "order_dow"):
    expr = F.lit(None).cast("string")
    for dow in reversed(range(7)):
        expr = F.when(F.col(col) == dow, F.lit(DAY_NAMES[dow])).otherwise(expr)
    return expr


def _surrogate_key(*cols: str):
    """Port of dbt_utils.generate_surrogate_key: md5 of '-'-joined, null-coalesced strings."""
    parts = [F.coalesce(F.col(c).cast("string"), F.lit(_SURROGATE_NULL)) for c in cols]
    return F.md5(F.concat_ws("-", *parts))


# --------------------------------------------------------------------------- staging


def stg_orders(orders: DataFrame) -> DataFrame:
    """dbt: stg_orders."""
    return orders.select(
        F.col("order_id").cast("int"),
        F.col("user_id").cast("int"),
        F.col("eval_set").cast("string"),
        F.col("order_number").cast("int"),
        F.col("order_dow").cast("int"),
        _day_name().alias("order_day_of_week"),
        F.col("order_hour_of_day").cast("int"),
        F.col("days_since_prior_order").cast("double"),
    )


def stg_order_products(order_products: DataFrame) -> DataFrame:
    """dbt: stg_order_products."""
    return order_products.select(
        F.col("order_id").cast("int"),
        F.col("product_id").cast("int"),
        F.col("add_to_cart_order").cast("int"),
        F.col("reordered").cast("int"),
    )


def stg_products(products: DataFrame) -> DataFrame:
    """dbt: stg_products."""
    return products.select(
        F.col("product_id").cast("int"),
        F.col("product_name").cast("string"),
        F.col("aisle_id").cast("int"),
        F.col("department_id").cast("int"),
    )


def stg_aisles(aisles: DataFrame) -> DataFrame:
    """dbt: stg_aisles."""
    return aisles.select(
        F.col("aisle_id").cast("int"), F.col("aisle").cast("string").alias("aisle_name")
    )


def stg_departments(departments: DataFrame) -> DataFrame:
    """dbt: stg_departments."""
    return departments.select(
        F.col("department_id").cast("int"),
        F.col("department").cast("string").alias("department_name"),
    )


# ------------------------------------------------------------------ intermediate / core


def _order_basket(stg_op: DataFrame) -> DataFrame:
    return stg_op.groupBy("order_id").agg(
        F.count(F.lit(1)).alias("basket_size"),
        F.sum("reordered").alias("reordered_items"),
    )


def _enriched_orders(stg_o: DataFrame, stg_op: DataFrame) -> DataFrame:
    basket = _order_basket(stg_op)
    return stg_o.join(basket, on="order_id", how="left").select(
        "order_id",
        "user_id",
        "eval_set",
        "order_number",
        "order_dow",
        "order_day_of_week",
        "order_hour_of_day",
        "days_since_prior_order",
        F.coalesce("basket_size", F.lit(0)).alias("basket_size"),
        F.coalesce("reordered_items", F.lit(0)).alias("reordered_items"),
    )


def customer_history_from_orders(orders_enriched: DataFrame) -> DataFrame:
    """The aggregation half of int_customer_order_history. Takes one row per order with
    basket_size and reordered_items already attached, which is exactly what dim_orders
    holds. The incremental path uses this to recompute only the customers that changed."""
    first_w = Window.partitionBy("user_id").orderBy(F.col("order_number").asc(), F.col("order_id").asc())
    last_w = Window.partitionBy("user_id").orderBy(F.col("order_number").desc(), F.col("order_id").desc())
    ranked = orders_enriched.withColumn("first_order_rank", F.row_number().over(first_w)).withColumn(
        "latest_order_rank", F.row_number().over(last_w)
    )

    return ranked.groupBy("user_id").agg(
        F.count(F.lit(1)).alias("total_orders"),
        F.min("order_number").alias("first_order_number"),
        F.max("order_number").alias("latest_order_number"),
        F.max(F.when(F.col("first_order_rank") == 1, F.col("order_id"))).alias("first_order_id"),
        F.max(F.when(F.col("latest_order_rank") == 1, F.col("order_id"))).alias("latest_order_id"),
        F.sum("basket_size").alias("total_items_purchased"),
        F.round(F.avg("basket_size").cast(NUMERIC), 2).alias("avg_basket_size"),
        F.sum("reordered_items").alias("total_reordered_items"),
        F.round(F.avg("days_since_prior_order").cast(NUMERIC), 2).alias("avg_days_since_prior_order"),
        F.max(
            F.when(F.col("latest_order_rank") == 1, F.col("days_since_prior_order"))
        ).alias("latest_days_since_prior_order"),
        F.min("order_hour_of_day").alias("earliest_order_hour"),
        F.max("order_hour_of_day").alias("latest_order_hour"),
    )


def int_customer_order_history(stg_o: DataFrame, stg_op: DataFrame) -> DataFrame:
    """dbt: int_customer_order_history."""
    return customer_history_from_orders(_enriched_orders(stg_o, stg_op))


def dim_customers(history: DataFrame) -> DataFrame:
    """dbt: dim_customers."""
    return history.select(
        "user_id",
        "total_orders",
        "first_order_number",
        "latest_order_number",
        "first_order_id",
        "latest_order_id",
        "total_items_purchased",
        "avg_basket_size",
        "total_reordered_items",
        F.when(F.col("total_items_purchased") == 0, F.lit(0).cast(NUMERIC))
        .otherwise(
            F.round(
                F.col("total_reordered_items").cast(NUMERIC) / F.col("total_items_purchased"), 4
            )
        )
        .alias("customer_reorder_rate"),
        "avg_days_since_prior_order",
        "latest_days_since_prior_order",
        "earliest_order_hour",
        "latest_order_hour",
    )


def dim_orders(stg_o: DataFrame, stg_op: DataFrame) -> DataFrame:
    """dbt: dim_orders."""
    enriched = _enriched_orders(stg_o, stg_op)
    return enriched.withColumn(
        "order_reorder_rate",
        F.when(F.col("basket_size") == 0, F.lit(0).cast(NUMERIC)).otherwise(
            F.round(F.col("reordered_items").cast(NUMERIC) / F.col("basket_size"), 4)
        ),
    )


def dim_products(stg_p: DataFrame, stg_a: DataFrame, stg_d: DataFrame) -> DataFrame:
    """dbt: dim_products (inner joins, as in the SQL)."""
    return (
        stg_p.join(F.broadcast(stg_a), on="aisle_id", how="inner")
        .join(F.broadcast(stg_d), on="department_id", how="inner")
        .select(
            "product_id", "product_name", "aisle_id", "aisle_name", "department_id", "department_name"
        )
    )


def dim_time(spark: SparkSession) -> DataFrame:
    """dbt: dim_time. The generated 7 x 24 = 168-slot grid (no timestamps in the source)."""
    days = spark.range(0, 7).select(F.col("id").cast("int").alias("order_dow"))
    hours = spark.range(0, 24).select(F.col("id").cast("int").alias("order_hour_of_day"))
    grid = days.crossJoin(hours)
    return grid.select(
        _surrogate_key("order_dow", "order_hour_of_day").alias("time_key"),
        "order_dow",
        "order_hour_of_day",
        _day_name().alias("order_day_of_week"),
        F.col("order_dow").isin(0, 6).alias("is_weekend"),
        F.when(F.col("order_hour_of_day").between(0, 5), "Overnight")
        .when(F.col("order_hour_of_day").between(6, 10), "Morning")
        .when(F.col("order_hour_of_day").between(11, 14), "Midday")
        .when(F.col("order_hour_of_day").between(15, 18), "Afternoon")
        .otherwise("Evening")
        .alias("daypart"),
    )


def fact_order_items(
    stg_o: DataFrame,
    stg_op: DataFrame,
    stg_p: DataFrame,
    stg_a: DataFrame,
    stg_d: DataFrame,
) -> DataFrame:
    """dbt: int_order_item_enriched narrowed to the columns of fact_order_items.

    Inner joins on every key, exactly as the SQL: a line whose order, product, aisle or
    department is missing is dropped here, and the dbt relationship tests are what flag
    it. Grain: one row per (order_id, product_id)."""
    products = stg_p.join(F.broadcast(stg_a), on="aisle_id", how="inner").join(
        F.broadcast(stg_d), on="department_id", how="inner"
    )
    return (
        stg_op.join(stg_o, on="order_id", how="inner")
        .join(F.broadcast(products.select("product_id", "aisle_id", "department_id")), on="product_id", how="inner")
        .select(
            "order_id",
            "product_id",
            "user_id",
            "add_to_cart_order",
            "reordered",
            "order_number",
            "order_dow",
            "order_day_of_week",
            "order_hour_of_day",
            "days_since_prior_order",
            "aisle_id",
            "department_id",
        )
    )


def build_silver(spark: SparkSession, bronze: dict[str, DataFrame]) -> dict[str, DataFrame]:
    """Stage typed tables from bronze and derive the conformed silver tables."""
    s_orders = stg_orders(bronze["orders"])
    s_items = stg_order_products(bronze["order_products"])
    s_products = stg_products(bronze["products"])
    s_aisles = stg_aisles(bronze["aisles"])
    s_depts = stg_departments(bronze["departments"])
    return derive_silver(spark, s_orders, s_items, s_products, s_aisles, s_depts)


def derive_silver(
    spark: SparkSession,
    s_orders: DataFrame,
    s_items: DataFrame,
    s_products: DataFrame,
    s_aisles: DataFrame,
    s_depts: DataFrame,
) -> dict[str, DataFrame]:
    """Derive dimensions and the fact from already-staged tables."""
    history = int_customer_order_history(s_orders, s_items)
    return {
        "stg_orders": s_orders,
        "stg_order_products": s_items,
        "stg_products": s_products,
        "stg_aisles": s_aisles,
        "stg_departments": s_depts,
        "dim_orders": dim_orders(s_orders, s_items),
        "dim_customers": dim_customers(history),
        "dim_products": dim_products(s_products, s_aisles, s_depts),
        "dim_time": dim_time(spark),
        "fact_order_items": fact_order_items(s_orders, s_items, s_products, s_aisles, s_depts),
    }
