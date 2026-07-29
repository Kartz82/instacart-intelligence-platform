-- The time-pattern mart is a complete repartition of every order, so its total_orders
-- must sum back to the order count in dim_orders. Catches the classic grain bug where
-- joining the order grain to the line-item grain multiplies orders by basket size.

with mart_total as (
    select sum(total_orders) as mart_orders
    from {{ ref('mart_time_patterns') }}
),

source_total as (
    select count(*) as source_orders
    from {{ ref('dim_orders') }}
)

select
    mart_total.mart_orders,
    source_total.source_orders
from mart_total
cross join source_total
where mart_total.mart_orders != source_total.source_orders
