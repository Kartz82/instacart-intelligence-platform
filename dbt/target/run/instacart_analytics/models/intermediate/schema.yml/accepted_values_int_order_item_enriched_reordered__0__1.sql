
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

with all_values as (

    select
        reordered as value_field,
        count(*) as n_records

    from "instacart_db"."analytics_intermediate"."int_order_item_enriched"
    group by reordered

)

select *
from all_values
where value_field not in (
    '0','1'
)



  
  
      
    ) dbt_internal_test