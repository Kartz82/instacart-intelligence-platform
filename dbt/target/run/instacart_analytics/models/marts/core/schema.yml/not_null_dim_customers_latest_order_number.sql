
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select latest_order_number
from "instacart_db"."analytics_core"."dim_customers"
where latest_order_number is null



  
  
      
    ) dbt_internal_test