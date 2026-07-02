
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select customer_reorder_rate
from "instacart_db"."analytics_kpis"."mart_customer_segments"
where customer_reorder_rate is null



  
  
      
    ) dbt_internal_test