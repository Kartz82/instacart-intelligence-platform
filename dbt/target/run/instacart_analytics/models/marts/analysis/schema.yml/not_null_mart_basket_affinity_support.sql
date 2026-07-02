
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select support
from "instacart_db"."analytics_analysis"."mart_basket_affinity"
where support is null



  
  
      
    ) dbt_internal_test