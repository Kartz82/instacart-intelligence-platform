
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select customer_reorder_rate
from "instacart_db"."analytics_core"."dim_customers"
where customer_reorder_rate is null



  
  
      
    ) dbt_internal_test