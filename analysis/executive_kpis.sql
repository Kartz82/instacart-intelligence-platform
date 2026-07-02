/*
Business question:
What are the headline operating metrics for the Instacart order dataset?

Notes:
- Query dbt KPI mart only.
- No revenue, margin, AOV, CLV, or price metrics are included.
- Default dbt profile schema is analytics, so this mart builds as analytics_kpis.
*/

select
    total_orders,
    total_customers,
    total_products,
    total_order_items,
    reorder_rate,
    average_basket_size,
    average_orders_per_customer,
    active_departments,
    top_department_by_items
from analytics_kpis.mart_executive_kpis;
