select
    cast(order_id as {{ dbt.type_int() }}) as order_id,
    cast(user_id as {{ dbt.type_int() }}) as user_id,
    cast(eval_set as {{ dbt.type_string() }}) as eval_set,
    cast(order_number as {{ dbt.type_int() }}) as order_number,
    cast(order_dow as {{ dbt.type_int() }}) as order_dow,
    case order_dow
        when 0 then 'Sunday'
        when 1 then 'Monday'
        when 2 then 'Tuesday'
        when 3 then 'Wednesday'
        when 4 then 'Thursday'
        when 5 then 'Friday'
        when 6 then 'Saturday'
    end as order_day_of_week,
    cast(order_hour_of_day as {{ dbt.type_int() }}) as order_hour_of_day,
    cast(days_since_prior_order as {{ dbt.type_float() }}) as days_since_prior_order
from {{ source('raw', 'orders') }}
