
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select total_order_items
from "instacart_db"."analytics_kpis"."mart_product_performance"
where total_order_items is null



  
  
      
    ) dbt_internal_test