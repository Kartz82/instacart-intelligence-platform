select
    user_id,
    total_orders,
    first_order_number,
    latest_order_number,
    first_order_id,
    latest_order_id,
    total_items_purchased,
    avg_basket_size,
    total_reordered_items,
    case
        when total_items_purchased = 0 then cast(0 as {{ dbt.type_numeric() }})
        else round(
            cast(total_reordered_items as {{ dbt.type_numeric() }})
            / total_items_purchased,
            4
        )
    end as customer_reorder_rate,
    avg_days_since_prior_order,
    latest_days_since_prior_order,
    earliest_order_hour,
    latest_order_hour
from {{ ref('int_customer_order_history') }}
