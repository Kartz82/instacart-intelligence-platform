with scored as (
    select
        user_id,
        total_orders,
        total_items_purchased,
        avg_basket_size,
        customer_reorder_rate,
        latest_days_since_prior_order,
        ntile(5) over (
            order by total_orders asc, user_id asc
        ) as frequency_score,
        ntile(5) over (
            order by avg_basket_size asc, user_id asc
        ) as basket_size_score,
        ntile(5) over (
            order by customer_reorder_rate asc, user_id asc
        ) as reorder_score,
        6 - ntile(5) over (
            order by coalesce(latest_days_since_prior_order, 999999.0) asc, user_id asc
        ) as recency_proxy_score
    from {{ ref('dim_customers') }}
),

segmented as (
    select
        *,
        (
            frequency_score
            + basket_size_score
            + reorder_score
            + recency_proxy_score
        ) as behavioral_score
    from scored
)

select
    user_id,
    total_orders,
    total_items_purchased,
    avg_basket_size,
    customer_reorder_rate,
    latest_days_since_prior_order,
    frequency_score,
    basket_size_score,
    reorder_score,
    recency_proxy_score,
    behavioral_score,
    -- There is deliberately no "Early Lifecycle" segment. The Instacart extract is a
    -- curated sample: every user in it has between 4 and 100 observed orders, verified
    -- against the built warehouse. Customers new to the platform are therefore absent
    -- from the sample by construction, and a segment for them would be an artefact of
    -- the cut point rather than a real cohort. Lowering the threshold until the segment
    -- populated would manufacture a lifecycle stage the data does not contain.
    case
        when behavioral_score >= 17 then 'High Engagement'
        when behavioral_score >= 13 then 'Loyal Routine'
        when frequency_score <= 2 and recency_proxy_score <= 2 then 'At Risk'
        else 'Moderate Engagement'
    end as behavioral_segment
from segmented
