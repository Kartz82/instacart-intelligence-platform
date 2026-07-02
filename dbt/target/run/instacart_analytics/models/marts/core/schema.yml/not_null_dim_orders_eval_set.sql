
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select eval_set
from "instacart_db"."analytics_core"."dim_orders"
where eval_set is null



  
  
      
    ) dbt_internal_test