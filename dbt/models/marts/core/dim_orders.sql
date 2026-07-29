with order_items as (
    select
        order_id,
        count(*) as basket_size,
        sum(reordered) as reordered_items
    from {{ ref('stg_order_products') }}
    group by order_id
)

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
    coalesce(order_items.reordered_items, 0) as reordered_items,
    case
        when coalesce(order_items.basket_size, 0) = 0 then cast(0 as {{ dbt.type_numeric() }})
        else round(
            cast(coalesce(order_items.reordered_items, 0) as {{ dbt.type_numeric() }})
            / order_items.basket_size,
            4
        )
    end as order_reorder_rate
from {{ ref('stg_orders') }} as orders
left join order_items
    on orders.order_id = order_items.order_id
