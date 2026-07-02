
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select behavioral_segment
from "instacart_db"."analytics_kpis"."mart_customer_segments"
where behavioral_segment is null



  
  
      
    ) dbt_internal_test