select
    order_id::integer as order_id,
    user_id::integer as user_id,
    eval_set::varchar as eval_set,
    order_number::integer as order_number,
    order_dow::integer as order_dow,
    case order_dow
        when 0 then 'Sunday'
        when 1 then 'Monday'
        when 2 then 'Tuesday'
        when 3 then 'Wednesday'
        when 4 then 'Thursday'
        when 5 then 'Friday'
        when 6 then 'Saturday'
    end as order_day_of_week,
    order_hour_of_day::integer as order_hour_of_day,
    days_since_prior_order::double precision as days_since_prior_order
from "instacart_db"."raw"."orders"