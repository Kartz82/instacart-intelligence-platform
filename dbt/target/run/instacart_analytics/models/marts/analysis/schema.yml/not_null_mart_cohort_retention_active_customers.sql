
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select active_customers
from "instacart_db"."analytics_analysis"."mart_cohort_retention"
where active_customers is null



  
  
      
    ) dbt_internal_test