
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select reorder_rate
from "instacart_db"."analytics_kpis"."mart_executive_kpis"
where reorder_rate is null



  
  
      
    ) dbt_internal_test