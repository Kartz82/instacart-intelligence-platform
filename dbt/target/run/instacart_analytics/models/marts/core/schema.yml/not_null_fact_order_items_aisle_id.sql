
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select aisle_id
from "instacart_db"."analytics_core"."fact_order_items"
where aisle_id is null



  
  
      
    ) dbt_internal_test