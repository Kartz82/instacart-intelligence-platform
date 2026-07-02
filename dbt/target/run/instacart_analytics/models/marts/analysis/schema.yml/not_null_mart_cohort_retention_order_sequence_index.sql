
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select order_sequence_index
from "instacart_db"."analytics_analysis"."mart_cohort_retention"
where order_sequence_index is null



  
  
      
    ) dbt_internal_test