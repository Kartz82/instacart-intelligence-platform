
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select confidence_a_to_b
from "instacart_db"."analytics_analysis"."mart_basket_affinity"
where confidence_a_to_b is null



  
  
      
    ) dbt_internal_test