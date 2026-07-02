with order_items as (
    select
        order_id,
        count(*) as basket_size,
        sum(reordered) as reordered_items
    from "instacart_db"."analytics_staging"."stg_order_products"
    group by order_id
),

orders_enriched as (
    select
        orders.order_id,
        orders.user_id,
        orders.eval_set,
        orders.order_number,
        orders.order_dow,
        orders.order_day_of_week,
        orders.order_hour_of_day,
        orders.days_since_prior_order,
        coalesce(order_items.basket_size, 0) as basket_size,
        coalesce(order_items.reordered_items, 0) as reordered_items
    from "instacart_db"."analytics_staging"."stg_orders" as orders
    left join order_items
        on orders.order_id = order_items.order_id
),

orders_ranked as (
    select
        *,
        row_number() over (
            partition by user_id
            order by order_number asc, order_id asc
        ) as first_order_rank,
        row_number() over (
            partition by user_id
            order by order_number desc, order_id desc
        ) as latest_order_rank
    from orders_enriched
)

select
    user_id,
    count(*) as total_orders,
    min(order_number) as first_order_number,
    max(order_number) as latest_order_number,
    max(order_id) filter (where first_order_rank = 1) as first_order_id,
    max(order_id) filter (where latest_order_rank = 1) as latest_order_id,
    sum(basket_size) as total_items_purchased,
    avg(basket_size)::numeric(10, 2) as avg_basket_size,
    sum(reordered_items) as total_reordered_items,
    avg(days_since_prior_order)::numeric(10, 2) as avg_days_since_prior_order,
    max(days_since_prior_order) filter (where latest_order_rank = 1) as latest_days_since_prior_order,
    min(order_hour_of_day) as earliest_order_hour,
    max(order_hour_of_day) as latest_order_hour
from orders_ranked
group by user_id