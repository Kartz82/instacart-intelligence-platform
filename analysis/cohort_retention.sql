/*
Business question:
How many customers continue to later observed order milestones?

Notes:
- This is order-sequence retention, not calendar retention.
- The dataset does not contain real order dates.
*/

select
    order_sequence_index,
    observed_order_number,
    starting_customers,
    active_customers,
    retention_rate
from analytics_analysis.mart_cohort_retention
order by order_sequence_index;

/*
Retention checkpoints for concise stakeholder reporting.
*/

select
    observed_order_number,
    active_customers,
    retention_rate
from analytics_analysis.mart_cohort_retention
where observed_order_number in (1, 2, 3, 5, 10, 15, 20)
order by observed_order_number;
