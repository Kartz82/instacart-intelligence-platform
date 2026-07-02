
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

select
    order_sequence_index as unique_field,
    count(*) as n_records

from "instacart_db"."analytics_analysis"."mart_cohort_retention"
where order_sequence_index is not null
group by order_sequence_index
having count(*) > 1



  
  
      
    ) dbt_internal_test