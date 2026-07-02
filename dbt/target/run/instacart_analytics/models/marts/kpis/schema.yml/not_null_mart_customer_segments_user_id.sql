
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select user_id
from "instacart_db"."analytics_kpis"."mart_customer_segments"
where user_id is null



  
  
      
    ) dbt_internal_test