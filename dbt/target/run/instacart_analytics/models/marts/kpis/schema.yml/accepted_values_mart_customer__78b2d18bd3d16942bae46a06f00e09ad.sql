
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

with all_values as (

    select
        recency_proxy_score as value_field,
        count(*) as n_records

    from "instacart_db"."analytics_kpis"."mart_customer_segments"
    group by recency_proxy_score

)

select *
from all_values
where value_field not in (
    '1','2','3','4','5'
)



  
  
      
    ) dbt_internal_test