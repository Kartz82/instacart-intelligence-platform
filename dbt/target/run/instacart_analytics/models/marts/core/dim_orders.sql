
  
    

  create  table "instacart_db"."analytics_core"."dim_orders__dbt_tmp"
  
  
    as
  
  (
    with order_items as (
    select
        order_id,
        count(*) as basket_size,
        sum(reordered) as reordered_items
    from "instacart_db"."analytics_staging"."stg_order_products"
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
        when coalesce(order_items.basket_size, 0) = 0 then 0::numeric(10, 4)
        else (
            coalesce(order_items.reordered_items, 0)::numeric
            / order_items.basket_size
        )::numeric(10, 4)
    end as order_reorder_rate
from "instacart_db"."analytics_staging"."stg_orders" as orders
left join order_items
    on orders.order_id = order_items.order_id
  );
  