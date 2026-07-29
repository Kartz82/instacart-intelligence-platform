-- Order volume and reorder intensity across day-of-week x hour-of-day.
--
-- Source for the Temporal Behavior heatmap in the BI layer. Built off dim_time so
-- the grid is always complete (168 rows) even where a slot has no orders.
--
-- Order counts come from dim_orders (one row per order); item counts and reorder
-- rate come from fact_order_items (one row per product per order). Mixing the two
-- grains in a single join would multiply order counts by basket size, so they are
-- aggregated separately and then joined onto the time grid.

with order_volume as (
    select
        order_dow,
        order_hour_of_day,
        count(*) as total_orders,
        count(distinct user_id) as distinct_customers,
        round(cast(avg(basket_size) as {{ dbt.type_numeric() }}), 2) as average_basket_size
    from {{ ref('dim_orders') }}
    group by order_dow, order_hour_of_day
),

item_volume as (
    select
        order_dow,
        order_hour_of_day,
        count(*) as total_order_items,
        sum(reordered) as reordered_items
    from {{ ref('fact_order_items') }}
    group by order_dow, order_hour_of_day
),

total_volume as (
    select count(*) as platform_total_orders
    from {{ ref('dim_orders') }}
)

select
    dim_time.time_key,
    dim_time.order_dow,
    dim_time.order_day_of_week,
    dim_time.order_hour_of_day,
    dim_time.daypart,
    dim_time.is_weekend,
    coalesce(order_volume.total_orders, 0) as total_orders,
    coalesce(order_volume.distinct_customers, 0) as distinct_customers,
    order_volume.average_basket_size,
    coalesce(item_volume.total_order_items, 0) as total_order_items,
    coalesce(item_volume.reordered_items, 0) as reordered_items,
    case
        when coalesce(item_volume.total_order_items, 0) = 0
            then cast(0 as {{ dbt.type_numeric() }})
        else round(
            cast(item_volume.reordered_items as {{ dbt.type_numeric() }})
            / item_volume.total_order_items,
            4
        )
    end as reorder_rate,
    round(
        cast(coalesce(order_volume.total_orders, 0) as {{ dbt.type_numeric() }})
        / nullif(total_volume.platform_total_orders, 0),
        6
    ) as share_of_total_orders
from {{ ref('dim_time') }} as dim_time
left join order_volume
    on dim_time.order_dow = order_volume.order_dow
    and dim_time.order_hour_of_day = order_volume.order_hour_of_day
left join item_volume
    on dim_time.order_dow = item_volume.order_dow
    and dim_time.order_hour_of_day = item_volume.order_hour_of_day
cross join total_volume
