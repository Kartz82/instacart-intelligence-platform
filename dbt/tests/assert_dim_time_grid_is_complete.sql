-- dim_time must always be the full 7 day-of-week x 24 hour-of-day grid: exactly 168
-- rows, no gaps. Returns a row (and therefore fails) if the grid is incomplete.

select
    count(*) as row_count,
    count(distinct order_dow) as distinct_days,
    count(distinct order_hour_of_day) as distinct_hours
from {{ ref('dim_time') }}
having
    count(*) != 168
    or count(distinct order_dow) != 7
    or count(distinct order_hour_of_day) != 24
