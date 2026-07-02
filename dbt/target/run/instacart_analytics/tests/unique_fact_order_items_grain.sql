
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  select
    order_id,
    product_id,
    count(*) as row_count
from "instacart_db"."analytics_core"."fact_order_items"
group by order_id, product_id
having count(*) > 1
  
  
      
    ) dbt_internal_test