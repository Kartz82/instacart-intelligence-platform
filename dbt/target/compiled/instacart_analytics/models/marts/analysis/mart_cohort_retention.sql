with customer_cohorts as (
    select
        user_id,
        min(order_number) as first_order_number,
        count(*) as total_observed_orders
    from "instacart_db"."analytics_core"."dim_orders"
    group by user_id
),

cohort_activity as (
    select
        orders.user_id,
        orders.order_id,
        orders.order_number,
        orders.order_number - customer_cohorts.first_order_number as order_sequence_index
    from "instacart_db"."analytics_core"."dim_orders" as orders
    inner join customer_cohorts
        on orders.user_id = customer_cohorts.user_id
),

cohort_size as (
    select
        count(distinct user_id) as starting_customers
    from customer_cohorts
),

retention as (
    select
        order_sequence_index,
        count(distinct user_id) as active_customers
    from cohort_activity
    where order_sequence_index between 0 and 20
    group by order_sequence_index
)

select
    retention.order_sequence_index,
    retention.order_sequence_index + 1 as observed_order_number,
    cohort_size.starting_customers,
    retention.active_customers,
    (
        retention.active_customers::numeric
        / nullif(cohort_size.starting_customers, 0)
    )::numeric(10, 4) as retention_rate
from retention
cross join cohort_size