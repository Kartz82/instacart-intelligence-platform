
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select basket_size
from "instacart_db"."analytics_core"."dim_orders"
where basket_size is null



  
  
      
    ) dbt_internal_test