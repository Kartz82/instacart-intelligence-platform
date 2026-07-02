
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select lift
from "instacart_db"."analytics_analysis"."mart_basket_affinity"
where lift is null



  
  
      
    ) dbt_internal_test