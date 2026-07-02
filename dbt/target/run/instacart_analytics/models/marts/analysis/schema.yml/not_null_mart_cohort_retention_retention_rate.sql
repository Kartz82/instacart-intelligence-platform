
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select retention_rate
from "instacart_db"."analytics_analysis"."mart_cohort_retention"
where retention_rate is null



  
  
      
    ) dbt_internal_test