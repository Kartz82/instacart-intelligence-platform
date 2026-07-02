
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select behavioral_score
from "instacart_db"."analytics_kpis"."mart_customer_segments"
where behavioral_score is null



  
  
      
    ) dbt_internal_test