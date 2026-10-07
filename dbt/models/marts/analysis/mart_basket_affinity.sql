-- Eligibility thresholds are dbt vars so tests can shrink them to fit a tiny sample.
-- The defaults are the production values documented in docs/decisions.md section 3;
-- with no --vars the compiled SQL is identical to the previous hard-coded version.
{% set min_product_orders = var('min_product_orders', 1000) %}
{% set min_pair_orders = var('min_pair_orders', 100) %}

with product_order_counts as (
    select
        product_id,
        count(distinct order_id) as orders_with_product
    from {{ ref('fact_order_items') }}
    group by product_id
),

eligible_products as (
    select
        product_id,
        orders_with_product
    from product_order_counts
    where orders_with_product >= {{ min_product_orders }}
),

eligible_order_items as (
    select
        order_items.order_id,
        order_items.product_id,
        eligible_products.orders_with_product
    from {{ ref('fact_order_items') }} as order_items
    inner join eligible_products
        on order_items.product_id = eligible_products.product_id
),

product_pairs as (
    select
        product_a.product_id as product_a_id,
        product_b.product_id as product_b_id,
        count(distinct product_a.order_id) as orders_with_both
    from eligible_order_items as product_a
    inner join eligible_order_items as product_b
        on product_a.order_id = product_b.order_id
        and product_a.product_id < product_b.product_id
    group by
        product_a.product_id,
        product_b.product_id
    having count(distinct product_a.order_id) >= {{ min_pair_orders }}
),

total_orders as (
    select count(*) as total_orders
    from {{ ref('dim_orders') }}
)

select
    product_pairs.product_a_id,
    product_a.product_name as product_a_name,
    product_pairs.product_b_id,
    product_b.product_name as product_b_name,
    product_a_counts.orders_with_product as orders_with_a,
    product_b_counts.orders_with_product as orders_with_b,
    product_pairs.orders_with_both,
    round(
        cast(product_pairs.orders_with_both as {{ dbt.type_numeric() }})
        / nullif(total_orders.total_orders, 0),
        6
    ) as support,
    round(
        cast(product_pairs.orders_with_both as {{ dbt.type_numeric() }})
        / nullif(product_a_counts.orders_with_product, 0),
        6
    ) as confidence_a_to_b,
    round(
        (
            cast(product_pairs.orders_with_both as {{ dbt.type_numeric() }})
            / nullif(product_a_counts.orders_with_product, 0)
        )
        / nullif(
            cast(product_b_counts.orders_with_product as {{ dbt.type_numeric() }})
            / nullif(total_orders.total_orders, 0),
            0
        ),
        6
    ) as lift
from product_pairs
inner join {{ ref('dim_products') }} as product_a
    on product_pairs.product_a_id = product_a.product_id
inner join {{ ref('dim_products') }} as product_b
    on product_pairs.product_b_id = product_b.product_id
inner join product_order_counts as product_a_counts
    on product_pairs.product_a_id = product_a_counts.product_id
inner join product_order_counts as product_b_counts
    on product_pairs.product_b_id = product_b_counts.product_id
cross join total_orders
