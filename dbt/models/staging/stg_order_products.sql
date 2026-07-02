select
    order_id::integer as order_id,
    product_id::integer as product_id,
    add_to_cart_order::integer as add_to_cart_order,
    reordered::integer as reordered
from {{ source('raw', 'order_products') }}
