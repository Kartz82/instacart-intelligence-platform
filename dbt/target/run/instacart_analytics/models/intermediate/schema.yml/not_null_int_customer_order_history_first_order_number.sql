
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select first_order_number
from "instacart_db"."analytics_intermediate"."int_customer_order_history"
where first_order_number is null



  
  
      
    ) dbt_internal_test