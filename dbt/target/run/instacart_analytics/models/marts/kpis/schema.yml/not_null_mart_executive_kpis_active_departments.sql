
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select active_departments
from "instacart_db"."analytics_kpis"."mart_executive_kpis"
where active_departments is null



  
  
      
    ) dbt_internal_test