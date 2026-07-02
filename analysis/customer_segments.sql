/*
Business question:
How are customers distributed across behavioral engagement segments?

Notes:
- Segments are behavioral/RFM-style, not financial RFM.
- No revenue, margin, CLV, or price fields are used.
*/

select
    behavioral_segment,
    count(*) as customer_count,
    (
        count(*)::numeric
        / nullif(sum(count(*)) over (), 0)
    )::numeric(10, 4) as customer_share,
    avg(total_orders)::numeric(10, 2) as avg_orders,
    avg(total_items_purchased)::numeric(10, 2) as avg_items_purchased,
    avg(avg_basket_size)::numeric(10, 2) as avg_basket_size,
    avg(customer_reorder_rate)::numeric(10, 4) as avg_customer_reorder_rate,
    avg(latest_days_since_prior_order)::numeric(10, 2) as avg_latest_reorder_gap_days
from analytics_kpis.mart_customer_segments
group by behavioral_segment
order by customer_count desc;

/*
Segment detail sample for BI validation.
*/

select
    user_id,
    behavioral_segment,
    total_orders,
    total_items_purchased,
    avg_basket_size,
    customer_reorder_rate,
    behavioral_score
from analytics_kpis.mart_customer_segments
order by behavioral_score desc, total_orders desc
limit 100;
