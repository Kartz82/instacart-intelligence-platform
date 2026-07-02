
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

with all_values as (

    select
        behavioral_segment as value_field,
        count(*) as n_records

    from "instacart_db"."analytics_kpis"."mart_customer_segments"
    group by behavioral_segment

)

select *
from all_values
where value_field not in (
    'High Engagement','Loyal Routine','At Risk','Early Lifecycle','Moderate Engagement'
)



  
  
      
    ) dbt_internal_test