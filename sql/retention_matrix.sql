WITH user_cohorts AS (
    SELECT 
        user_id,
        MIN(order_number) AS first_order_milestone,
        COUNT(order_id) AS lifetime_orders
    FROM orders
    GROUP BY user_id
),
cohort_order_mapping AS (
    SELECT 
        o.user_id,
        o.order_number - uc.first_order_milestone AS transaction_cohort_index,
        o.order_id
    FROM orders o
    JOIN user_cohorts uc ON o.user_id = uc.user_id
)
SELECT 
    transaction_cohort_index,
    COUNT(DISTINCT user_id) AS active_users,
    ROUND(COUNT(DISTINCT user_id) * 100.0 / (SELECT COUNT(DISTINCT user_id) FROM orders), 2) AS retention_efficiency_pct
FROM cohort_order_mapping
WHERE transaction_cohort_index <= 12
GROUP BY transaction_cohort_index
ORDER BY transaction_cohort_index;