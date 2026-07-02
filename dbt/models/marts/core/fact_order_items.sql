select
    order_id,
    product_id,
    user_id,
    add_to_cart_order,
    reordered,
    order_number,
    order_dow,
    order_day_of_week,
    order_hour_of_day,
    days_since_prior_order,
    aisle_id,
    department_id
from {{ ref('int_order_item_enriched') }}
