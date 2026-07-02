# BI Data Dictionary

Power BI should connect to dbt marts, not raw tables. The marts below are the BI-facing tables for the portfolio dashboard.

## BI-Facing Marts

| Mart | Relation | Grain | Primary Use |
|---|---|---|---|
| Executive KPIs | `analytics_kpis.mart_executive_kpis` | One row | Executive summary cards |
| Product Performance | `analytics_kpis.mart_product_performance` | One row per `product_id` | Product, aisle, and department analysis |
| Customer Segments | `analytics_kpis.mart_customer_segments` | One row per `user_id` | Behavioral engagement segmentation |
| Cohort Retention | `analytics_analysis.mart_cohort_retention` | One row per order-sequence index | Retention across observed order milestones |
| Basket Affinity | `analytics_analysis.mart_basket_affinity` | One row per product pair | Product affinity and merchandising analysis |

## `analytics_kpis.mart_executive_kpis`

Grain: one row for the full dataset.

Key columns:

| Column | Definition | Business Usage |
|---|---|---|
| `kpi_snapshot_id` | Static single-row identifier | Technical key for Power BI |
| `total_orders` | Count of observed orders | Dataset scale |
| `total_customers` | Count of observed customers | Customer base size |
| `total_products` | Count of products in the product dimension | Catalog breadth |
| `total_order_items` | Count of order-product line items | Basket activity volume |
| `reorder_rate` | Average of the order-item `reordered` flag | Repeat-purchase behavior |
| `average_basket_size` | Average product line items per order | Basket depth |
| `average_orders_per_customer` | Average observed orders per customer | Customer order frequency |
| `active_departments` | Count of departments represented in purchased items | Department breadth |
| `top_department_by_items` | Department with the most order-item lines | Executive merchandising callout |

Limitations:
- No revenue, profit, margin, AOV, or CLV.
- Single-row snapshot; slicers are not expected to change this page.

## `analytics_kpis.mart_product_performance`

Grain: one row per `product_id`.

Key columns:

| Column | Definition | Business Usage |
|---|---|---|
| `product_id` | Product identifier | Product-level joins and detail |
| `product_name` | Product name | BI display label |
| `aisle_name` | Aisle label | Category filtering |
| `department_name` | Department label | Executive category grouping |
| `total_order_items` | Count of order lines containing the product | Product volume ranking |
| `distinct_orders` | Count of distinct orders containing the product | Order reach |
| `distinct_customers` | Count of distinct customers who purchased the product | Customer reach |
| `reorder_rate` | Product-level average reordered flag | Repeat-purchase behavior |

Business usage:
- Rank products by purchase volume.
- Compare product reach and reorder behavior.
- Filter product performance by aisle or department.

Limitations:
- No price, margin, or revenue contribution.
- Department-level distinct order reach should be calculated carefully; summing product-level distinct orders can double count orders containing multiple products in the same department.

## `analytics_kpis.mart_customer_segments`

Grain: one row per `user_id`.

Key columns:

| Column | Definition | Business Usage |
|---|---|---|
| `user_id` | Customer identifier | Customer-level detail |
| `total_orders` | Observed order count for the customer | Frequency behavior |
| `total_items_purchased` | Total order-product lines for the customer | Basket activity |
| `avg_basket_size` | Average line items per customer order | Basket depth |
| `customer_reorder_rate` | Customer-level share of reordered items | Repeat behavior |
| `latest_days_since_prior_order` | Latest observed reorder-gap proxy | Recency proxy |
| `frequency_score` | 1-5 score based on observed order count | Behavioral scoring |
| `basket_size_score` | 1-5 score based on average basket size | Behavioral scoring |
| `reorder_score` | 1-5 score based on customer reorder rate | Behavioral scoring |
| `recency_proxy_score` | 1-5 score based on latest reorder-gap proxy | Behavioral scoring |
| `behavioral_score` | Sum of behavior scores | Segment ranking |
| `behavioral_segment` | Segment label | Customer engagement grouping |

Segment labels:
- `High Engagement`
- `Loyal Routine`
- `At Risk`
- `Early Lifecycle`
- `Moderate Engagement`

Business usage:
- Show distribution of customer engagement groups.
- Compare order frequency, basket size, and reorder behavior by segment.
- Identify lifecycle groups for recommendation discussion.

Limitations:
- Behavioral/RFM-style only, not financial RFM.
- No CLV, revenue, or margin.
- Recency is a proxy from `days_since_prior_order`, not calendar recency.

## `analytics_analysis.mart_cohort_retention`

Grain: one row per observed order-sequence index.

Key columns:

| Column | Definition | Business Usage |
|---|---|---|
| `order_sequence_index` | Zero-based sequence from each customer's first observed order | Technical cohort index |
| `observed_order_number` | One-based order milestone | BI axis label |
| `starting_customers` | Count of customers in the observed dataset | Retention denominator |
| `active_customers` | Customers observed at that order milestone | Retention numerator |
| `retention_rate` | Active customers divided by starting customers | Order-sequence retention |

Business usage:
- Visualize customer continuation across observed order milestones.
- Identify drop-off points across the order sequence.
- Support lifecycle recommendations.

Limitations:
- Not calendar retention.
- The dataset does not include real order dates.
- Retention is across observed order number, not monthly/weekly cohorts.

## `analytics_analysis.mart_basket_affinity`

Grain: one row per product pair, where `product_a_id < product_b_id`.

Key columns:

| Column | Definition | Business Usage |
|---|---|---|
| `product_a_id` | First product identifier in stable pair direction | Product pair key |
| `product_a_name` | First product name | BI display label |
| `product_b_id` | Second product identifier in stable pair direction | Product pair key |
| `product_b_name` | Second product name | BI display label |
| `orders_with_a` | Orders containing product A | Affinity denominator |
| `orders_with_b` | Orders containing product B | Product B baseline |
| `orders_with_both` | Orders containing both products | Co-occurrence count |
| `support` | Orders with both products divided by total orders | Pair prevalence |
| `confidence_a_to_b` | Orders with both divided by orders with A | Directional affinity |
| `lift` | Confidence A to B divided by product B order share | Relative affinity strength |

Business usage:
- Identify product pairs for merchandising or cross-sell discussion.
- Compare high-lift pairs against high-support pairs.
- Populate basket affinity dashboard visuals.

Limitations:
- Product affinity only; not prediction or machine learning.
- The mart filters to common products and co-occurring pairs for local performance.
- High lift does not imply causation.

## Upstream Core Marts

These are used by dbt to build the BI-facing marts and may be useful for validation, but Power BI should prioritize the BI-facing marts above.

| Mart | Grain | Notes |
|---|---|---|
| `analytics_core.dim_customers` | One row per `user_id` | Customer lifecycle attributes |
| `analytics_core.dim_products` | One row per `product_id` | Product catalog with aisle and department |
| `analytics_core.dim_orders` | One row per `order_id` | Order timing and basket-size attributes |
| `analytics_core.fact_order_items` | One row per `order_id` + `product_id` | Order-item fact table |

## General Limitations

- No prices are available in the source dataset.
- Do not calculate revenue, profit, margin, AOV, or CLV.
- No real calendar dates are available.
- Cohorts are based on observed order sequence.
- Basket affinity is product co-occurrence, not predictive modeling.
- Final metric values should be filled only after PostgreSQL load, dbt run, and dbt tests pass.
