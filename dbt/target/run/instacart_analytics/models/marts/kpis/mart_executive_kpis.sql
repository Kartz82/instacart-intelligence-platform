
  
    

  create  table "instacart_db"."analytics_kpis"."mart_executive_kpis__dbt_tmp"
  
  
    as
  
  (
    with order_item_metrics as (
    select
        count(*) as total_order_items,
        avg(reordered)::numeric(10, 4) as reorder_rate
    from "instacart_db"."analytics_core"."fact_order_items"
),

order_metrics as (
    select
        count(*) as total_orders,
        avg(basket_size)::numeric(10, 2) as average_basket_size
    from "instacart_db"."analytics_core"."dim_orders"
),

customer_metrics as (
    select
        count(*) as total_customers,
        avg(total_orders)::numeric(10, 2) as average_orders_per_customer
    from "instacart_db"."analytics_core"."dim_customers"
),

product_metrics as (
    select
        count(*) as total_products
    from "instacart_db"."analytics_core"."dim_products"
),

department_metrics as (
    select
        count(distinct products.department_id) as active_departments
    from "instacart_db"."analytics_core"."fact_order_items" as order_items
    inner join "instacart_db"."analytics_core"."dim_products" as products
        on order_items.product_id = products.product_id
),

department_ranked as (
    select
        products.department_name,
        count(*) as total_order_items,
        row_number() over (
            order by count(*) desc, products.department_name asc
        ) as department_rank
    from "instacart_db"."analytics_core"."fact_order_items" as order_items
    inner join "instacart_db"."analytics_core"."dim_products" as products
        on order_items.product_id = products.product_id
    group by products.department_name
)

select
    1 as kpi_snapshot_id,
    order_metrics.total_orders,
    customer_metrics.total_customers,
    product_metrics.total_products,
    order_item_metrics.total_order_items,
    order_item_metrics.reorder_rate,
    order_metrics.average_basket_size,
    customer_metrics.average_orders_per_customer,
    department_metrics.active_departments,
    department_ranked.department_name as top_department_by_items
from order_metrics
cross join customer_metrics
cross join product_metrics
cross join order_item_metrics
cross join department_metrics
left join department_ranked
    on department_ranked.department_rank = 1
  );
  