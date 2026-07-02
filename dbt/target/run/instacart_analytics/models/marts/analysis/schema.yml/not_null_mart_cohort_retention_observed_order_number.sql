
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select observed_order_number
from "instacart_db"."analytics_analysis"."mart_cohort_retention"
where observed_order_number is null



  
  
      
    ) dbt_internal_test