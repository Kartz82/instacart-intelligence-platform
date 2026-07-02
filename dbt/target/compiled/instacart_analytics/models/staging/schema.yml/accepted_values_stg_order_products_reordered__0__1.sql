
    
    

with all_values as (

    select
        reordered as value_field,
        count(*) as n_records

    from "instacart_db"."analytics_staging"."stg_order_products"
    group by reordered

)

select *
from all_values
where value_field not in (
    '0','1'
)


