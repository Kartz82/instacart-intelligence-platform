select
    products.product_id,
    products.product_name,
    products.aisle_name,
    products.department_name,
    count(order_items.product_id) as total_order_items,
    count(distinct order_items.order_id) as distinct_orders,
    count(distinct order_items.user_id) as distinct_customers,
    avg(order_items.reordered)::numeric(10, 4) as reorder_rate
from "instacart_db"."analytics_core"."dim_products" as products
left join "instacart_db"."analytics_core"."fact_order_items" as order_items
    on products.product_id = order_items.product_id
group by
    products.product_id,
    products.product_name,
    products.aisle_name,
    products.department_name