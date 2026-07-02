/*
Business question:
Which products, aisles, and departments drive item volume and repeat behavior?

Notes:
- Query dbt product performance mart only.
- Reorder rate is based on the Instacart reordered flag, not revenue.
*/

select
    product_id,
    product_name,
    aisle_name,
    department_name,
    total_order_items,
    distinct_orders,
    distinct_customers,
    reorder_rate
from analytics_kpis.mart_product_performance
order by total_order_items desc, product_name asc
limit 50;

/*
Department summary for executive review.
*/

select
    department_name,
    sum(total_order_items) as total_order_items,
    sum(distinct_orders) as summed_product_order_reach,
    avg(reorder_rate)::numeric(10, 4) as avg_product_reorder_rate
from analytics_kpis.mart_product_performance
group by department_name
order by total_order_items desc;
