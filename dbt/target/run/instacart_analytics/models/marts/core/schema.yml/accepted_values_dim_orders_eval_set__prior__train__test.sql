
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

with all_values as (

    select
        eval_set as value_field,
        count(*) as n_records

    from "instacart_db"."analytics_core"."dim_orders"
    group by eval_set

)

select *
from all_values
where value_field not in (
    'prior','train','test'
)



  
  
      
    ) dbt_internal_test