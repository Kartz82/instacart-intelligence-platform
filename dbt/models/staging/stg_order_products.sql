select
    cast(order_id as {{ dbt.type_int() }}) as order_id,
    cast(product_id as {{ dbt.type_int() }}) as product_id,
    cast(add_to_cart_order as {{ dbt.type_int() }}) as add_to_cart_order,
    cast(reordered as {{ dbt.type_int() }}) as reordered
from {{ source('raw', 'order_products') }}
