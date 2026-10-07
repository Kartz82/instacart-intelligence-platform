"""Gold layer: five dbt marts as pure DataFrame functions.

The five were chosen because each exercises a different Spark problem:

    mart_executive_kpis     many small aggregates joined into one row
    mart_customer_segments  global window functions (ntile) over every customer
    mart_cohort_retention   cohort arithmetic over the order sequence
    mart_time_patterns      two grains (order, line item) reconciled onto a generated grid
    mart_basket_affinity    the quadratic self-join, rewritten as array pair generation

Each docstring names the dbt model it ports. Output columns, names and rounding match.
"""

from __future__ import annotations

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

from .silver import NUMERIC


def mart_executive_kpis(
    fact: DataFrame, orders: DataFrame, customers: DataFrame, products: DataFrame
) -> DataFrame:
    """dbt: mart_executive_kpis. One row."""
    item_metrics = fact.agg(
        F.count(F.lit(1)).alias("total_order_items"),
        F.round(F.avg("reordered").cast(NUMERIC), 4).alias("reorder_rate"),
    )
    order_metrics = orders.agg(
        F.count(F.lit(1)).alias("total_orders"),
        F.round(F.avg("basket_size").cast(NUMERIC), 2).alias("average_basket_size"),
    )
    customer_metrics = customers.agg(
        F.count(F.lit(1)).alias("total_customers"),
        F.round(F.avg("total_orders").cast(NUMERIC), 2).alias("average_orders_per_customer"),
    )
    product_metrics = products.agg(F.count(F.lit(1)).alias("total_products"))

    # Join to dim_products as the SQL does. The product's department is aliased so it
    # cannot collide with fact_order_items.department_id.
    fact_products = fact.select("product_id").join(
        F.broadcast(
            products.select(
                "product_id",
                F.col("department_id").alias("product_department_id"),
                "department_name",
            )
        ),
        on="product_id",
        how="inner",
    )
    department_metrics = fact_products.agg(
        F.countDistinct("product_department_id").alias("active_departments")
    )
    top_department = (
        fact_products.groupBy("department_name")
        .agg(F.count(F.lit(1)).alias("total_order_items"))
        .orderBy(F.col("total_order_items").desc(), F.col("department_name").asc())
        .limit(1)
        .select(F.col("department_name").alias("top_department_by_items"))
    )

    return (
        order_metrics.crossJoin(customer_metrics)
        .crossJoin(product_metrics)
        .crossJoin(item_metrics)
        .crossJoin(department_metrics)
        .crossJoin(top_department)
        .select(
            F.lit(1).alias("kpi_snapshot_id"),
            "total_orders",
            "total_customers",
            "total_products",
            "total_order_items",
            "reorder_rate",
            "average_basket_size",
            "average_orders_per_customer",
            "active_departments",
            "top_department_by_items",
        )
    )


def mart_customer_segments(customers: DataFrame) -> DataFrame:
    """dbt: mart_customer_segments.

    ntile() over the whole customer set means a single-partition window. That is the same
    logical plan as the SQL and is fine at 206K customers; it would not scale to
    hundreds of millions of rows, where approximate quantiles would be the right tool."""

    def ordered(col):
        return Window.orderBy(col.asc(), F.col("user_id").asc())

    scored = customers.select(
        "user_id",
        "total_orders",
        "total_items_purchased",
        "avg_basket_size",
        "customer_reorder_rate",
        "latest_days_since_prior_order",
        F.ntile(5).over(ordered(F.col("total_orders"))).alias("frequency_score"),
        F.ntile(5).over(ordered(F.col("avg_basket_size"))).alias("basket_size_score"),
        F.ntile(5).over(ordered(F.col("customer_reorder_rate"))).alias("reorder_score"),
        (
            F.lit(6)
            - F.ntile(5).over(
                ordered(F.coalesce(F.col("latest_days_since_prior_order"), F.lit(999999.0)))
            )
        ).alias("recency_proxy_score"),
    )
    segmented = scored.withColumn(
        "behavioral_score",
        F.col("frequency_score")
        + F.col("basket_size_score")
        + F.col("reorder_score")
        + F.col("recency_proxy_score"),
    )
    # No "Early Lifecycle" branch: see docs/decisions.md section 8.
    return segmented.select(
        "user_id",
        "total_orders",
        "total_items_purchased",
        "avg_basket_size",
        "customer_reorder_rate",
        "latest_days_since_prior_order",
        "frequency_score",
        "basket_size_score",
        "reorder_score",
        "recency_proxy_score",
        "behavioral_score",
        F.when(F.col("behavioral_score") >= 17, "High Engagement")
        .when(F.col("behavioral_score") >= 13, "Loyal Routine")
        .when((F.col("frequency_score") <= 2) & (F.col("recency_proxy_score") <= 2), "At Risk")
        .otherwise("Moderate Engagement")
        .alias("behavioral_segment"),
    )


def mart_cohort_retention(orders: DataFrame, max_index: int = 20) -> DataFrame:
    """dbt: mart_cohort_retention. Retention by order sequence, not calendar."""
    cohorts = orders.groupBy("user_id").agg(
        F.min("order_number").alias("first_order_number"),
        F.count(F.lit(1)).alias("total_observed_orders"),
    )
    activity = orders.join(cohorts, on="user_id", how="inner").select(
        "user_id",
        (F.col("order_number") - F.col("first_order_number")).alias("order_sequence_index"),
    )
    starting = cohorts.agg(F.countDistinct("user_id").alias("starting_customers"))
    retention = (
        activity.where(F.col("order_sequence_index").between(0, max_index))
        .groupBy("order_sequence_index")
        .agg(F.countDistinct("user_id").alias("active_customers"))
    )
    return retention.crossJoin(starting).select(
        "order_sequence_index",
        (F.col("order_sequence_index") + 1).alias("observed_order_number"),
        "starting_customers",
        "active_customers",
        F.round(
            F.col("active_customers").cast(NUMERIC)
            / F.when(F.col("starting_customers") == 0, None).otherwise(F.col("starting_customers")),
            4,
        ).alias("retention_rate"),
    )


def mart_time_patterns(time_dim: DataFrame, orders: DataFrame, fact: DataFrame) -> DataFrame:
    """dbt: mart_time_patterns. Always 168 rows: order volume and reorder rate by
    day-of-week x hour. Orders and line items are aggregated separately and then joined
    onto the grid, so order counts are never multiplied by basket size."""
    order_volume = orders.groupBy("order_dow", "order_hour_of_day").agg(
        F.count(F.lit(1)).alias("total_orders"),
        F.countDistinct("user_id").alias("distinct_customers"),
        F.round(F.avg("basket_size").cast(NUMERIC), 2).alias("average_basket_size"),
    )
    item_volume = fact.groupBy("order_dow", "order_hour_of_day").agg(
        F.count(F.lit(1)).alias("total_order_items"),
        F.sum("reordered").alias("reordered_items"),
    )
    platform_total = orders.agg(F.count(F.lit(1)).alias("platform_total_orders"))

    keys = ["order_dow", "order_hour_of_day"]
    joined = (
        time_dim.join(order_volume, on=keys, how="left")
        .join(item_volume, on=keys, how="left")
        .crossJoin(platform_total)
    )
    items = F.coalesce("total_order_items", F.lit(0))
    total_orders = F.coalesce("total_orders", F.lit(0))
    return joined.select(
        "time_key",
        "order_dow",
        "order_day_of_week",
        "order_hour_of_day",
        "daypart",
        "is_weekend",
        total_orders.alias("total_orders"),
        F.coalesce("distinct_customers", F.lit(0)).alias("distinct_customers"),
        "average_basket_size",
        items.alias("total_order_items"),
        F.coalesce("reordered_items", F.lit(0)).alias("reordered_items"),
        F.when(items == 0, F.lit(0).cast(NUMERIC))
        .otherwise(F.round(F.col("reordered_items").cast(NUMERIC) / F.col("total_order_items"), 4))
        .alias("reorder_rate"),
        F.round(
            total_orders.cast(NUMERIC)
            / F.when(F.col("platform_total_orders") == 0, None).otherwise(F.col("platform_total_orders")),
            6,
        ).alias("share_of_total_orders"),
    )


def mart_basket_affinity(
    fact: DataFrame,
    orders: DataFrame,
    products: DataFrame,
    *,
    min_product_orders: int = 1000,
    min_pair_orders: int = 100,
) -> DataFrame:
    """dbt: mart_basket_affinity. Support, confidence and lift for product pairs.

    The SQL self-joins the line-item table on order_id, which shuffles every line item
    against every other line item of its order. Here each order's eligible products are
    collapsed into one sorted array, and the pairs are generated locally from that array
    (``a < b`` by construction, as in the SQL's ``product_a.product_id < product_b.product_id``).
    That is one shuffle on order_id instead of a join, with identical results.

    ``collect_set`` guarantees one entry per (order, product), so ``count(*)`` over pairs
    equals the SQL's ``count(distinct order_id)``."""
    product_counts = fact.groupBy("product_id").agg(
        F.countDistinct("order_id").alias("orders_with_product")
    )
    eligible = product_counts.where(F.col("orders_with_product") >= min_product_orders).select(
        "product_id"
    )

    baskets = (
        fact.select("order_id", "product_id")
        .join(F.broadcast(eligible), on="product_id", how="left_semi")
        .groupBy("order_id")
        .agg(F.array_sort(F.collect_set("product_id")).alias("items"))
        .where(F.size("items") >= 2)
    )

    # For each 1-based position i, pair items[i] with every later item.
    pair_expr = (
        "flatten(transform(sequence(1, size(items) - 1), "
        "i -> transform(slice(items, i + 1, size(items) - i), "
        "j -> named_struct('product_a_id', element_at(items, i), 'product_b_id', j))))"
    )
    pairs = (
        baskets.select(F.explode(F.expr(pair_expr)).alias("pair"))
        .select("pair.product_a_id", "pair.product_b_id")
        .groupBy("product_a_id", "product_b_id")
        .agg(F.count(F.lit(1)).alias("orders_with_both"))
        .where(F.col("orders_with_both") >= min_pair_orders)
    )

    total_orders = orders.agg(F.count(F.lit(1)).alias("total_orders"))
    name_a = products.select(
        F.col("product_id").alias("product_a_id"), F.col("product_name").alias("product_a_name")
    )
    name_b = products.select(
        F.col("product_id").alias("product_b_id"), F.col("product_name").alias("product_b_name")
    )
    counts_a = product_counts.select(
        F.col("product_id").alias("product_a_id"), F.col("orders_with_product").alias("orders_with_a")
    )
    counts_b = product_counts.select(
        F.col("product_id").alias("product_b_id"), F.col("orders_with_product").alias("orders_with_b")
    )

    joined = (
        pairs.join(F.broadcast(name_a), on="product_a_id", how="inner")
        .join(F.broadcast(name_b), on="product_b_id", how="inner")
        .join(counts_a, on="product_a_id", how="inner")
        .join(counts_b, on="product_b_id", how="inner")
        .crossJoin(total_orders)
    )

    both = F.col("orders_with_both")
    # Exact integer arithmetic for lift. (both/a)/(b/total) == both*total/(a*b); computing
    # it as one decimal division avoids losing digits through two nested divisions.
    wide = "decimal(38,0)"
    lift = F.round(
        (both.cast(wide) * F.col("total_orders").cast(wide))
        / (F.col("orders_with_a").cast(wide) * F.col("orders_with_b").cast(wide)),
        6,
    )
    return joined.select(
        "product_a_id",
        "product_a_name",
        "product_b_id",
        "product_b_name",
        "orders_with_a",
        "orders_with_b",
        "orders_with_both",
        F.round(both.cast(NUMERIC) / F.col("total_orders"), 6).alias("support"),
        F.round(both.cast(NUMERIC) / F.col("orders_with_a"), 6).alias("confidence_a_to_b"),
        lift.alias("lift"),
    )


GOLD_KEYS: dict[str, list[str]] = {
    "mart_executive_kpis": ["kpi_snapshot_id"],
    "mart_customer_segments": ["user_id"],
    "mart_cohort_retention": ["order_sequence_index"],
    "mart_time_patterns": ["order_dow", "order_hour_of_day"],
    "mart_basket_affinity": ["product_a_id", "product_b_id"],
}


def build_gold(
    silver: dict[str, DataFrame], *, min_product_orders: int = 1000, min_pair_orders: int = 100
) -> dict[str, DataFrame]:
    fact = silver["fact_order_items"]
    orders = silver["dim_orders"]
    customers = silver["dim_customers"]
    products = silver["dim_products"]
    return {
        "mart_executive_kpis": mart_executive_kpis(fact, orders, customers, products),
        "mart_customer_segments": mart_customer_segments(customers),
        "mart_cohort_retention": mart_cohort_retention(orders),
        "mart_time_patterns": mart_time_patterns(silver["dim_time"], orders, fact),
        "mart_basket_affinity": mart_basket_affinity(
            fact,
            orders,
            products,
            min_product_orders=min_product_orders,
            min_pair_orders=min_pair_orders,
        ),
    }
