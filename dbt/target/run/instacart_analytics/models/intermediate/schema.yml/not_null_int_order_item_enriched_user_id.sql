
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select user_id
from "instacart_db"."analytics_intermediate"."int_order_item_enriched"
where user_id is null



  
  
      
    ) dbt_internal_test