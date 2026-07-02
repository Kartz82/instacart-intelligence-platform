select
    order_products.order_id,
    order_products.product_id,
    orders.user_id,
    orders.eval_set,
    orders.order_number,
    orders.order_dow,
    orders.order_day_of_week,
    orders.order_hour_of_day,
    orders.days_since_prior_order,
    order_products.add_to_cart_order,
    order_products.reordered,
    products.product_name,
    products.aisle_id,
    aisles.aisle_name,
    products.department_id,
    departments.department_name
from {{ ref('stg_order_products') }} as order_products
inner join {{ ref('stg_orders') }} as orders
    on order_products.order_id = orders.order_id
inner join {{ ref('stg_products') }} as products
    on order_products.product_id = products.product_id
inner join {{ ref('stg_aisles') }} as aisles
    on products.aisle_id = aisles.aisle_id
inner join {{ ref('stg_departments') }} as departments
    on products.department_id = departments.department_id
