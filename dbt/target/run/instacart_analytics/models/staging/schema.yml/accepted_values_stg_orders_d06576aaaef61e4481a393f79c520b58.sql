
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

with all_values as (

    select
        order_day_of_week as value_field,
        count(*) as n_records

    from "instacart_db"."analytics_staging"."stg_orders"
    group by order_day_of_week

)

select *
from all_values
where value_field not in (
    'Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'
)



  
  
      
    ) dbt_internal_test