
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select order_hour_of_day
from "instacart_db"."analytics_core"."fact_order_items"
where order_hour_of_day is null



  
  
      
    ) dbt_internal_test