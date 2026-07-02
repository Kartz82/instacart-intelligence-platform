
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select total_items_purchased
from "instacart_db"."analytics_core"."dim_customers"
where total_items_purchased is null



  
  
      
    ) dbt_internal_test