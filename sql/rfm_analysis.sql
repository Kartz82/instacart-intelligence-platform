/*
RFM-style customer engagement segmentation for the Instacart dataset.

The public Instacart Market Basket Analysis dataset does not include prices or
true transaction dates, so this table uses defensible engagement proxies:

- Recency: days_since_prior_order on the customer's latest observed order.
  Lower values mean the customer ordered again more recently in their observed
  sequence. This is a recency proxy, not calendar-date recency.
- Frequency: count of distinct orders per customer.
- Monetary/value proxy: total basket line items purchased by the customer.

Scores are quintiles generated with NTILE(5). Higher scores are better:
- recency_score: 5 = shortest latest reorder gap, 1 = longest/latest gap.
- frequency_score: 5 = most orders.
- value_score: 5 = most purchased items.
*/

DROP TABLE IF EXISTS customer_rfm_segments;

CREATE TABLE customer_rfm_segments AS
WITH latest_orders AS (
    SELECT DISTINCT ON (o.user_id)
        o.user_id,
        o.order_id AS latest_order_id,
        o.order_number AS latest_order_number,
        COALESCE(o.days_since_prior_order, 999999.0) AS latest_reorder_gap_days
    FROM orders o
    ORDER BY o.user_id, o.order_number DESC, o.order_id DESC
),
customer_order_metrics AS (
    SELECT
        o.user_id,
        COUNT(DISTINCT o.order_id) AS total_orders
    FROM orders o
    GROUP BY o.user_id
),
customer_item_metrics AS (
    SELECT
        o.user_id,
        COUNT(op.product_id) AS total_items_purchased,
        ROUND(COUNT(op.product_id)::NUMERIC / NULLIF(COUNT(DISTINCT o.order_id), 0), 2) AS avg_items_per_order
    FROM orders o
    LEFT JOIN order_products op
        ON o.order_id = op.order_id
    GROUP BY o.user_id
),
customer_metrics AS (
    SELECT
        com.user_id,
        lo.latest_order_id,
        lo.latest_order_number,
        NULLIF(lo.latest_reorder_gap_days, 999999.0) AS latest_reorder_gap_days,
        com.total_orders,
        COALESCE(cim.total_items_purchased, 0) AS total_items_purchased,
        COALESCE(cim.avg_items_per_order, 0) AS avg_items_per_order
    FROM customer_order_metrics com
    JOIN latest_orders lo
        ON com.user_id = lo.user_id
    LEFT JOIN customer_item_metrics cim
        ON com.user_id = cim.user_id
),
scored AS (
    SELECT
        cm.*,
        6 - NTILE(5) OVER (
            ORDER BY COALESCE(cm.latest_reorder_gap_days, 999999.0) ASC, cm.user_id ASC
        ) AS recency_score,
        NTILE(5) OVER (
            ORDER BY cm.total_orders ASC, cm.user_id ASC
        ) AS frequency_score,
        NTILE(5) OVER (
            ORDER BY cm.total_items_purchased ASC, cm.user_id ASC
        ) AS value_score
    FROM customer_metrics cm
),
final_scored AS (
    SELECT
        s.*,
        (s.recency_score + s.frequency_score + s.value_score) AS rfm_score
    FROM scored s
)
SELECT
    fs.user_id,
    fs.latest_order_id,
    fs.latest_order_number,
    fs.latest_reorder_gap_days,
    fs.total_orders,
    fs.total_items_purchased,
    fs.avg_items_per_order,
    fs.recency_score,
    fs.frequency_score,
    fs.value_score,
    fs.rfm_score,
    CASE
        WHEN fs.rfm_score >= 13 THEN 'Champions'
        WHEN fs.rfm_score <= 5 THEN 'Hibernating / Lost'
        WHEN fs.recency_score <= 3 AND fs.rfm_score BETWEEN 6 AND 9 THEN 'At Risk'
        WHEN fs.frequency_score <= 2 AND fs.recency_score >= 4 THEN 'New Customers'
        ELSE 'Loyal Customers'
    END AS customer_segment
FROM final_scored fs;

CREATE INDEX idx_customer_rfm_segments_user_id
    ON customer_rfm_segments(user_id);

CREATE INDEX idx_customer_rfm_segments_segment
    ON customer_rfm_segments(customer_segment);

ANALYZE customer_rfm_segments;

-- Validation summary used by README/dashboard checks.
SELECT
    customer_segment,
    COUNT(*) AS customer_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS customer_pct,
    ROUND(AVG(total_orders), 1) AS avg_orders,
    ROUND(AVG(total_items_purchased), 1) AS avg_items,
    ROUND(AVG(latest_reorder_gap_days)::NUMERIC, 1) AS avg_latest_reorder_gap_days
FROM customer_rfm_segments
GROUP BY customer_segment
ORDER BY customer_count DESC;
