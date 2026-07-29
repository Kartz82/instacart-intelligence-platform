-- Conformed time dimension for the Instacart dataset.
--
-- The source data carries no absolute timestamps: only order_dow (0-6, Sunday-based)
-- and order_hour_of_day (0-23). The finest real time grain available is therefore
-- day-of-week x hour-of-day, which is exactly 7 * 24 = 168 rows. This dimension is
-- generated rather than derived from the fact table so that hours with zero orders
-- still appear in the heatmap.

with days as (
    select generated_number - 1 as order_dow
    from ({{ dbt_utils.generate_series(upper_bound=7) }}) as generated_days
),

hours as (
    select generated_number - 1 as order_hour_of_day
    from ({{ dbt_utils.generate_series(upper_bound=24) }}) as generated_hours
),

day_hour_grid as (
    select
        days.order_dow,
        hours.order_hour_of_day
    from days
    cross join hours
)

select
    {{ dbt_utils.generate_surrogate_key(['order_dow', 'order_hour_of_day']) }} as time_key,
    order_dow,
    order_hour_of_day,
    case order_dow
        when 0 then 'Sunday'
        when 1 then 'Monday'
        when 2 then 'Tuesday'
        when 3 then 'Wednesday'
        when 4 then 'Thursday'
        when 5 then 'Friday'
        when 6 then 'Saturday'
    end as order_day_of_week,
    case
        when order_dow in (0, 6) then true
        else false
    end as is_weekend,
    case
        when order_hour_of_day between 0 and 5 then 'Overnight'
        when order_hour_of_day between 6 and 10 then 'Morning'
        when order_hour_of_day between 11 and 14 then 'Midday'
        when order_hour_of_day between 15 and 18 then 'Afternoon'
        else 'Evening'
    end as daypart
from day_hour_grid
